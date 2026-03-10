from fastapi.testclient import TestClient

import main


class FakeStore:
    async def delete_by_user_id(self, user_id: str) -> int:
        assert user_id == "u-reset"
        return 2


def test_reset_user_state_success(monkeypatch):
    async def _stub_reset_student_state_by_user_id(user_id: str) -> dict[str, int | bool]:
        assert user_id == "u-reset"
        return {
            "deleted_profile": True,
            "deleted_legacy_state": False,
            "deleted_concepts": 5,
        }

    monkeypatch.setattr(main, "store", FakeStore())
    monkeypatch.setattr(main, "reset_student_state_by_user_id", _stub_reset_student_state_by_user_id)

    client = TestClient(main.app)
    resp = client.post("/users/u-reset/reset")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {
        "user_id": "u-reset",
        "deleted_dialogs": 2,
        "deleted_concepts": 5,
        "deleted_profile": True,
        "deleted_legacy_state": False,
    }


def test_reset_user_state_user_id_required(monkeypatch):
    class _AnyStore:
        async def delete_by_user_id(self, user_id: str) -> int:
            _ = user_id
            return 0

    async def _stub_reset_student_state_by_user_id(user_id: str) -> dict[str, int | bool]:
        _ = user_id
        return {
            "deleted_profile": False,
            "deleted_legacy_state": False,
            "deleted_concepts": 0,
        }

    monkeypatch.setattr(main, "store", _AnyStore())
    monkeypatch.setattr(main, "reset_student_state_by_user_id", _stub_reset_student_state_by_user_id)

    client = TestClient(main.app)
    resp = client.post("/users/%20/reset")

    assert resp.status_code == 400
    assert "user_id is required" in resp.text
