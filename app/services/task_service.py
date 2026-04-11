from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskCreateRequest


def create_task(db: Session, req: TaskCreateRequest) -> Task:
    """Create a task and save it to the database (status=pending, difficulty/risk_level=None)."""
    task = Task(
        prompt=req.prompt,
        budget=req.budget,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: str) -> Task | None:
    return db.query(Task).filter(Task.task_id == task_id).first()


def update_task_assessment(
    db: Session,
    task: Task,
    difficulty: str,
    risk_level: str,
    status: str = "running",
) -> Task:
    """Update the difficulty, risk level, and status of a task."""
    task.difficulty = difficulty
    task.risk_level = risk_level
    task.status = status
    db.commit()
    db.refresh(task)
    return task


def update_task_status(db: Session, task: Task, status: str) -> Task:
    task.status = status
    db.commit()
    db.refresh(task)
    return task
