from typing import Any, Literal

from pydantic import BaseModel, Field


class StartDialogRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Learning goal or interview goal.")
    user_id: str = Field(default="", description="Stable user identifier for loading/saving student state.")
    max_round: int = Field(default=5, ge=1, le=20)
    auto_answer_enabled: bool = Field(default=False)
    auto_answer_proficiency: float = Field(default=70.0, ge=0.0, le=100.0)
    question_mode: Literal["open", "choice"] = Field(default="choice")
    choice_option_count: int = Field(default=4, ge=2, le=4)


class StartDialogResponse(BaseModel):
    dialog_id: str
    current_round: int
    max_round: int
    current_question: str
    current_concept: str
    knowledge_graph_root: dict[str, Any]


class AnswerRequest(BaseModel):
    dialog_id: str = Field(..., min_length=1)
    user_answer: str = Field(default="")


class AnswerResponse(BaseModel):
    dialog_id: str
    finished: bool
    current_round: int
    max_round: int
    current_concept: str
    current_question: str
    current_feedback: str
    current_score: float
    last_ground_truth: str


class DialogSnapshot(BaseModel):
    dialog_id: str
    created_at: str
    updated_at: str
    finished: bool
    state: dict[str, Any]


class DeleteUserDialogsResponse(BaseModel):
    user_id: str
    deleted_count: int


class ResetUserStateResponse(BaseModel):
    user_id: str
    deleted_dialogs: int
    deleted_concepts: int
    deleted_profile: bool
    deleted_legacy_state: bool
