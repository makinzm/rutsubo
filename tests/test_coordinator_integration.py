"""
コーディネーター統合テスト — 評価・分配・trust_score更新フローの確認。

外部依存（Claude API・httpx）はすべてモックする。
DB は conftest.py の StaticPool インメモリ SQLite を使用。
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.agent import Agent
from app.models.task import SubTask, Task


# ---------------------------------------------------------------------------
# テスト用 DB セットアップ
# ---------------------------------------------------------------------------

_TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_claude_mock(difficulty_resp: str, subtasks_resp: str, review_score: str):
    """Claude API の messages.create を side_effect でモックする。"""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=difficulty_resp)]),  # assess_task
        MagicMock(content=[MagicMock(text=subtasks_resp)]),    # decompose_task
        MagicMock(content=[MagicMock(text=review_score)]),     # evaluate_subtask
    ]
    return mock_client


# ---------------------------------------------------------------------------
# test_coordinator_completes_task
# ---------------------------------------------------------------------------


def test_coordinator_completes_task(db):
    """
    全フロー実行後に task.status == 'completed' になることを確認する。
    - エージェント1件登録
    - コーディネーターが難易度判定 → サブタスク分解 → 送信 → 評価 → 分配 → trust_score更新
    """
    import os
    from app.services.coordinator import run_coordinator

    # エージェントをDBに追加
    agent = Agent(
        name="IntegrationAgent",
        description="統合テスト用エージェント",
        wallet_address="Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        endpoint="https://agent-integration.example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # タスクをDBに追加
    task = Task(
        prompt="統合テストのタスク",
        budget=1.0,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    difficulty_resp = '{"difficulty": "medium", "risk_level": "low"}'
    subtasks_resp = json.dumps([{"agent_name": "IntegrationAgent", "subtask": "サブタスク内容"}])
    review_score = '{"score": 0.8}'

    with patch("app.services.llm.complete", side_effect=[
            difficulty_resp, subtasks_resp, review_score
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx, \
         patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):

        # httpx モック（ワーカーへの送信）
        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(status_code=200, text="サブタスクの実行結果")
        )

        asyncio.run(run_coordinator(db, task))

    db.refresh(task)
    assert task.status == "completed"


def test_coordinator_updates_subtask_score(db):
    """
    コーディネーター完了後にSubTaskのscoreが設定されることを確認する。
    """
    import os
    from app.services.coordinator import run_coordinator

    agent = Agent(
        name="ScoreAgent",
        description="スコアテスト用",
        wallet_address="Wa11etCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        endpoint="https://agent-score.example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    task = Task(
        prompt="スコアテストのタスク",
        budget=0.5,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    difficulty_resp = '{"difficulty": "low", "risk_level": "low"}'
    subtasks_resp = json.dumps([{"agent_name": "ScoreAgent", "subtask": "スコアサブタスク"}])
    review_score = '{"score": 0.9}'

    with patch("app.services.llm.complete", side_effect=[
            difficulty_resp, subtasks_resp, review_score
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx, \
         patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):

        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(status_code=200, text="実行結果テキスト")
        )

        asyncio.run(run_coordinator(db, task))

    subtasks = db.query(SubTask).filter(SubTask.task_id == task.task_id).all()
    assert len(subtasks) == 1
    assert subtasks[0].score == pytest.approx(0.9)
    assert subtasks[0].reward is not None
