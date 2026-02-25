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


def _concept_sort_key(concept_item: dict[str, Any]) -> tuple[float, int]:
    familiarity = _normalize_score(concept_item.get("familiarity", 0.0))
    question_count = int(concept_item.get("posterior_question_count", 0) or 0)
    return (familiarity, question_count)


def _build_question_tools() -> list[dict[str, Any]]:
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


def _build_question_prompt(concept_name: str, qa_history: list[dict[str, Any]]) -> str:
    history_text = json.dumps(qa_history[-5:], ensure_ascii=False, indent=2)
    question_index = min(len(qa_history) + 1, 5)
    return (
        "You are a diagnostic tutor. Generate ONE concise question to evaluate user's understanding.\n"
        f"Target concept: {concept_name}\n"
        f"This is diagnostic question #{question_index} out of 5 for this concept.\n"
        "Goal: across 5 questions, cover all major aspects of the concept (definition, intuition, formula/mechanism, example/application, edge cases/comparison).\n"
        "Use past Q/A to avoid duplicates; pick an uncovered or weakly covered aspect.\n"
        "The question should be specific, answerable in 2-6 sentences, and suitable for scoring in [0,100].\n\n"
        f"Past QA history (latest up to 5):\n{history_text}"
    )


async def question_node(state: AgentState) -> AgentState:
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

    prompt = _build_question_prompt(concept_name, qa_history)

    current_question = f"Please explain {concept_name} and give one example."
    try:
        response = await call_llm_with_tools(
            prompt=prompt,
            tools=_build_question_tools(),
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
        "answer": current_question,
    }
