import json
import logging
from typing import Any

from lib.agentic.config import AgentState
from lib.llm.litellm_api import call_llm_with_tools

logger = logging.getLogger(__name__)


def _normalize_score(raw: Any) -> float:
    try:
        score = float(raw)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(100.0, score))


def _compute_familiarity(qa_history: list[dict[str, Any]]) -> float:
    if not qa_history:
        return 0.0
    recent_five = qa_history[-5:]
    total_score = sum(_normalize_score(item.get("score", 0.0)) for item in recent_five)
    familiarity = total_score / 5.0
    return round(max(0.0, min(100.0, familiarity)), 2)


def _build_ref_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "evaluate_answer",
                "description": "Evaluate user answer quality and return score plus feedback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "description": "Score in [0, 100].",
                        },
                        "feedback": {"type": "string"},
                        "ground_truth_answer": {
                            "type": "string",
                            "description": "A concise reference answer for this question.",
                        },
                    },
                    "required": ["score", "feedback", "ground_truth_answer"],
                },
            },
        }
    ]


def _build_ref_prompt(concept: str, question: str, user_answer: str) -> str:
    return (
        "You are a strict but fair learning reviewer.\n"
        "Evaluate the learner's answer for the given concept and question.\n"
        "Output score in [0, 100] for this single question.\n"
        "Scoring rubric:\n"
        "- 90-100: accurate, complete, clear reasoning/examples\n"
        "- 70-89: mostly correct but missing depth/details\n"
        "- 40-69: partial understanding with notable mistakes/gaps\n"
        "- 0-39: largely incorrect or irrelevant\n"
        "Return concise feedback (1-3 sentences) with key missing points.\n"
        "Also provide a concise ground-truth/reference answer (2-5 sentences) for the same question.\n"
        "System familiarity rule: familiarity = sum(last up to 5 scores) / 5, clipped to [0,100].\n\n"
        f"Concept: {concept}\n"
        f"Question: {question}\n"
        f"Learner answer: {user_answer}\n"
    )


def _update_concept_with_qa(
    concepts: list[dict[str, Any]],
    current_concept: str,
    current_question: str,
    user_answer: str,
    score: float,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    concept_key = current_concept.strip().lower()

    for item in concepts:
        cloned = dict(item)
        name = str(cloned.get("concept", "")).strip().lower()
        if name != concept_key:
            updated.append(cloned)
            continue

        qa_history = cloned.get("qa_history", [])
        if not isinstance(qa_history, list):
            qa_history = []
        qa_history = [entry for entry in qa_history if isinstance(entry, dict)]

        qa_history.append(
            {
                "question": current_question,
                "answer": user_answer,
                "score": score,
            }
        )

        cloned["qa_history"] = qa_history
        cloned["posterior_question_count"] = len(qa_history)
        cloned["familiarity"] = _compute_familiarity(qa_history)
        updated.append(cloned)
    return updated


async def ref_node(state: AgentState) -> AgentState:
    current_round = int(state.get("current_round", 0) or 0)
    max_round = int(state.get("max_round", 5) or 5)

    user_answer = str(state.get("user_answer", "")).strip()
    current_question = str(state.get("current_question", "")).strip()
    current_concept = str(state.get("current_concept", "")).strip()

    if not user_answer:
        return {
            **state,
            "max_round": max_round,
            "current_round": current_round + 1,
            "current_feedback": "Missing user_answer.",
            "current_score": 0.0,
            "last_ground_truth": "",
        }
    if not current_concept or not current_question:
        return {
            **state,
            "max_round": max_round,
            "current_round": current_round + 1,
            "current_feedback": "Missing current_concept or current_question.",
            "current_score": 0.0,
            "last_ground_truth": "",
        }

    score = 0.0
    feedback = "Answer reviewed."
    ground_truth = ""

    try:
        response = await call_llm_with_tools(
            prompt=_build_ref_prompt(current_concept, current_question, user_answer),
            tools=_build_ref_tools(),
            model_name="gpt",
            tool_choice="required",
        )
        if response.get("tool_calls"):
            arguments = response["tool_calls"][0]["function"]["arguments"]
            payload = json.loads(arguments)
            score = _normalize_score(payload.get("score", 0.0))
            candidate_feedback = str(payload.get("feedback", "")).strip()
            candidate_ground_truth = str(payload.get("ground_truth_answer", "")).strip()
            if candidate_feedback:
                feedback = candidate_feedback
            if candidate_ground_truth:
                ground_truth = candidate_ground_truth
    except Exception as exc:
        logger.warning(f"reference evaluation failed: {exc}")

    root = dict(state.get("knowledge_graph_root") or {})
    concepts = root.get("concepts", [])
    if not isinstance(concepts, list):
        concepts = []
    root["concepts"] = _update_concept_with_qa(
        concepts=concepts,
        current_concept=current_concept,
        current_question=current_question,
        user_answer=user_answer,
        score=score,
    )

    return {
        **state,
        "knowledge_graph_root": root,
        "max_round": max_round,
        "current_round": current_round + 1,
        "current_score": score,
        "current_feedback": feedback,
        "last_ground_truth": ground_truth,
        "answer": feedback,
        "user_answer": "",
    }
