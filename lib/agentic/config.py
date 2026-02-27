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
    auto_answer_enabled: bool
    auto_answer_proficiency: float
    question_mode: str
    current_round: int
    current_concept: str
    current_question: str
    current_question_type: str
    current_options: list[str]
    current_correct_option: str
    current_feedback: str
    current_score: float
    current_score_raw: float
    last_ground_truth: str
    query_type: str
    followup_threshold: float
    is_followup: bool
    parent_question: str
    parent_score_raw: float
    followup_effective_score: float
    pending_sub_questions: list[str]
    sub_qa_history: list[QAItem]

    # Generic response fields
    answer: str
    planned_skill_calls: list[dict[str, Any]]
    search_ops: Any
