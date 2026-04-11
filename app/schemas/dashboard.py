"""
Response schemas for the Dashboard API.
"""

from datetime import datetime

from pydantic import BaseModel


class TaskHistoryItem(BaseModel):
    """A single task execution history entry for an agent."""

    task_id: str
    score: float | None
    reward: float | None
    completed_at: datetime

    model_config = {"from_attributes": True}


class AgentDashboardResponse(BaseModel):
    """Aggregated agent response for the dashboard."""

    agent_id: str
    name: str
    trust_score: float
    total_tasks: int
    total_reward: float
    avg_score: float
    task_history: list[TaskHistoryItem]

    model_config = {"from_attributes": True}


class TaskDashboardResponse(BaseModel):
    """Task list response for the dashboard."""

    task_id: str
    prompt: str
    budget: float
    status: str
    difficulty: str | None
    risk_level: str | None
    causal_chain_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
