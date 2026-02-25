from langgraph.graph import END, StateGraph

from lib.agentic.config import AgentState
from lib.agentic.nodes.auto_answer_node import auto_answer_node
from lib.agentic.nodes.entry_node import entry_llm_node
from lib.agentic.nodes.question_node import question_node
from lib.agentic.nodes.ref_node import ref_node


def _route_after_entry(state: AgentState) -> str:
    user_answer = str(state.get("user_answer", "")).strip()
    has_pending_question = bool(str(state.get("current_question", "")).strip())
    if user_answer and has_pending_question:
        return "ref"
    return "question"


def _route_after_ref(state: AgentState) -> str:
    current_round = int(state.get("current_round", 0) or 0)
    max_round = int(state.get("max_round", 5) or 5)
    if current_round >= max_round:
        return END
    return "question"


class AgenticGraph:
    """Workflow for concept questioning and answer scoring."""

    def build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("entry_llm", entry_llm_node)
        workflow.add_node("question", question_node)
        workflow.add_node("auto_answer", auto_answer_node)
        workflow.add_node("ref", ref_node)

        workflow.set_entry_point("entry_llm")
        workflow.add_conditional_edges(
            "entry_llm",
            _route_after_entry,
            {
                "question": "question",
                "ref": "ref",
            },
        )
        workflow.add_edge("question", "auto_answer")
        workflow.add_edge("auto_answer", "ref")
        workflow.add_conditional_edges(
            "ref",
            _route_after_ref,
            {
                "question": "question",
                END: END,
            },
        )
        return workflow

