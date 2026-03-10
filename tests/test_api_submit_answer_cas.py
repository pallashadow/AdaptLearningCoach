import json
from typing import Any

from fastapi.testclient import TestClient

import main


class FakeStore:
    def __init__(self, record: dict[str, Any], fail_count: int = 0) -> None:
        self.record = json.loads(json.dumps(record))
        self.fail_count = fail_count
        self.compare_calls = 0

    async def get(self, dialog_id: str) -> dict[str, Any] | None:
        if dialog_id != "dlg-1":
            return None
        return json.loads(json.dumps(self.record))

    async def compare_and_set(self, dialog_id: str, expected_updated_at: str, value: dict[str, Any]) -> bool:
        self.compare_calls += 1
        if dialog_id != "dlg-1":
            return False
        current_updated_at = str(self.record.get("updated_at", ""))
        if current_updated_at != expected_updated_at:
            return False
        if self.compare_calls <= self.fail_count:
            return False
        self.record = json.loads(json.dumps(value))
        return True

    async def set(self, dialog_id: str, value: dict[str, Any]) -> None:
        self.record = json.loads(json.dumps(value))

    async def delete(self, dialog_id: str) -> bool:
        return dialog_id == "dlg-1"


def _base_record() -> dict[str, Any]:
    return {
        "created_at": "2026-03-09T00:00:00+00:00",
        "updated_at": "2026-03-09T00:00:00+00:00",
        "state": {
            "current_round": 0,
            "max_round": 5,
            "auto_answer_enabled": False,
            "question_mode": "open",
            "current_question_type": "open",
            "current_question": "Q1",
            "current_concept": "C1",
            "knowledge_graph_root": {"concepts": []},
        },
    }


async def _stub_ref_node(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "current_round": int(state.get("current_round", 0)) + 1,
        "current_feedback": "ok",
        "current_score": 88.0,
        "last_ground_truth": "gt",
        "user_answer": "",
    }


async def _stub_question_node(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "current_question": "Q2",
        "current_concept": "C1",
    }


def test_submit_answer_retries_on_conflict_then_succeeds(monkeypatch):
    store = FakeStore(_base_record(), fail_count=2)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "ref_node", _stub_ref_node)
    monkeypatch.setattr(main, "question_node", _stub_question_node)

    client = TestClient(main.app)
    resp = client.post("/dialogs/answer", json={"dialog_id": "dlg-1", "user_answer": "my answer"})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["finished"] is False
    assert payload["current_round"] == 1
    assert payload["current_question"] == "Q2"
    assert store.compare_calls == 3


def test_submit_answer_returns_409_after_retry_exhausted(monkeypatch):
    store = FakeStore(_base_record(), fail_count=10)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "ref_node", _stub_ref_node)
    monkeypatch.setattr(main, "question_node", _stub_question_node)

    client = TestClient(main.app)
    resp = client.post("/dialogs/answer", json={"dialog_id": "dlg-1", "user_answer": "my answer"})

    assert resp.status_code == 409
    assert "concurrently" in resp.text
    assert store.compare_calls == 3
