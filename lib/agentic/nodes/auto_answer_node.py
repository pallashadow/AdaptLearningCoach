import json
import logging
from typing import Any

from lib.agentic.config import AgentState
from lib.llm.litellm_api import call_llm_with_tools

logger = logging.getLogger(__name__)


def _build_auto_answer_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_auto_answer",
                "description": "Generate a learner-style answer for the question.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                    },
                    "required": ["answer"],
                },
            },
        }
    ]


def _build_auto_answer_prompt(concept: str, question: str, qa_history: list[dict[str, Any]]) -> str:
    history_text = json.dumps(qa_history[-3:], ensure_ascii=False, indent=2)
    return (
        "You are simulating a learner answering a tutor question.\n"
        "Write one concise but meaningful answer (2-6 sentences).\n"
        "Target concept:\n"
        f"{concept}\n"
        "Current question:\n"
        f"{question}\n"
        "Past attempts (latest up to 3):\n"
        f"{history_text}\n"
        "Try to improve over previous weak points when possible."
    )


async def auto_answer_node(state: AgentState) -> AgentState:
    current_question = str(state.get("current_question", "")).strip()
    current_concept = str(state.get("current_concept", "")).strip()
    if not current_question:
        return {
            **state,
            "user_answer": "",
            "answer": "Missing current_question.",
        }

    root = state.get("knowledge_graph_root") or {}
    concepts = root.get("concepts", [])
    qa_history: list[dict[str, Any]] = []
    if isinstance(concepts, list):
        for concept_item in concepts:
            if not isinstance(concept_item, dict):
                continue
            if str(concept_item.get("concept", "")).strip().lower() == current_concept.lower():
                candidate = concept_item.get("qa_history", [])
                if isinstance(candidate, list):
                    qa_history = [entry for entry in candidate if isinstance(entry, dict)]
                break

    auto_answer = "I need more context, but I will try to explain the core idea and provide one example."
    try:
        response = await call_llm_with_tools(
            prompt=_build_auto_answer_prompt(current_concept, current_question, qa_history),
            tools=_build_auto_answer_tools(),
            model_name="gpt",
            tool_choice="required",
        )
        if response.get("tool_calls"):
            arguments = response["tool_calls"][0]["function"]["arguments"]
            payload = json.loads(arguments)
            generated = str(payload.get("answer", "")).strip()
            if generated:
                auto_answer = generated
    except Exception as exc:
        logger.warning(f"auto answer generation failed: {exc}")

    return {
        **state,
        "user_answer": auto_answer,
        "answer": auto_answer,
    }
