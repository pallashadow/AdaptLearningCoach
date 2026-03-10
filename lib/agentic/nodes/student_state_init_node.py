import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from lib.agentic.config import AgentState
from lib.api.firestore_crud import FirestoreCRUD

logger = logging.getLogger(__name__)

_firestore_crud: FirestoreCRUD | None = None
_firestore_ready = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile_collection() -> str:
    return os.getenv("FIRESTORE_STUDENT_PROFILE_COLLECTION", "agentic_student_profiles").strip() or "agentic_student_profiles"


def _concept_collection() -> str:
    return os.getenv("FIRESTORE_STUDENT_CONCEPT_COLLECTION", "agentic_student_concepts").strip() or "agentic_student_concepts"


def _legacy_state_collection() -> str:
    return os.getenv("FIRESTORE_STUDENT_COLLECTION", "agentic_student_states").strip() or "agentic_student_states"


def _project_id() -> str | None:
    return os.getenv("FIRESTORE_PROJECT_ID", "").strip() or None


def _default_root() -> dict[str, Any]:
    return {
        "concepts": [],
        "reasoning_pattern": "",
    }


def _normalize_concept_key(concept: str) -> str:
    key = re.sub(r"\s+", "_", concept.strip().lower())
    key = re.sub(r"[^a-z0-9_\-]", "", key)
    return key or "unknown"


def _concept_doc_id(user_id: str, concept: str) -> str:
    return f"{user_id}::{_normalize_concept_key(concept)}"


def _normalize_score(raw: Any) -> float:
    try:
        score = float(raw)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(100.0, score))


