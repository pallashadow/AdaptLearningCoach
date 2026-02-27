import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lib.agentic.config import AgentState
from lib.agentic.nodes.auto_answer_node import auto_answer_node
from lib.agentic.nodes.entry_node import entry_llm_node
from lib.agentic.nodes.question_node import question_node
from lib.agentic.nodes.ref_node import ref_node

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartDialogRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Learning goal or interview goal.")
    max_round: int = Field(default=5, ge=1, le=20)
    auto_answer_enabled: bool = Field(default=False)
    auto_answer_proficiency: float = Field(default=70.0, ge=0.0, le=100.0)
    question_mode: Literal["open", "choice"] = Field(default="choice")


class StartDialogResponse(BaseModel):
    dialog_id: str
    current_round: int
    max_round: int
    current_question: str
    current_concept: str
    knowledge_graph_root: dict[str, Any]


class AnswerRequest(BaseModel):
    dialog_id: str = Field(..., min_length=1)
    user_answer: str = Field(default="")


class AnswerResponse(BaseModel):
    dialog_id: str
    finished: bool
    current_round: int
    max_round: int
    current_concept: str
    current_question: str
    current_feedback: str
    current_score: float
    last_ground_truth: str


class DialogSnapshot(BaseModel):
    dialog_id: str
    created_at: str
    updated_at: str
    finished: bool
    state: dict[str, Any]


class InMemoryDialogStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, dialog_id: str) -> dict[str, Any] | None:
        async with self._lock:
            item = self._items.get(dialog_id)
            if item is None:
                return None
            return json.loads(json.dumps(item))

    async def set(self, dialog_id: str, value: dict[str, Any]) -> None:
        async with self._lock:
            self._items[dialog_id] = json.loads(json.dumps(value))

    async def delete(self, dialog_id: str) -> bool:
        async with self._lock:
            return self._items.pop(dialog_id, None) is not None


class FirestoreDialogStore:
    def __init__(self, firestore_client: Any, collection: str = "agentic_dialogs") -> None:
        self._firestore = firestore_client
        self._collection = collection

    def _doc(self, dialog_id: str) -> Any:
        return self._firestore.collection(self._collection).document(dialog_id)

    async def get(self, dialog_id: str) -> dict[str, Any] | None:
        snapshot = await self._doc(dialog_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return json.loads(json.dumps(data))

    async def set(self, dialog_id: str, value: dict[str, Any]) -> None:
        await self._doc(dialog_id).set(value)

    async def delete(self, dialog_id: str) -> bool:
        doc_ref = self._doc(dialog_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return False
        await doc_ref.delete()
        return True


store: InMemoryDialogStore | FirestoreDialogStore = InMemoryDialogStore()
firestore_client: Any | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global store, firestore_client
    firestore_project_id = os.getenv("FIRESTORE_PROJECT_ID", "").strip() or None
    firestore_collection = os.getenv("FIRESTORE_COLLECTION", "").strip() or "agentic_dialogs"

    try:
        from google.cloud.firestore_v1.async_client import AsyncClient as FirestoreAsyncClient  # type: ignore
    except Exception:
        logger.warning("google-cloud-firestore not installed, fallback to in-memory dialog store.")
        firestore_client = None
        store = InMemoryDialogStore()
    else:
        try:
            firestore_client = FirestoreAsyncClient(project=firestore_project_id)
            await firestore_client.collection(firestore_collection).limit(1).get()
            store = FirestoreDialogStore(firestore_client, collection=firestore_collection)
            logger.info(f"Using Firestore dialog store (collection={firestore_collection}).")
        except Exception as exc:
            logger.warning(f"Firestore unavailable ({exc}), fallback to in-memory dialog store.")
            firestore_client = None
            store = InMemoryDialogStore()
    try:
        yield
    finally:
        if firestore_client is not None:
            await firestore_client.close()
            firestore_client = None


app = FastAPI(title="Agentic Learning API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/dialogs/start", response_model=StartDialogResponse)
async def start_dialog(payload: StartDialogRequest) -> StartDialogResponse:
    dialog_id = str(uuid4())
    initial_state: AgentState = {
        "question": payload.question.strip(),
        "max_round": payload.max_round,
        "auto_answer_enabled": payload.auto_answer_enabled,
        "auto_answer_proficiency": payload.auto_answer_proficiency,
        "question_mode": payload.question_mode,
        "current_round": 0,
    }

    state = await entry_llm_node(initial_state)
    state = await question_node(state)

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

    record["state"] = state
    record["updated_at"] = _now_iso()
    await store.set(payload.dialog_id, record)

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


@app.get("/dialogs/{dialog_id}", response_model=DialogSnapshot)
async def get_dialog(dialog_id: str) -> DialogSnapshot:
    record = await store.get(dialog_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dialog_id not found")
    return _snapshot_from_record(dialog_id, record)


@app.delete("/dialogs/{dialog_id}")
async def delete_dialog(dialog_id: str) -> dict[str, bool]:
    deleted = await store.delete(dialog_id)
    return {"deleted": deleted}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)
