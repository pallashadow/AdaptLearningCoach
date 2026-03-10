from typing import Any

from fastapi.testclient import TestClient

import main


class FakeStore:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    async def set(self, dialog_id: str, value: dict[str, Any]) -> None:
        self.records[dialog_id] = value

    async def get(self, dialog_id: str) -> dict[str, Any] | None:
        return self.records.get(dialog_id)

    async def compare_and_set(self, dialog_id: str, expected_updated_at: str, value: dict[str, Any]) -> bool:
        _ = expected_updated_at
        self.records[dialog_id] = value
        return True

    async def delete(self, dialog_id: str) -> bool:
        return self.records.pop(dialog_id, None) is not None

    async def delete_by_user_id(self, user_id: str) -> int:
        _ = user_id
        return 0


async def _stub_entry_node(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "knowledge_graph_root": {
            "concepts": [
                {
                    "concept": "Bias-Variance",
                    "familiarity": 0.0,
                    "posterior_question_count": 0,
                    "qa_history": [],
                }
            ],
            "reasoning_pattern": "test",
        },
    }


async def _stub_question_node_valid(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "current_concept": "Bias-Variance",
        "current_question_type": "choice",
        "choice_option_count": 2,
        "current_options": ["Option A", "Option B"],
        "current_correct_option": "A",
        "current_question": "Pick one.\nA. Option A\nB. Option B",
    }


async def _stub_question_node_invalid(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "current_concept": "Bias-Variance",
        "current_question_type": "choice",
        "choice_option_count": 2,
        "current_options": ["Option A", "Option B", "Option C", "Option D"],
        "current_correct_option": "A",
        "current_question": "Pick one.\nA. Option A\nB. Option B\nC. Option C\nD. Option D",
    }


def test_start_dialog_choice_contract_valid(monkeypatch):
    monkeypatch.setattr(main, "store", FakeStore())
    monkeypatch.setattr(main, "entry_llm_node", _stub_entry_node)
    monkeypatch.setattr(main, "question_node", _stub_question_node_valid)

    client = TestClient(main.app)
    resp = client.post(
        "/dialogs/start",
        json={
            "question": "test",
            "question_mode": "choice",
            "choice_option_count": 2,
            "max_round": 5,
            "auto_answer_enabled": False,
            "auto_answer_proficiency": 60,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["current_question"].startswith("Pick one.")
    assert payload["current_concept"] == "Bias-Variance"


def test_start_dialog_choice_contract_invalid_returns_500(monkeypatch):
    monkeypatch.setattr(main, "store", FakeStore())
    monkeypatch.setattr(main, "entry_llm_node", _stub_entry_node)
    monkeypatch.setattr(main, "question_node", _stub_question_node_invalid)

    client = TestClient(main.app)
    resp = client.post(
        "/dialogs/start",
        json={
            "question": "test",
            "question_mode": "choice",
            "choice_option_count": 2,
            "max_round": 5,
            "auto_answer_enabled": False,
            "auto_answer_proficiency": 60,
        },
    )

    assert resp.status_code == 500
    assert "INVALID_CHOICE_QUESTION" in resp.text
