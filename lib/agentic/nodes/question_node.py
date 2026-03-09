import json
import logging
from typing import Any

from lib.agentic.config import AgentState
from lib.llm.litellm_api import call_llm_with_tools

logger = logging.getLogger(__name__)
OPTION_LABELS = ("A", "B", "C", "D")


def _normalize_score(raw: Any) -> float:
    try:
        score = float(raw)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(100.0, score))


def _concept_sort_key(concept_item: dict[str, Any]) -> tuple[float, int]:
    familiarity = _normalize_score(concept_item.get("familiarity", 0.0))
    question_count = int(concept_item.get("posterior_question_count", 0) or 0)
    return (familiarity, question_count)


def _build_open_question_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_diagnostic_question",
                "description": "Generate one diagnostic question for the selected concept.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                    },
                    "required": ["question"],
                },
            },
        }
    ]


def _build_choice_question_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_multiple_choice_question",
                "description": "Generate one single-choice diagnostic question for the selected concept.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "correct_option": {
                            "type": "string",
                            "enum": ["A", "B", "C", "D"],
                        },
                    },
                    "required": ["question", "options", "correct_option"],
                },
            },
        }
    ]


def _build_question_prompt(
    concept_name: str,
    learning_goal: str,
    qa_history: list[dict[str, Any]],
    question_mode: str,
    main_question_total: int,
) -> str:
    history_text = json.dumps(qa_history[-5:], ensure_ascii=False, indent=2)
    if main_question_total <= 0:
        main_question_total = 5
    question_index = min(len(qa_history) + 1, main_question_total)
    return (
        "You are a diagnostic tutor. Generate ONE concise question to evaluate user's understanding.\n"
        f"Learning Goal: {learning_goal}\n"
        f"Target concept: {concept_name}\n"
        f"This is diagnostic question #{question_index} out of {main_question_total} for this concept.\n"
        f"Goal: across {main_question_total} questions, cover all major aspects of the concept (definition, intuition, formula/mechanism, example/application, edge cases/comparison).\n"
        "The generated question MUST be a concrete decomposition of the Learning Goal under this Target concept.\n"
        "Do not ask detached trivia; each question should clearly advance diagnosis for the Learning Goal.\n"
        "Use past Q/A to avoid duplicates; pick an uncovered or weakly covered aspect.\n"
        f"Question mode: {question_mode}\n"
        "If mode is open: question should be specific, answerable in 2-6 sentences, and suitable for scoring in [0,100].\n"
        "If mode is choice: this MUST be a single-choice question.\n"
        "Provide one clear stem and 4 options (A/B/C/D) with exactly one correct option.\n"
        "Do not use 'multiple answers', 'all of the above', or 'none of the above'.\n"
        "The learner must be able to answer by choosing exactly one option letter.\n\n"
        f"Past QA history (latest up to 5):\n{history_text}"
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


def _normalize_choice_options(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    normalized = [str(item).strip() for item in raw[:4] if str(item).strip()]
    if len(normalized) != 4:
        return []
    return normalized


def _normalize_correct_option(raw: Any) -> str:
    option = str(raw or "").strip().upper()
    if option in OPTION_LABELS:
        return option
    return "A"


def _format_choice_question(question: str, options: list[str]) -> str:
    rendered_options = [f"{label}. {text}" for label, text in zip(OPTION_LABELS, options)]
    return f"{question}\n" + "\n".join(rendered_options)


async def question_node(state: AgentState) -> AgentState:
    pending_sub_questions = _normalize_sub_questions(state.get("pending_sub_questions", []))
    if pending_sub_questions:
        next_sub_question = pending_sub_questions[0]
        return {
            **state,
            "current_question": next_sub_question,
            "pending_sub_questions": pending_sub_questions[1:],
            "is_followup": True,
            "current_question_type": "open",
            "current_options": [],
            "current_correct_option": "",
            "answer": next_sub_question,
        }

    root = state.get("knowledge_graph_root") or {}
    concepts = root.get("concepts", [])
    if not concepts:
        return {
            **state,
            "current_concept": "",
            "current_question": "",
            "answer": "No concepts found in knowledge_graph_root.",
        }

    # Pick the lowest familiarity concept; if tie, pick the one with fewer attempts.
    concept_item = min(concepts, key=_concept_sort_key)
    concept_name = str(concept_item.get("concept", "")).strip()
    qa_history = concept_item.get("qa_history", [])
    if not isinstance(qa_history, list):
        qa_history = []

    question_mode = str(state.get("question_mode", "choice") or "choice").strip().lower()
    if question_mode not in {"open", "choice"}:
        question_mode = "choice"
    learning_goal = str(state.get("question", "") or state.get("course_plan", "") or state.get("user_plan", "")).strip()
    if not learning_goal:
        learning_goal = "General learning diagnostics."
    main_question_total = int(state.get("max_round", 5) or 5)
    if main_question_total <= 0:
        main_question_total = 5

    prompt = _build_question_prompt(
        concept_name=concept_name,
        learning_goal=learning_goal,
        qa_history=qa_history,
        question_mode=question_mode,
        main_question_total=main_question_total,
    )

    if question_mode == "choice":
        current_options = [
            f"{concept_name} is mainly a debugging tool",
            f"{concept_name} is unrelated to machine learning",
            f"{concept_name} is a core concept that impacts model behavior",
            f"{concept_name} means deleting all training data",
        ]
        current_question = _format_choice_question(
            f"Which statement is most accurate about {concept_name}?",
            current_options,
        )
        current_question_type = "choice"
        current_correct_option = "C"
    else:
        current_question = f"Please explain {concept_name} and give one example."
        current_question_type = "open"
        current_options = []
        current_correct_option = ""
    try:
        if question_mode == "choice":
            response = await call_llm_with_tools(
                prompt=prompt,
                tools=_build_choice_question_tools(),
                model_name="gpt",
                tool_choice="required",
            )
            if response.get("tool_calls"):
                arguments = response["tool_calls"][0]["function"]["arguments"]
                payload = json.loads(arguments)
                generated_question = str(payload.get("question", "")).strip()
                generated_options = _normalize_choice_options(payload.get("options", []))
                if generated_question and generated_options:
                    current_question = _format_choice_question(generated_question, generated_options)
                    current_question_type = "choice"
                    current_options = generated_options
                    current_correct_option = _normalize_correct_option(payload.get("correct_option"))
        else:
            response = await call_llm_with_tools(
                prompt=prompt,
                tools=_build_open_question_tools(),
                model_name="gpt",
                tool_choice="required",
            )
            if response.get("tool_calls"):
                arguments = response["tool_calls"][0]["function"]["arguments"]
                payload = json.loads(arguments)
                generated = str(payload.get("question", "")).strip()
                if generated:
                    current_question = generated
    except Exception as exc:
        logger.warning(f"question generation failed: {exc}")

    return {
        **state,
        "current_concept": concept_name,
        "current_question": current_question,
        "current_question_type": current_question_type,
        "current_options": current_options,
        "current_correct_option": current_correct_option,
        "is_followup": False,
        "parent_question": "",
        "answer": current_question,
    }
