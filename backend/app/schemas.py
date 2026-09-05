from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    user_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class SessionCreateResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    query: str


class ChatResponse(BaseModel):
    message_id: int
    answer_type: Literal["text", "clarify", "chart", "report", "error"]
    text: str
    data_rows: list[dict[str, Any]] = Field(default_factory=list)
    chart_config: dict[str, Any] | None = None
    generated_sql: str | None = None
    suggestions: list[dict[str, Any]] = Field(default_factory=list)


class MessageOut(BaseModel):
    id: int
    role: str
    text: str
    answer_type: str | None = None
    chart_config: dict[str, Any] | None = None
    data_rows: list[dict[str, Any]] = Field(default_factory=list)
    generated_sql: str | None = None
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str


class SkillRunRequest(BaseModel):
    skill: Literal[
        "overall_distribution",
        "risk_warning",
        "class_compare",
        "course_deep",
        "trend_compare",
        "group_diff",
    ]
    exam_batch: str | None = None
    course_name: str | None = None


class SkillRunResponse(BaseModel):
    answer_type: Literal["report", "error"]
    text: str
    data_rows: list[dict[str, Any]] = Field(default_factory=list)
    chart_config: dict[str, Any] | None = None
    generated_sql: str | None = None


class AttributionRequest(BaseModel):
    course_name: str | None = None
    exam_batch: str | None = None


class AttributionResponse(BaseModel):
    answer_type: Literal["text", "error"]
    text: str
    data_rows: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    message_id: int
    feedback: Literal[-1, 0, 1]
    feedback_reason: str | None = None


class FeedbackResponse(BaseModel):
    id: int
    message_id: int
    feedback: int
    feedback_reason: str | None
    query: str
    result_summary: str | None
    created_at: str
