import json
import logging
from typing import Any

from lib.agentic.prompt_build.entry_node_prompt_builder import build_entry_node_prompt
from lib.agentic.tools.entry_node_tools import get_entry_node_tools
from lib.llm.litellm_api import call_llm_with_tools
from lib.agentic.nodes.student_state_init_node import (
    get_student_state_by_user_id,
    save_student_state_by_user_id,
    student_state_init_node,
)

try:
    from lib.agentic.config import AgentState
except Exception:
    AgentState = dict[str, Any]

logger = logging.getLogger(__name__)


def _normalize_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


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
        score = _normalize_score(item.get("score", 0))
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


def _compute_familiarity_from_history(history: list[dict[str, Any]]) -> float:
    if not history:
        return 0.0
    avg_score = sum(float(item["score"]) for item in history) / len(history)
    return round(avg_score, 2)


def _normalize_concept_item(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        concept_name = raw.strip()
        qa_history: list[dict[str, Any]] = []
    elif isinstance(raw, dict):
        concept_name = str(raw.get("concept", "") or raw.get("name", "")).strip()
        qa_history = _normalize_qa_history(
            raw.get(
                "qa_history",
                raw.get("history_questions", raw.get("历史提问", [])),
            )
        )
    else:
        return None

    if not concept_name:
        return None

    return {
        "concept": concept_name,
        "familiarity": _compute_familiarity_from_history(qa_history),
        "posterior_question_count": len(qa_history),
        "qa_history": qa_history,
    }


def _extract_raw_concepts(raw: dict[str, Any]) -> list[Any]:
    if isinstance(raw.get("concepts"), list):
        return raw["concepts"]

    # Backward compatibility for old root schema
    legacy_concepts = (
        _normalize_list(raw.get("topic_nodes", []))
        + _normalize_list(raw.get("mastered_concepts", []))
        + _normalize_list(raw.get("vague_concepts", []))
        + _normalize_list(raw.get("misconceptions", []))
    )
    return legacy_concepts


def _normalize_root_node(raw: dict[str, Any]) -> dict[str, Any]:
    concepts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _extract_raw_concepts(raw):
        normalized = _normalize_concept_item(item)
        if normalized is None:
            continue
        concept_key = normalized["concept"].lower()
        if concept_key in seen:
            continue
        seen.add(concept_key)
        concepts.append(normalized)

    return {
        "concepts": concepts,
        "reasoning_pattern": str(raw.get("reasoning_pattern", "")).strip(),
    }


async def _load_state_from_firestore(user_id: str) -> dict[str, Any] | None:
    student_state = await get_student_state_by_user_id(user_id)
    if not isinstance(student_state, dict):
        return None
    root = student_state.get("knowledge_graph_root")
    if not isinstance(root, dict):
        return None
    return root


async def entry_llm_node(state: AgentState) -> AgentState:
    """
    Build the root node for a soft knowledge graph from user's course/interview plan.
    Output shape follows docs/PROPOSAL.md item 1:
    { concepts: [{ concept, familiarity, posterior_question_count, qa_history }], reasoning_pattern }
    """
    user_id = str(state.get("user_id", "") or "").strip()
    if user_id:
        persisted_root = await _load_state_from_firestore(user_id)
        if persisted_root is None:
            state = await student_state_init_node(state)
        elif isinstance(persisted_root.get("concepts"), list) and persisted_root.get("concepts"):
            return {
                **state,
                "query_type": "learning_plan",
                "answer": json.dumps(persisted_root, ensure_ascii=False, indent=2),
                "knowledge_graph_root": persisted_root,
                "planned_skill_calls": [],
                "search_ops": None,
            }

    existing_root = state.get("knowledge_graph_root")
    if isinstance(existing_root, dict) and isinstance(existing_root.get("concepts"), list):
        if existing_root.get("concepts"):
            return state

    question = (
        state.get("question")
        or state.get("course_plan")
        or state.get("user_plan")
        or ""
    )
    question = str(question).strip()
    if not question:
        question = "I am preparing for an ML Algorithm Engineer interview. Please give me a learning plan."

    prompt = build_entry_node_prompt(question)

    tools = get_entry_node_tools()

    root_node: dict[str, Any] | None = None
    try:
        response = await call_llm_with_tools(
            prompt=prompt,
            tools=tools,
            model_name="gpt",
            tool_choice="required",
        )
        if response.get("tool_calls"):
            arguments = response["tool_calls"][0]["function"]["arguments"]
            root_node = _normalize_root_node(json.loads(arguments))
    except Exception as exc:
        logger.warning(f"tool-calling failed in entry node: {exc}")

    if root_node is None:
        root_node = _normalize_root_node({})

    if user_id:
        try:
            await save_student_state_by_user_id(user_id, root_node)
        except Exception as exc:
            logger.warning(f"failed to save student state for user_id={user_id}: {exc}")

    return {
        **state,
        "query_type": "learning_plan",
        "answer": json.dumps(root_node, ensure_ascii=False, indent=2),
        "knowledge_graph_root": root_node,
        "planned_skill_calls": [],
        "search_ops": None,
    }
