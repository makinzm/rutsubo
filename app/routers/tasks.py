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
    # task_id のみ渡し、バックグラウンドタスク内で独立したDB Sessionを作成する
    background_tasks.add_task(_run_coordinator_sync, task.task_id)

    return task


def _run_coordinator_sync(task_id: str) -> None:
    """
    BackgroundTasks から asyncio コルーチンを呼び出すためのラッパー。

    レスポンス完了後にリクエストスコープのSessionが閉じられる可能性があるため、
    バックグラウンドタスク内で独立したSessionを生成する。
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
    タスクの因果連鎖エントリを取得する。

    タスクが存在しない場合は404を返す。
    タスクが存在するがエントリがない場合は空のリストを返す。
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
