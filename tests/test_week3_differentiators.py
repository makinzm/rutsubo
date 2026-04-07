"""
Week 3 差別化機能のテスト。

テスト対象:
1. ε-greedy 焼きなまし（compute_epsilon）
2. 因果連鎖の可視化（CausalChainEntry モデル・GET エンドポイント）
3. 非対称損失関数のパラメータ化（reviewer の risk_weight）

外部依存（Claude API）は unittest.mock でモックする。
DB は StaticPool インメモリ SQLite を使用。
"""

import asyncio
import json
import math
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.agent import Agent
from app.models.task import Task


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
# 機能1: ε-greedy 焼きなまし
# ---------------------------------------------------------------------------


def test_epsilon_decreases_with_tasks():
    """タスク数が増えるとεが単調減少することを確認する。"""
    from app.services.coordinator import compute_epsilon

    eps_0 = compute_epsilon(0)
    eps_10 = compute_epsilon(10)
    eps_50 = compute_epsilon(50)
    eps_100 = compute_epsilon(100)

    assert eps_0 > eps_10 > eps_50
    assert eps_50 >= eps_100


def test_epsilon_minimum_floor():
    """大量タスク後もε≥0.05（最小値フロア）が保証されることを確認する。"""
    from app.services.coordinator import compute_epsilon

    # 非常に大きいタスク数でも最小値フロアを下回らない
    eps = compute_epsilon(10000)
    assert eps >= 0.05


def test_epsilon_initial_value():
    """n_tasks=0 のときに ε_initial（0.3）が返されることを確認する。"""
    from app.services.coordinator import compute_epsilon

    eps = compute_epsilon(0)
    assert eps == pytest.approx(0.3)


def test_epsilon_formula():
    """ε = max(0.05, 0.3 * exp(-0.01 * n)) の計算式が正しいことを確認する。"""
    from app.services.coordinator import compute_epsilon

    n = 30
    expected = max(0.05, 0.3 * math.exp(-0.01 * n))
    assert compute_epsilon(n) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# 機能2: 因果連鎖の可視化
# ---------------------------------------------------------------------------


def test_causal_chain_entries_created(db):
    """
    コーディネーターがタスクを完了させた後、
    CausalChainEntry が DB に保存されることを確認する。
    """
    from app.models.causal_chain import CausalChainEntry
    from app.services.coordinator import run_coordinator

    agent = Agent(
        name="CausalAgent",
        description="因果連鎖テスト用",
        wallet_address="Wa11etCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        endpoint="https://causal-agent.example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    task = Task(
        prompt="因果連鎖テストのタスク",
        budget=1.0,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    difficulty_resp = '{"difficulty": "medium", "risk_level": "medium"}'
    subtasks_resp = json.dumps([{"agent_name": "CausalAgent", "subtask": "サブタスク"}])
    review_score = '{"score": 0.7}'

    with patch("app.services.llm.complete", side_effect=[
            difficulty_resp,
            subtasks_resp,
            review_score,
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx, \
         patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):

        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(status_code=200, text="実行結果")
        )

        asyncio.run(run_coordinator(db, task))

    entries = db.query(CausalChainEntry).filter(
        CausalChainEntry.task_id == task.task_id
    ).all()
    assert len(entries) > 0
    # worker レイヤーのエントリが存在する
    worker_entries = [e for e in entries if e.layer == "worker"]
    assert len(worker_entries) > 0
    assert worker_entries[0].score is not None


def test_get_causal_chain_api(client):
    """
    GET /tasks/{task_id}/causal-chain が存在するタスクに対して200を返すことを確認する。
    CausalChainEntry が存在しない場合も200（空のリスト）を返す。
    """
    # まずエージェントを登録してタスクを作成
    client.post("/agents/register", json={
        "name": "CausalAPIAgent",
        "description": "APIテスト用",
        "wallet_address": "Wa11etDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
        "endpoint": "https://causal-api-agent.example.com",
    })

    with patch("app.routers.tasks.run_coordinator"):
        resp = client.post("/tasks", json={"prompt": "テストタスク", "budget": 0.5})
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    causal_resp = client.get(f"/tasks/{task_id}/causal-chain")
    assert causal_resp.status_code == 200
    data = causal_resp.json()
    assert isinstance(data, list)


def test_causal_chain_not_found(client):
    """
    存在しない task_id に対して GET /tasks/{task_id}/causal-chain が404を返すことを確認する。
    """
    resp = client.get("/tasks/nonexistent-task-id/causal-chain")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 機能3: 非対称損失関数のパラメータ化
# ---------------------------------------------------------------------------


def test_reviewer_high_risk_prompt():
    """
    risk_level="high" のとき、プロンプトに 3倍ペナルティが含まれることを確認する。
    """
    from app.services.reviewer import _build_system_prompt

    prompt = _build_system_prompt("high")
    assert "3" in prompt or "3.0" in prompt or "3x" in prompt


def test_reviewer_low_risk_prompt():
    """
    risk_level="low" のとき、プロンプトに 1倍（標準）ペナルティが含まれることを確認する。
    """
    from app.services.reviewer import _build_system_prompt

    prompt = _build_system_prompt("low")
    assert "1" in prompt or "1.0" in prompt or "1x" in prompt


def test_reviewer_high_risk_weight():
    """risk_level="high" の重みが 3.0 であることを確認する。"""
    from app.services.reviewer import _RISK_WEIGHT

    assert _RISK_WEIGHT["high"] == pytest.approx(3.0)


def test_reviewer_medium_risk_weight():
    """risk_level="medium" の重みが 2.0 であることを確認する。"""
    from app.services.reviewer import _RISK_WEIGHT

    assert _RISK_WEIGHT["medium"] == pytest.approx(2.0)


def test_reviewer_low_risk_weight():
    """risk_level="low" の重みが 1.0 であることを確認する。"""
    from app.services.reviewer import _RISK_WEIGHT

    assert _RISK_WEIGHT["low"] == pytest.approx(1.0)
