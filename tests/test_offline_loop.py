import asyncio
from typing import Any

import pytest

from lib.agentic.simulation.offline_loop import (
    deterministic_choice_question_node,
    run_offline_loop,
)


async def _stub_entry(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "knowledge_graph_root": {
            "concepts": [
                {
                    "concept": "Gradient Descent",
                    "familiarity": 0.0,
                    "posterior_question_count": 0,
                    "qa_history": [],
                }
            ],
            "reasoning_pattern": "test",
        },
    }


def _run(coro):
    return asyncio.run(coro)


def test_offline_loop_runs_to_max_round_without_api_service():
    initial_state = {
        "question": "test",
        "max_round": 3,
        "question_mode": "choice",
        "choice_option_count": 4,
        "auto_answer_enabled": True,
        "auto_answer_proficiency": 100.0,
    }

    result = _run(
        run_offline_loop(
            initial_state,
            entry_node_fn=_stub_entry,
            question_node_fn=deterministic_choice_question_node,
        )
    )

    assert len(result.rounds) == 3
    assert int(result.state["current_round"]) == 3
    root = result.state["knowledge_graph_root"]
    concept = root["concepts"][0]
    assert concept["posterior_question_count"] == 3
    assert len(concept["qa_history"]) == 3
    assert float(concept["familiarity"]) == 60.0
    assert all(float(item.score) == 100.0 for item in result.rounds)


def test_offline_loop_raises_explicit_error_on_invalid_choice_contract():
    async def _invalid_question_node(state: dict[str, Any]) -> dict[str, Any]:
        return {
            **state,
            "question_mode": "choice",
            "choice_option_count": 2,
            "current_question_type": "choice",
            "current_concept": "Gradient Descent",
            "current_question": "bad",
            "current_options": ["A", "B", "C"],
            "current_correct_option": "A",
        }

    initial_state = {
        "question": "test",
        "max_round": 1,
        "question_mode": "choice",
        "choice_option_count": 2,
        "auto_answer_enabled": True,
        "auto_answer_proficiency": 100.0,
    }

    with pytest.raises(ValueError, match="current_options length does not match"):
        _run(
            run_offline_loop(
                initial_state,
                entry_node_fn=_stub_entry,
                question_node_fn=_invalid_question_node,
            )
        )
