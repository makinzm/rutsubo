"""
Dashboard API — read-only.

Endpoints:
- GET /dashboard/agents         Aggregate trust scores and reward history for all agents
- GET /dashboard/agents/{id}    Details for a specific agent
- GET /dashboard/tasks          Task list with causal chain summary
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
    """Build aggregated data for an agent."""
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
    """Return aggregated trust scores and reward history for all agents."""
    agents = db.query(Agent).all()
    return [_build_agent_response(db, agent) for agent in agents]


@router.get("/agents/{agent_id}", response_model=AgentDashboardResponse)
def get_agent_dashboard(agent_id: str, db: Session = Depends(get_db)):
    """Return details for a specific agent. Returns 404 if not found."""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _build_agent_response(db, agent)


@router.get("/tasks", response_model=list[TaskDashboardResponse])
def list_task_dashboard(db: Session = Depends(get_db)):
    """Return the task list with a causal chain summary for each task.

    Note:
        Currently queries causal_chain_count per task individually (N+1).
        Optimize with a subquery/GROUP BY when the number of tasks grows.
    """
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
