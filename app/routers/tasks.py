import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.causal_chain import CausalChainEntry
from app.schemas.causal_chain import CausalChainEntryResponse
from app.schemas.task import TaskCreateRequest, TaskResponse
from app.services import agent_service
from app.services.coordinator import run_coordinator
from app.services.task_service import create_task, get_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create(
    req: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a task and launch the coordinator in the background.

    Returns 400 if no agents are registered.
    """
    agents = agent_service.list_agents(db)
    if not agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No agents registered. Please register at least one agent before submitting a task.",
        )

    task = create_task(db, req)

    # Run the coordinator asynchronously in the background.
    # Only the task_id is passed; an independent DB Session is created inside the background task.
    background_tasks.add_task(_run_coordinator_sync, task.task_id)

    return task


def _run_coordinator_sync(task_id: str) -> None:
    """
    Wrapper to call an asyncio coroutine from BackgroundTasks.

    Because the request-scoped Session may be closed after the response is sent,
    an independent Session is created inside the background task.
    """
    db = SessionLocal()
    try:
        task = get_task(db, task_id)
        if task is None:
            return
        asyncio.run(run_coordinator(db, task))
    finally:
        db.close()


@router.get("/{task_id}", response_model=TaskResponse)
def get_task_by_id(task_id: str, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/{task_id}/causal-chain", response_model=list[CausalChainEntryResponse])
def get_causal_chain(task_id: str, db: Session = Depends(get_db)):
    """
    Retrieve causal chain entries for a task.

    Returns 404 if the task does not exist.
    Returns an empty list if the task exists but has no entries.
    """
    task = get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    entries = (
        db.query(CausalChainEntry)
        .filter(CausalChainEntry.task_id == task_id)
        .order_by(CausalChainEntry.created_at)
        .all()
    )
    return entries
