import asyncio

import lib.agentic.nodes.entry_node as entry_node


def _run(coro):
    return asyncio.run(coro)


def test_entry_node_uses_persisted_student_state(monkeypatch):
    persisted_root = {
        "concepts": [
            {
                "concept": "Backpropagation",
                "familiarity": 42.0,
                "posterior_question_count": 3,
                "qa_history": [],
            }
        ],
        "reasoning_pattern": "",
    }

    async def _stub_get_student_state(user_id: str):
        assert user_id == "u-1"
        return {"knowledge_graph_root": persisted_root}

    async def _stub_init_node(state):
        raise AssertionError("student_state_init_node should not be called when state exists")

    async def _stub_llm(**kwargs):
        raise AssertionError("LLM should not be called when persisted state exists")

    monkeypatch.setattr(entry_node, "get_student_state_by_user_id", _stub_get_student_state)
    monkeypatch.setattr(entry_node, "student_state_init_node", _stub_init_node)
    monkeypatch.setattr(entry_node, "call_llm_with_tools", _stub_llm)

    state = _run(entry_node.entry_llm_node({"question": "learn ML", "user_id": "u-1"}))

    assert state["knowledge_graph_root"] == persisted_root
    assert state["query_type"] == "learning_plan"


def test_entry_node_initializes_missing_student_state_then_generates(monkeypatch):
    tracker = {
        "init_called": False,
        "saved": None,
    }

    async def _stub_get_student_state(user_id: str):
        assert user_id == "u-2"
        return None

    async def _stub_init_node(state):
        tracker["init_called"] = True
        return {
            **state,
            "knowledge_graph_root": {"concepts": [], "reasoning_pattern": ""},
        }

    async def _stub_save_student_state(user_id: str, knowledge_graph_root: dict):
        tracker["saved"] = (user_id, knowledge_graph_root)
        return True

    async def _stub_llm(**kwargs):
        return {
            "tool_calls": [
                {
                    "function": {
                        "arguments": '{"concepts": ["Linear Regression"], "reasoning_pattern": "top-down"}'
                    }
                }
            ]
        }

    monkeypatch.setattr(entry_node, "get_student_state_by_user_id", _stub_get_student_state)
    monkeypatch.setattr(entry_node, "student_state_init_node", _stub_init_node)
    monkeypatch.setattr(entry_node, "save_student_state_by_user_id", _stub_save_student_state)
    monkeypatch.setattr(entry_node, "call_llm_with_tools", _stub_llm)

    state = _run(entry_node.entry_llm_node({"question": "learn ML", "user_id": "u-2"}))

    assert tracker["init_called"] is True
    assert state["knowledge_graph_root"]["concepts"][0]["concept"] == "Linear Regression"
    assert tracker["saved"][0] == "u-2"
