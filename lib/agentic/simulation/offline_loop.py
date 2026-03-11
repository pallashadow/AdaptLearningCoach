from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from lib.agentic.config import AgentState
from lib.agentic.nodes.auto_answer_node import auto_answer_node
from lib.agentic.nodes.entry_node import entry_llm_node
from lib.agentic.nodes.question_node import MAX_OPTION_LABELS, question_node
from lib.agentic.nodes.ref_node import ref_node

CHOICE_LABELS = MAX_OPTION_LABELS

StateNode = Callable[[AgentState], Awaitable[AgentState]]
StateValidator = Callable[[dict[str, Any]], None]


@dataclass
class OfflineRoundRecord:
    round_index: int
    concept: str
    question: str
    answer: str
    score: float
    feedback: str


@dataclass
class OfflineLoopResult:
    state: AgentState
    rounds: list[OfflineRoundRecord]


def _normalize_choice_option_count(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 4
    return max(2, min(4, value))


def _validate_choice_question_contract(state: dict[str, Any]) -> None:
    question_mode = str(state.get("question_mode", "choice") or "choice").strip().lower()
    if question_mode != "choice":
        return

    question_type = str(state.get("current_question_type", "") or "").strip().lower()
    if question_type != "choice":
        raise ValueError("current_question_type must be 'choice' in choice mode")

    choice_option_count = _normalize_choice_option_count(state.get("choice_option_count", 4))
    current_options = state.get("current_options", [])
    if not isinstance(current_options, list):
        raise ValueError("current_options must be a list")
    if len(current_options) != choice_option_count:
        raise ValueError("current_options length does not match choice_option_count")

    current_question = str(state.get("current_question", "") or "").strip()
    if not current_question:
        raise ValueError("current_question is empty")

    labels = CHOICE_LABELS[:choice_option_count]
    current_correct_option = str(state.get("current_correct_option", "") or "").strip().upper()
    if current_correct_option not in labels:
        raise ValueError("current_correct_option is not a valid label")


async def deterministic_choice_question_node(state: AgentState) -> AgentState:
    root = dict(state.get("knowledge_graph_root") or {})
    concepts = root.get("concepts", [])
    if not isinstance(concepts, list) or not concepts:
        raise RuntimeError("No concepts found in knowledge_graph_root.")

    concept_item = min(
        concepts,
        key=lambda item: (
            float(item.get("familiarity", 0.0) or 0.0),
            int(item.get("posterior_question_count", 0) or 0),
        ),
    )
    concept_name = str(concept_item.get("concept", "")).strip() or "Unknown Concept"
    option_count = _normalize_choice_option_count(state.get("choice_option_count", 4))
    labels = CHOICE_LABELS[:option_count]
    options = [f"{concept_name} option {label}" for label in labels]
    rendered_options = "\n".join(f"{label}. {text}" for label, text in zip(labels, options))
    question = (
        f"[offline] What is the most accurate statement about {concept_name}?\n"
        f"{rendered_options}"
    )
    return {
        **state,
        "question_mode": "choice",
        "choice_option_count": option_count,
        "current_concept": concept_name,
        "current_question_type": "choice",
        "current_options": options,
        "current_correct_option": "A",
        "current_question": question,
        "is_followup": False,
        "parent_question": "",
        "answer": question,
    }


async def run_offline_loop(
    initial_state: AgentState,
    *,
    entry_node_fn: StateNode = entry_llm_node,
    question_node_fn: StateNode = question_node,
    answer_node_fn: StateNode = auto_answer_node,
    ref_node_fn: StateNode = ref_node,
    state_validator: StateValidator = _validate_choice_question_contract,
) -> OfflineLoopResult:
    state: AgentState = {
        **initial_state,
        "current_round": int(initial_state.get("current_round", 0) or 0),
    }
    rounds: list[OfflineRoundRecord] = []

    state = await entry_node_fn(state)
    state = await question_node_fn(state)
    state_validator(dict(state))

    max_round = int(state.get("max_round", 5) or 5)
    while int(state.get("current_round", 0) or 0) < max_round:
        question_snapshot = str(state.get("current_question", "") or "")
        concept_snapshot = str(state.get("current_concept", "") or "")

        state = await answer_node_fn(state)
        answer_snapshot = str(state.get("user_answer", "") or "")
        state = await ref_node_fn(state)

        rounds.append(
            OfflineRoundRecord(
                round_index=int(state.get("current_round", 0) or 0),
                concept=concept_snapshot,
                question=question_snapshot,
                answer=answer_snapshot,
                score=float(state.get("current_score", 0.0) or 0.0),
                feedback=str(state.get("current_feedback", "") or ""),
            )
        )

        if int(state.get("current_round", 0) or 0) >= max_round:
            break
        state = await question_node_fn(state)
        state_validator(dict(state))

    return OfflineLoopResult(state=state, rounds=rounds)
