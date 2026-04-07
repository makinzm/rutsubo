import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
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
    タスクを作成し、バックグラウンドでコーディネーターを起動する。

    エージェントが1件も登録されていない場合は 400 を返す。
    """
    agents = agent_service.list_agents(db)
    if not agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No agents registered. Please register at least one agent before submitting a task.",
        )

    task = create_task(db, req)

    # コーディネーターをバックグラウンドで非同期実行
    background_tasks.add_task(_run_coordinator_sync, task.task_id, db)

    return task


def _run_coordinator_sync(task_id: str, db: Session) -> None:
    """BackgroundTasks から asyncio コルーチンを呼び出すためのラッパー。"""
    from app.services.task_service import get_task as _get_task

    task = _get_task(db, task_id)
    if task is None:
        return
    asyncio.run(run_coordinator(db, task))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task_by_id(task_id: str, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
