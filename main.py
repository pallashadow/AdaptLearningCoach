import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lib.agentic.config import AgentState
from lib.agentic.nodes.entry_node import entry_llm_node
from lib.agentic.nodes.question_node import question_node
from lib.agentic.nodes.ref_node import ref_node

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartDialogRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Learning goal or interview goal.")
    max_round: int = Field(default=5, ge=1, le=20)


class StartDialogResponse(BaseModel):
    dialog_id: str
    current_round: int
    max_round: int
    current_question: str
    current_concept: str
    knowledge_graph_root: dict[str, Any]


class AnswerRequest(BaseModel):
    dialog_id: str = Field(..., min_length=1)
    user_answer: str = Field(..., min_length=1)


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


class RedisDialogStore:
    def __init__(self, redis_client: Any, key_prefix: str = "agentic:dialog:") -> None:
        self._redis = redis_client
        self._prefix = key_prefix

    def _key(self, dialog_id: str) -> str:
        return f"{self._prefix}{dialog_id}"

    async def get(self, dialog_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(dialog_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, dialog_id: str, value: dict[str, Any]) -> None:
        await self._redis.set(self._key(dialog_id), json.dumps(value, ensure_ascii=False))

    async def delete(self, dialog_id: str) -> bool:
        deleted_count = await self._redis.delete(self._key(dialog_id))
        return bool(deleted_count)


app = FastAPI(title="Agentic Learning API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store: InMemoryDialogStore | RedisDialogStore = InMemoryDialogStore()
redis_client: Any | None = None


@app.on_event("startup")
async def startup_event() -> None:
    global store, redis_client
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        logger.info("REDIS_URL not configured, using in-memory dialog store.")
        return

    try:
        import redis.asyncio as redis  # type: ignore
    except Exception:
        logger.warning("redis package not installed, fallback to in-memory dialog store.")
        return

    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        store = RedisDialogStore(redis_client)
        logger.info("Using Redis dialog store.")
    except Exception as exc:
        logger.warning(f"Redis unavailable ({exc}), fallback to in-memory dialog store.")
        redis_client = None
        store = InMemoryDialogStore()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None


def _snapshot_from_record(dialog_id: str, record: dict[str, Any]) -> DialogSnapshot:
    state = record.get("state", {})
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

    state["user_answer"] = payload.user_answer.strip()
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
