import asyncio

from lib.agentic.nodes.ref_node import ref_node


BASE_STATE = {
    "max_round": 5,
    "current_round": 2,
    "current_concept": "Gradient Descent",
    "current_question": "What does learning rate do?",
    "current_question_type": "choice",
    "current_options": ["A", "B", "C", "D"],
    "current_correct_option": "A",
    "knowledge_graph_root": {
        "concepts": [
            {
                "concept": "Gradient Descent",
                "familiarity": 0.0,
                "posterior_question_count": 0,
                "qa_history": [],
            }
        ]
    },
}


def _run(coro):
    return asyncio.run(coro)


def test_main_question_increments_round():
    state = {
        **BASE_STATE,
        "is_followup": False,
        "user_answer": "A",
    }

    updated = _run(ref_node(state))

    assert updated["current_round"] == 3


def test_followup_question_does_not_increment_round():
    state = {
        **BASE_STATE,
        "is_followup": True,
        "user_answer": "A",
    }

    updated = _run(ref_node(state))

    assert updated["current_round"] == 2


def test_missing_answer_followup_does_not_increment_round():
    state = {
        **BASE_STATE,
        "is_followup": True,
        "user_answer": "",
    }

    updated = _run(ref_node(state))

    assert updated["current_round"] == 2
    assert updated["current_feedback"] == "Missing user_answer."


def test_missing_answer_main_question_increments_round():
    state = {
        **BASE_STATE,
        "is_followup": False,
        "user_answer": "",
    }

    updated = _run(ref_node(state))

    assert updated["current_round"] == 3
    assert updated["current_feedback"] == "Missing user_answer."