def _normalize_qa_history(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    history: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        score = _normalize_score(item.get("score", 0.0))
        if not question and not answer:
            continue
        history.append(
            {
                "question": question,
                "answer": answer,
                "score": score,
            }
        )
    return history


def _normalize_concept_item(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        concept_name = raw.strip()
        familiarity = 0.0
        qa_history: list[dict[str, Any]] = []
    elif isinstance(raw, dict):
        concept_name = str(raw.get("concept", "")).strip()
        familiarity = _normalize_score(raw.get("familiarity", 0.0))
        qa_history = _normalize_qa_history(raw.get("qa_history", []))
    else:
        return None

    if not concept_name:
        return None

    question_count = int(raw.get("posterior_question_count", len(qa_history))) if isinstance(raw, dict) else len(qa_history)
    if question_count < 0:
        question_count = 0

    return {
        "concept": concept_name,
        "familiarity": familiarity,
        "posterior_question_count": question_count,
        "qa_history": qa_history,
    }


async def _get_firestore_crud() -> FirestoreCRUD | None:
    global _firestore_crud, _firestore_ready
    if _firestore_ready:
        return _firestore_crud

    try:
        from google.cloud.firestore_v1.async_client import AsyncClient as FirestoreAsyncClient  # type: ignore
    except Exception:
        logger.warning("google-cloud-firestore not installed, student state persistence disabled.")
        _firestore_ready = True
        _firestore_crud = None
        return None

    try:
        client = FirestoreAsyncClient(project=_project_id())
        await client.collection(_profile_collection()).limit(1).get()
        _firestore_crud = FirestoreCRUD(client)
        _firestore_ready = True
        return _firestore_crud
    except Exception as exc:
        logger.warning(f"Firestore unavailable for student state ({exc}).")
        _firestore_ready = True
        _firestore_crud = None
        return None


async def get_student_state_by_user_id(user_id: str) -> dict[str, Any] | None:
    user_key = str(user_id or "").strip()
    if not user_key:
        return None

    crud = await _get_firestore_crud()
    if crud is None:
        return None

    # 1/2/3 concurrent fetch to reduce latency for student state hydration.
    profile, concept_rows, legacy_state = await asyncio.gather(
        crud.get(_profile_collection(), user_key),
        crud.list_by_field(_concept_collection(), "user_id", user_key),
        crud.get(_legacy_state_collection(), user_key),
    )

    if profile is None and not concept_rows and legacy_state is None:
        return None

    concepts: list[dict[str, Any]] = []
    for row in concept_rows:
        concept_data = row.get("concept_data", {}) if isinstance(row, dict) else {}
        normalized = _normalize_concept_item(concept_data)
        if normalized is not None:
            concepts.append(normalized)

    if not concepts and isinstance(legacy_state, dict):
        legacy_root = legacy_state.get("knowledge_graph_root", {})
        raw_concepts = legacy_root.get("concepts", []) if isinstance(legacy_root, dict) else []
        if isinstance(raw_concepts, list):
            for item in raw_concepts:
                normalized = _normalize_concept_item(item)
                if normalized is not None:
                    concepts.append(normalized)

    concepts.sort(key=lambda item: str(item.get("concept", "")).lower())

    reasoning_pattern = ""
    if isinstance(profile, dict):
        reasoning_pattern = str(profile.get("reasoning_pattern", "")).strip()
    if not reasoning_pattern and isinstance(legacy_state, dict):
        legacy_root = legacy_state.get("knowledge_graph_root", {})
        if isinstance(legacy_root, dict):
            reasoning_pattern = str(legacy_root.get("reasoning_pattern", "")).strip()

    return {
        "user_id": user_key,
        "knowledge_graph_root": {
            "concepts": concepts,
            "reasoning_pattern": reasoning_pattern,
        },
    }


async def save_student_state_by_user_id(user_id: str, knowledge_graph_root: dict[str, Any]) -> bool:
    user_key = str(user_id or "").strip()
    if not user_key:
        return False

    crud = await _get_firestore_crud()
    if crud is None:
        return False

    root = dict(knowledge_graph_root or {})
    raw_concepts = root.get("concepts", [])
    concepts: list[dict[str, Any]] = []
    if isinstance(raw_concepts, list):
        for item in raw_concepts:
            normalized = _normalize_concept_item(item)
            if normalized is not None:
                concepts.append(normalized)

    now = _now_iso()
    profile_collection = _profile_collection()
    concept_collection = _concept_collection()

    existing_profile = await crud.get(profile_collection, user_key)
    existing_concepts = await crud.list_by_field(concept_collection, "user_id", user_key)
    existing_by_doc_id = {
        str(item.get("_doc_id", "")): item
        for item in existing_concepts
        if isinstance(item, dict) and str(item.get("_doc_id", "")).strip()
    }

    target_doc_ids: set[str] = set()
    for concept in concepts:
        concept_name = str(concept.get("concept", "")).strip()
        if not concept_name:
            continue

        doc_id = _concept_doc_id(user_key, concept_name)
        target_doc_ids.add(doc_id)
        existing = existing_by_doc_id.get(doc_id, {})
        payload = {
            "user_id": user_key,
            "concept": concept_name,
            "concept_key": _normalize_concept_key(concept_name),
            "concept_data": concept,
            "created_at": str(existing.get("created_at", now)),
            "updated_at": now,
        }
        await crud.set(concept_collection, doc_id, payload)

    stale_doc_ids = set(existing_by_doc_id.keys()) - target_doc_ids
    for doc_id in stale_doc_ids:
        await crud.delete(concept_collection, doc_id)

    profile_payload = {
        "user_id": user_key,
        "reasoning_pattern": str(root.get("reasoning_pattern", "")).strip(),
        "concept_count": len(target_doc_ids),
        "created_at": str((existing_profile or {}).get("created_at", now)),
        "updated_at": now,
    }
    await crud.set(profile_collection, user_key, profile_payload)
    return True


async def reset_student_state_by_user_id(user_id: str) -> dict[str, int | bool]:
    user_key = str(user_id or "").strip()
    if not user_key:
        return {
            "deleted_profile": False,
            "deleted_legacy_state": False,
            "deleted_concepts": 0,
        }

    crud = await _get_firestore_crud()
    if crud is None:
        return {
            "deleted_profile": False,
            "deleted_legacy_state": False,
            "deleted_concepts": 0,
        }

    concept_rows = await crud.list_by_field(_concept_collection(), "user_id", user_key)
    deleted_concepts = 0
    for row in concept_rows:
        doc_id = str(row.get("_doc_id", "")).strip()
        if not doc_id:
            continue
        deleted = await crud.delete(_concept_collection(), doc_id)
        if deleted:
            deleted_concepts += 1

    deleted_profile = await crud.delete(_profile_collection(), user_key)
    deleted_legacy_state = await crud.delete(_legacy_state_collection(), user_key)
    return {
        "deleted_profile": deleted_profile,
        "deleted_legacy_state": deleted_legacy_state,
        "deleted_concepts": deleted_concepts,
    }


async def student_state_init_node(state: AgentState) -> AgentState:
    user_id = str(state.get("user_id", "") or "").strip()
    if not user_id:
        return state

    root = state.get("knowledge_graph_root")
    if not isinstance(root, dict):
        root = _default_root()

    await save_student_state_by_user_id(user_id, root)
    return {
        **state,
        "knowledge_graph_root": root,
    }
