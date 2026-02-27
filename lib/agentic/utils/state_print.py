from pprint import pprint

from lib.agentic.config import AgentState


def state_brief_print(state: AgentState) -> None:
    concept_name = state.get("current_concept")
    updated_concept = None
    for concept in state.get("knowledge_graph_root", {}).get("concepts", []):
        if concept.get("concept") == concept_name:
            updated_concept = concept
            break

    brief = {
        "current_round": state.get("current_round"),
        "max_round": state.get("max_round"),
        "last_concept": concept_name,
        "last_score": state.get("current_score"),
        "last_feedback": state.get("current_feedback"),
        "last_ground_truth": state.get("last_ground_truth"),
        "updated_concept": updated_concept,
    }
    pprint(brief, width=100, sort_dicts=False)
