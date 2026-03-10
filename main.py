import logging
import os
from inspect import isawaitable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from lib.api.dialog_store import FirestoreDialogStore
from lib.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    DialogSnapshot,
    DeleteUserDialogsResponse,
    ResetUserStateResponse,
    StartDialogRequest,
    StartDialogResponse,
)
from lib.agentic.config import AgentState
from lib.agentic.nodes.auto_answer_node import auto_answer_node
from lib.agentic.nodes.entry_node import entry_llm_node
from lib.agentic.nodes.question_node import question_node
from lib.agentic.nodes.ref_node import ref_node
from lib.agentic.nodes.student_state_init_node import reset_student_state_by_user_id

logger = logging.getLogger(__name__)
CHOICE_LABELS = ("A", "B", "C", "D")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_cors_origins() -> list[str]:
    default_origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return default_origins
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or default_origins


store: FirestoreDialogStore | None = None
firestore_client: Any | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global store, firestore_client
    firestore_project_id = os.getenv("FIRESTORE_PROJECT_ID", "").strip() or None
    firestore_collection = os.getenv("FIRESTORE_COLLECTION", "").strip() or "agentic_dialogs"

    try:
        from google.cloud.firestore_v1.async_client import AsyncClient as FirestoreAsyncClient  # type: ignore
    except Exception as exc:
        raise RuntimeError("google-cloud-firestore is required and must be installed.") from exc

    firestore_client = FirestoreAsyncClient(project=firestore_project_id)
    await firestore_client.collection(firestore_collection).limit(1).get()
    store = FirestoreDialogStore(firestore_client, collection=firestore_collection)
    logger.info(f"Using Firestore dialog store (collection={firestore_collection}).")

    try:
        yield
    finally:
        if firestore_client is not None:
            close_result = firestore_client.close()
            if isawaitable(close_result):
                await close_result
            firestore_client = None
        store = None


app = FastAPI(title="Agentic Learning API", version="0.1.0", lifespan=lifespan)

cors_allow_origins = _parse_cors_origins()
cors_allow_credentials = _parse_bool_env("CORS_ALLOW_CREDENTIALS", default=False)
if cors_allow_credentials and "*" in cors_allow_origins:
    logger.warning("CORS_ALLOW_CREDENTIALS=true is incompatible with wildcard origin '*'; downgrading credentials to false.")
    cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _snapshot_from_record(dialog_id: str, record: dict[str, Any]) -> DialogSnapshot:
    raw_state = record.get("state", {})
    state = dict(raw_state) if isinstance(raw_state, dict) else {}
    # Keep correctness data server-side so client snapshots cannot leak answers.
    state.pop("current_correct_option", None)
    current_round = int(state.get("current_round", 0) or 0)
    max_round = int(state.get("max_round", 0) or 0)
    finished = current_round >= max_round and max_round > 0
    return DialogSnapshot(
        dialog_id=dialog_id,
        created_at=str(record.get("created_at", "")),
        updated_at=str(record.get("updated_at", "")),
        finished=finished,
        state=state,
    )


def _validate_choice_question_contract(state: dict[str, Any]) -> None:
    question_mode = str(state.get("question_mode", "choice") or "choice").strip().lower()
    if question_mode != "choice":
        return

    question_type = str(state.get("current_question_type", "") or "").strip().lower()
    if question_type != "choice":
        raise ValueError(f"question_type must be 'choice' when question_mode='choice', got '{question_type or '-'}'")

    raw_option_count = state.get("choice_option_count", 4)
    try:
        choice_option_count = int(raw_option_count)
    except (TypeError, ValueError):
        raise ValueError(f"choice_option_count must be an integer in [2,4], got '{raw_option_count}'")
    if choice_option_count < 2 or choice_option_count > 4:
        raise ValueError(f"choice_option_count must be in [2,4], got '{choice_option_count}'")

    current_question = str(state.get("current_question", "") or "").strip()
    if not current_question:
        raise ValueError("current_question is empty")

    current_options = state.get("current_options", [])
    if not isinstance(current_options, list):
        raise ValueError("current_options must be a list")
    if len(current_options) != choice_option_count:
        raise ValueError(
            f"current_options length must equal choice_option_count ({choice_option_count}), got {len(current_options)}"
        )

    labels = CHOICE_LABELS[:choice_option_count]
    current_correct_option = str(state.get("current_correct_option", "") or "").strip().upper()
    if current_correct_option not in labels:
        raise ValueError(f"current_correct_option must be one of {labels}, got '{current_correct_option or '-'}'")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/dialogs/start", response_model=StartDialogResponse)
