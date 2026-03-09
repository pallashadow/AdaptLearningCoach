import json
import logging
from typing import Any

from lib.agentic.config import AgentState
from lib.llm.litellm_api import call_llm_with_tools

logger = logging.getLogger(__name__)
OPTION_LABELS = ("A", "B", "C", "D")

def _next_round(current_round: int, is_followup: bool) -> int:
    return current_round if is_followup else current_round + 1


def _normalize_score(raw: Any) -> float:
    try:
        score = float(raw)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(100.0, score))


def _normalize_option_answer(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if not text:
        return ""
    for label in OPTION_LABELS:
        if text == label or text.startswith(f"{label}.") or text.startswith(f"{label})") or text.startswith(f"{label} "):
            return label
    return ""


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


def _build_followup_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_sub_questions",
                "description": "Generate concise follow-up sub-questions for weak or incomplete answers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sub_questions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 2,
                        }
                    },
                    "required": ["sub_questions"],
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


def _build_followup_prompt(
    concept: str,
    question: str,
    user_answer: str,
    feedback: str,
    ground_truth: str,
) -> str:
    return (
        "You are a tutor creating progressive follow-up questions.\n"
        "Given the original question and learner answer, generate 1-2 sub-questions that are STRICTLY chained to the learner's mistakes or missing information.\n"
        "Rules:\n"
        "- Do NOT ask random or broad questions.\n"
        "- Focus only on concrete errors/gaps revealed by the learner answer, feedback, and reference answer.\n"
        "- Keep sub-questions in progressive order.\n"
        "- Sub-question 1 targets the most critical error or missing point.\n"
        "- Sub-question 2 (if present) must build on sub-question 1 and go one step deeper on the SAME weak point family; do not switch topic.\n"
        "- Avoid re-asking the original question verbatim.\n"
        "- Each sub-question should be answerable in 1-3 sentences and be directly scorable.\n"
        "- Use precise wording that makes the intended correction explicit.\n\n"
        f"Concept: {concept}\n"
        f"Original question: {question}\n"
        f"Learner answer: {user_answer}\n"
        f"Feedback: {feedback}\n"
        f"Reference answer: {ground_truth}\n"
    )


def _normalize_sub_questions(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


async def _generate_sub_questions(
    concept: str,
    question: str,
    user_answer: str,
    feedback: str,
    ground_truth: str,
) -> list[str]:
    try:
        response = await call_llm_with_tools(
            prompt=_build_followup_prompt(
                concept=concept,
                question=question,
                user_answer=user_answer,
                feedback=feedback,
                ground_truth=ground_truth,
            ),
            tools=_build_followup_tools(),
            model_name="gpt",
            tool_choice="required",
        )
        if response.get("tool_calls"):
            arguments = response["tool_calls"][0]["function"]["arguments"]
            payload = json.loads(arguments)
            return _normalize_sub_questions(payload.get("sub_questions", []))
    except Exception as exc:
        logger.warning(f"sub-question generation failed: {exc}")
    return []


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
    is_followup = bool(state.get("is_followup", False))
    current_question_type = str(state.get("current_question_type", "open") or "open").strip().lower()
    current_correct_option = _normalize_option_answer(state.get("current_correct_option", ""))
    current_options_raw = state.get("current_options", [])
    current_options = current_options_raw if isinstance(current_options_raw, list) else []
    parent_question = str(state.get("parent_question", "")).strip()
    parent_score_raw = _normalize_score(state.get("parent_score_raw", 0.0))
    followup_effective_score = _normalize_score(state.get("followup_effective_score", 0.0))
    followup_threshold = _normalize_score(state.get("followup_threshold", 80.0))
    if followup_threshold <= 0:
        followup_threshold = 80.0

    if not user_answer:
        return {
            **state,
            "max_round": max_round,
            "current_round": _next_round(current_round, is_followup),
            "current_feedback": "Missing user_answer.",
            "current_score": 0.0,
            "current_score_raw": 0.0,
            "last_ground_truth": "",
        }
    if not current_concept or not current_question:
        return {
            **state,
            "max_round": max_round,
            "current_round": _next_round(current_round, is_followup),
            "current_feedback": "Missing current_concept or current_question.",
            "current_score": 0.0,
            "current_score_raw": 0.0,
            "last_ground_truth": "",
        }

    score = 0.0
    feedback = "Answer reviewed."
    ground_truth = ""

    if current_question_type == "choice" and current_correct_option:
        selected_option = _normalize_option_answer(user_answer)
        if selected_option == current_correct_option:
            score = 100.0
            feedback = f"Correct choice: {selected_option}."
        else:
            score = 0.0
            feedback = f"Incorrect choice. You selected '{selected_option or user_answer}', correct answer is '{current_correct_option}'."
        correct_idx = OPTION_LABELS.index(current_correct_option)
        correct_text = (
            str(current_options[correct_idx]).strip()
            if correct_idx < len(current_options)
            else ""
        )
        if correct_text:
            ground_truth = f"{current_correct_option}. {correct_text}"
        else:
            ground_truth = current_correct_option
    else:
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

    pending_sub_questions = _normalize_sub_questions(state.get("pending_sub_questions", []))
    updated_parent_question = parent_question
    updated_parent_score_raw = parent_score_raw
    updated_followup_effective_score = followup_effective_score
    if (
        not is_followup
        and current_question_type != "choice"
        and score < followup_threshold
        and not pending_sub_questions
    ):
        generated_sub_questions = await _generate_sub_questions(
            concept=current_concept,
            question=current_question,
            user_answer=user_answer,
            feedback=feedback,
            ground_truth=ground_truth,
        )
        if generated_sub_questions:
            pending_sub_questions = generated_sub_questions
            updated_parent_question = current_question
            updated_parent_score_raw = score
            updated_followup_effective_score = score

    effective_score = score
    if is_followup:
        baseline_score = parent_score_raw
        if baseline_score <= 0:
            baseline_score = _normalize_score(state.get("current_score", 0.0))
        effective_score = max(score, baseline_score, followup_effective_score)
        updated_followup_effective_score = effective_score
        if not pending_sub_questions:
            updated_parent_question = ""
            updated_parent_score_raw = 0.0
            updated_followup_effective_score = 0.0
    elif not pending_sub_questions:
        updated_parent_question = ""
        updated_parent_score_raw = 0.0
        updated_followup_effective_score = 0.0

    sub_qa_history = state.get("sub_qa_history", [])
    if not isinstance(sub_qa_history, list):
        sub_qa_history = []
    if is_followup:
        sub_qa_history = [
            *sub_qa_history,
            {
                "question": current_question,
                "answer": user_answer,
                "score": score,
            },
        ]

    return {
        **state,
        "knowledge_graph_root": root,
        "max_round": max_round,
        "current_round": _next_round(current_round, is_followup),
        "current_score": effective_score,
        "current_score_raw": score,
        "current_feedback": feedback,
        "last_ground_truth": ground_truth,
        "followup_threshold": followup_threshold,
        "pending_sub_questions": pending_sub_questions,
        "parent_question": updated_parent_question,
        "parent_score_raw": updated_parent_score_raw,
        "followup_effective_score": updated_followup_effective_score,
        "sub_qa_history": sub_qa_history,
        "answer": feedback,
        "user_answer": "",
    }


