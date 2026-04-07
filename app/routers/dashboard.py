"""
ダッシュボードAPI — 読み取り専用。

エンドポイント:
- GET /dashboard/agents         全エージェントの信頼スコア・報酬履歴集計
- GET /dashboard/agents/{id}    特定エージェントの詳細
- GET /dashboard/tasks          タスク一覧＋因果連鎖サマリー
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.agent import Agent
from app.models.causal_chain import CausalChainEntry
from app.models.task import SubTask, Task
from app.schemas.dashboard import AgentDashboardResponse, TaskDashboardResponse, TaskHistoryItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_agent_response(db: Session, agent: Agent) -> AgentDashboardResponse:
    """エージェントの集計データを構築する。"""
    subtasks = (
        db.query(SubTask)
        .filter(SubTask.agent_id == agent.agent_id, SubTask.status == "completed")
        .all()
    )

    total_tasks = len(subtasks)
    total_reward = sum(s.reward for s in subtasks if s.reward is not None)
    scores = [s.score for s in subtasks if s.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    task_history = [
        TaskHistoryItem(
            task_id=s.task_id,
            score=s.score,
            reward=s.reward,
            completed_at=s.created_at,
        )
        for s in subtasks
    ]

    return AgentDashboardResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        trust_score=agent.trust_score,
        total_tasks=total_tasks,
        total_reward=total_reward,
        avg_score=avg_score,
        task_history=task_history,
    )


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------


@router.get("/agents", response_model=list[AgentDashboardResponse])
def list_agent_dashboard(db: Session = Depends(get_db)):
    """全エージェントの信頼スコア・報酬履歴を集計して返す。"""
    agents = db.query(Agent).all()
    return [_build_agent_response(db, agent) for agent in agents]


@router.get("/agents/{agent_id}", response_model=AgentDashboardResponse)
def get_agent_dashboard(agent_id: str, db: Session = Depends(get_db)):
    """特定エージェントの詳細を返す。存在しない場合は 404。"""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _build_agent_response(db, agent)


@router.get("/tasks", response_model=list[TaskDashboardResponse])
def list_task_dashboard(db: Session = Depends(get_db)):
    """タスク一覧と各タスクの因果連鎖サマリーを返す。"""
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    result = []
    for task in tasks:
        causal_chain_count = (
            db.query(CausalChainEntry)
            .filter(CausalChainEntry.task_id == task.task_id)
            .count()
        )
        result.append(
            TaskDashboardResponse(
                task_id=task.task_id,
                prompt=task.prompt,
                budget=task.budget,
                status=task.status,
                difficulty=task.difficulty,
                risk_level=task.risk_level,
                causal_chain_count=causal_chain_count,
                created_at=task.created_at,
            )
        )
    return result
