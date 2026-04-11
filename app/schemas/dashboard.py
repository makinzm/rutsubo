"""
ダッシュボードAPIのレスポンススキーマ。
"""

from datetime import datetime

from pydantic import BaseModel


class TaskHistoryItem(BaseModel):
    """エージェントのタスク実行履歴の1件。"""

    task_id: str
    score: float | None
    reward: float | None
    completed_at: datetime

    model_config = {"from_attributes": True}


class AgentDashboardResponse(BaseModel):
    """ダッシュボード用エージェント集計レスポンス。"""

    agent_id: str
    name: str
    trust_score: float
    total_tasks: int
    total_reward: float
    avg_score: float
    task_history: list[TaskHistoryItem]

    model_config = {"from_attributes": True}


class TaskDashboardResponse(BaseModel):
    """ダッシュボード用タスク一覧レスポンス。"""

    task_id: str
    prompt: str
    budget: float
    status: str
    difficulty: str | None
    risk_level: str | None
    causal_chain_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
