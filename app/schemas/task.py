from datetime import datetime

from pydantic import BaseModel, field_validator


class TaskCreateRequest(BaseModel):
    prompt: str
    budget: float

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("prompt must not be empty")
        return v

    @field_validator("budget")
    @classmethod
    def budget_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("budget must be greater than 0")
        return v


class TaskResponse(BaseModel):
    task_id: str
    prompt: str
    budget: float
    status: str
    difficulty: str | None
    risk_level: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