async def start_dialog(payload: StartDialogRequest) -> StartDialogResponse:
    if store is None:
        raise HTTPException(status_code=503, detail="Firestore store is not initialized")

    dialog_id = str(uuid4())
    initial_state: AgentState = {
        "question": payload.question.strip(),
        "user_id": payload.user_id.strip(),
        "max_round": payload.max_round,
        "auto_answer_enabled": payload.auto_answer_enabled,
        "auto_answer_proficiency": payload.auto_answer_proficiency,
        "question_mode": payload.question_mode,
        "choice_option_count": payload.choice_option_count,
        "current_round": 0,
    }

    state = await entry_llm_node(initial_state)
    state = await question_node(state)
    try:
        _validate_choice_question_contract(state)
    except ValueError as exc:
        logger.error("Choice question contract failed in /dialogs/start for dialog_id=%s: %s", dialog_id, exc)
        raise HTTPException(status_code=500, detail=f"INVALID_CHOICE_QUESTION: {exc}") from exc

    timestamp = _now_iso()
    record = {
        "created_at": timestamp,
        "updated_at": timestamp,
        "state": state,
    }
    await store.set(dialog_id, record)

    return StartDialogResponse(
        dialog_id=dialog_id,
        current_round=int(state.get("current_round", 0) or 0),
        max_round=int(state.get("max_round", payload.max_round) or payload.max_round),
        current_question=str(state.get("current_question", "")),
        current_concept=str(state.get("current_concept", "")),
        knowledge_graph_root=dict(state.get("knowledge_graph_root") or {}),
    )


@app.post("/dialogs/answer", response_model=AnswerResponse)
async def submit_answer(payload: AnswerRequest) -> AnswerResponse:
    if store is None:
        raise HTTPException(status_code=503, detail="Firestore store is not initialized")

    max_write_retries = 3

    for attempt in range(max_write_retries):
        record = await store.get(payload.dialog_id)
        if record is None:
            raise HTTPException(status_code=404, detail="dialog_id not found")

        state = dict(record.get("state") or {})
        current_round = int(state.get("current_round", 0) or 0)
        max_round = int(state.get("max_round", 5) or 5)
        if current_round >= max_round:
            raise HTTPException(status_code=400, detail="dialog already finished")

        auto_answer_enabled = bool(state.get("auto_answer_enabled", False))
        if auto_answer_enabled:
            state = await auto_answer_node(state)
        else:
            user_answer = payload.user_answer.strip()
            if not user_answer:
                raise HTTPException(status_code=400, detail="user_answer is required when auto_answer_enabled=false")
            state["user_answer"] = user_answer
        state = await ref_node(state)

        current_round = int(state.get("current_round", 0) or 0)
        finished = current_round >= max_round
        if not finished:
            state = await question_node(state)
            try:
                _validate_choice_question_contract(state)
            except ValueError as exc:
                logger.error("Choice question contract failed in /dialogs/answer for dialog_id=%s: %s", payload.dialog_id, exc)
                raise HTTPException(status_code=500, detail=f"INVALID_CHOICE_QUESTION: {exc}") from exc

        expected_updated_at = str(record.get("updated_at", ""))
        next_record = {
            **record,
            "state": state,
            "updated_at": _now_iso(),
        }
        updated = await store.compare_and_set(payload.dialog_id, expected_updated_at, next_record)
        if updated:
            return AnswerResponse(
                dialog_id=payload.dialog_id,
                finished=finished,
                current_round=current_round,
                max_round=max_round,
                current_concept=str(state.get("current_concept", "")),
                current_question="" if finished else str(state.get("current_question", "")),
                current_feedback=str(state.get("current_feedback", "")),
                current_score=float(state.get("current_score", 0.0) or 0.0),
                last_ground_truth=str(state.get("last_ground_truth", "")),
            )

        logger.info("Concurrent update conflict on dialog_id=%s (attempt %s/%s)", payload.dialog_id, attempt + 1, max_write_retries)

    raise HTTPException(status_code=409, detail="dialog was updated concurrently, please retry")


@app.get("/dialogs/{dialog_id}", response_model=DialogSnapshot)
async def get_dialog(dialog_id: str) -> DialogSnapshot:
    if store is None:
        raise HTTPException(status_code=503, detail="Firestore store is not initialized")

    record = await store.get(dialog_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dialog_id not found")
    return _snapshot_from_record(dialog_id, record)


@app.delete("/dialogs/{dialog_id}")
async def delete_dialog(dialog_id: str) -> dict[str, bool]:
    if store is None:
        raise HTTPException(status_code=503, detail="Firestore store is not initialized")

    deleted = await store.delete(dialog_id)
    return {"deleted": deleted}



@app.delete("/users/{user_id}/dialogs", response_model=DeleteUserDialogsResponse)
async def delete_user_dialogs(user_id: str) -> DeleteUserDialogsResponse:
    if store is None:
        raise HTTPException(status_code=503, detail="Firestore store is not initialized")

    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    deleted_count = await store.delete_by_user_id(normalized_user_id)
    return DeleteUserDialogsResponse(user_id=normalized_user_id, deleted_count=deleted_count)


@app.post("/users/{user_id}/reset", response_model=ResetUserStateResponse)
async def reset_user_state(user_id: str) -> ResetUserStateResponse:
    if store is None:
        raise HTTPException(status_code=503, detail="Firestore store is not initialized")

    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    deleted_dialogs = await store.delete_by_user_id(normalized_user_id)
    reset_result = await reset_student_state_by_user_id(normalized_user_id)

    return ResetUserStateResponse(
        user_id=normalized_user_id,
        deleted_dialogs=deleted_dialogs,
        deleted_concepts=int(reset_result.get("deleted_concepts", 0) or 0),
        deleted_profile=bool(reset_result.get("deleted_profile", False)),
        deleted_legacy_state=bool(reset_result.get("deleted_legacy_state", False)),
    )

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)




