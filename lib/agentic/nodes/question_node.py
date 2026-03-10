import json
from typing import Any

from lib.agentic.config import AgentState
from lib.llm.litellm_api import call_llm_with_tools

MAX_OPTION_LABELS = ("A", "B", "C", "D")


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


def _normalize_choice_option_count(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 4
    return max(2, min(4, value))


def _option_labels(option_count: int) -> tuple[str, ...]:
    normalized = _normalize_choice_option_count(option_count)
    return MAX_OPTION_LABELS[:normalized]


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


def _build_choice_question_tools(option_labels: tuple[str, ...]) -> list[dict[str, Any]]:
    option_count = len(option_labels)
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_multiple_choice_question",
                "description": "Generate one high-quality single-choice diagnostic question with plausible distractors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "description": "All options must be technically plausible and in the same knowledge scope.",
                            "items": {"type": "string"},
                            "minItems": option_count,
                            "maxItems": option_count,
                        },
                        "correct_option": {
                            "type": "string",
                            "enum": list(option_labels),
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
    option_labels: tuple[str, ...],
) -> str:
    history_text = json.dumps(qa_history[-5:], ensure_ascii=False, indent=2)
    if main_question_total <= 0:
        main_question_total = 5
    question_index = min(len(qa_history) + 1, main_question_total)
    option_text = "/".join(option_labels)
    option_count = len(option_labels)
    return (
        "You are a senior ML interviewer and diagnostic tutor. Generate ONE strong diagnostic question.\n"
        f"Learning Goal: {learning_goal}\n"
        f"Target concept: {concept_name}\n"
        f"Question index: {question_index}/{main_question_total}.\n"
        "The question must test conceptual depth + practical reasoning, not trivia.\n"
        "Use past Q/A to avoid duplicates and target uncovered weak points.\n"
        f"Question mode: {question_mode}.\n"
        "If mode is open: produce one concrete, answerable question (2-6 sentence answer expected).\n"
        "If mode is choice: produce a high-quality single-choice question.\n"
        f"For choice mode, produce exactly {option_count} options labeled {option_text}.\n"
        "Choice quality rules:\n"
        "1) Exactly one correct option.\n"
        "2) Distractors must be plausible misconceptions in the SAME topic.\n"
        "3) Avoid absurd/obviously wrong options.\n"
        "4) No 'all/none of the above'.\n"
        "5) Keep options concise and parallel in style/length.\n"
        "Bad examples (forbidden): 'unrelated to ML', 'delete all data', random nonsense.\n"
        "Good distractor style: subtle confusion between bias vs variance, train vs test error, regularization effects, model complexity trade-offs.\n\n"
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


def _normalize_choice_options(raw: Any, option_count: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    normalized = [str(item).strip() for item in raw[:option_count] if str(item).strip()]
    if len(normalized) != option_count:
        return []
    return normalized


def _normalize_correct_option(raw: Any, option_labels: tuple[str, ...]) -> str:
    option = str(raw or "").strip().upper()
    if option in option_labels:
        return option
    return ""


def _format_choice_question(question: str, options: list[str], option_labels: tuple[str, ...]) -> str:
    rendered_options = [f"{label}. {text}" for label, text in zip(option_labels, options)]
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
        raise RuntimeError("No concepts found in knowledge_graph_root.")

    concept_item = min(concepts, key=_concept_sort_key)
    concept_name = str(concept_item.get("concept", "")).strip()
    qa_history = concept_item.get("qa_history", [])
    if not isinstance(qa_history, list):
        qa_history = []

    question_mode = str(state.get("question_mode", "choice") or "choice").strip().lower()
    if question_mode not in {"open", "choice"}:
        question_mode = "choice"

    choice_option_count = _normalize_choice_option_count(state.get("choice_option_count", 4))
    option_labels = _option_labels(choice_option_count)

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
        option_labels=option_labels,
    )

    if question_mode == "choice":
        try:
            response = await call_llm_with_tools(
                prompt=prompt,
                tools=_build_choice_question_tools(option_labels),
                model_name="gpt",
                tool_choice="required",
            )
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                raise RuntimeError("LLM returned no tool call for choice question generation.")
            arguments = tool_calls[0]["function"]["arguments"]
            payload = json.loads(arguments)

            generated_question = str(payload.get("question", "")).strip()
            generated_options = _normalize_choice_options(payload.get("options", []), choice_option_count)
            generated_correct_option = _normalize_correct_option(payload.get("correct_option"), option_labels)

            if not generated_question:
                raise RuntimeError("LLM returned empty choice question text.")
            if not generated_options:
                raise RuntimeError("LLM returned invalid choice options.")
            if not generated_correct_option:
                raise RuntimeError("LLM returned invalid correct option.")

            current_question = _format_choice_question(generated_question, generated_options, option_labels)
            current_question_type = "choice"
            current_options = generated_options
            current_correct_option = generated_correct_option
        except Exception as exc:
            raise RuntimeError(f"Choice question generation failed: {exc}") from exc
    else:
        try:
            response = await call_llm_with_tools(
                prompt=prompt,
                tools=_build_open_question_tools(),
                model_name="gpt",
                tool_choice="required",
            )
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                raise RuntimeError("LLM returned no tool call for open question generation.")
            arguments = tool_calls[0]["function"]["arguments"]
            payload = json.loads(arguments)
            generated = str(payload.get("question", "")).strip()
            if not generated:
                raise RuntimeError("LLM returned empty open question text.")

            current_question = generated
            current_question_type = "open"
            current_options = []
            current_correct_option = ""
        except Exception as exc:
            raise RuntimeError(f"Open question generation failed: {exc}") from exc

    return {
        **state,
        "choice_option_count": choice_option_count,
        "current_concept": concept_name,
        "current_question": current_question,
        "current_question_type": current_question_type,
        "current_options": current_options,
        "current_correct_option": current_correct_option,
        "is_followup": False,
        "parent_question": "",
        "answer": current_question,
    }
