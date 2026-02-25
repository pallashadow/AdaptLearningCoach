from typing import Any, TypedDict


class QAItem(TypedDict):
    question: str
    answer: str
    score: float


class ConceptItem(TypedDict):
    concept: str
    familiarity: float
    posterior_question_count: int
    qa_history: list[QAItem]


class KnowledgeGraphRoot(TypedDict):
    concepts: list[ConceptItem]
    reasoning_pattern: str


class AgentState(TypedDict, total=False):
    # Input/user context
    question: str
    course_plan: str
    user_plan: str
    user_answer: str

    # Main graph state
    knowledge_graph_root: KnowledgeGraphRoot
    max_round: int
    current_round: int
    current_concept: str
    current_question: str
    current_feedback: str
    current_score: float
    last_ground_truth: str
    query_type: str

    # Generic response fields
    answer: str
    planned_skill_calls: list[dict[str, Any]]
    search_ops: Any
