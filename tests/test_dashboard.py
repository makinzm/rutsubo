"""
ダッシュボードAPIのテスト。

GET /dashboard/agents — 全エージェントの信頼スコア・報酬履歴集計
GET /dashboard/agents/{agent_id} — 特定エージェントの詳細
GET /dashboard/tasks — タスク一覧＋因果連鎖サマリー
"""

import pytest
from fastapi.testclient import TestClient

from app.db.database import Base
from app.models.agent import Agent
from app.models.causal_chain import CausalChainEntry
from app.models.task import SubTask, Task
from tests.conftest import TestingSessionLocal, test_engine


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_agent(db, *, name="TestAgent", trust_score=0.5):
    agent = Agent(
        name=name,
        description="Test agent",
        wallet_address="So11111111111111111111111111111111111111112",
        endpoint="http://localhost:9999",
        trust_score=trust_score,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _make_task(db, *, prompt="test task", budget=0.1, status="completed"):
    task = Task(prompt=prompt, budget=budget, status=status)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _make_subtask(db, *, task_id, agent_id, score=None, reward=None, status="completed"):
    subtask = SubTask(
        task_id=task_id,
        agent_id=agent_id,
        prompt="subtask prompt",
        status=status,
        result="result text",
        score=score,
        reward=reward,
    )
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return subtask


# ---------------------------------------------------------------------------
# GET /dashboard/agents
# ---------------------------------------------------------------------------


def test_dashboard_agents_empty(client):
    """エージェント0件のとき 200 で空配列を返す。"""
    resp = client.get("/dashboard/agents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_agents_with_data(client):
    """エージェント・タスク・サブタスクがあるとき集計値が正しい。"""
    db = TestingSessionLocal()
    try:
        agent = _make_agent(db, name="HighQualityAgent", trust_score=0.82)
        task = _make_task(db, status="completed")
        _make_subtask(db, task_id=task.task_id, agent_id=agent.agent_id, score=0.9, reward=0.05)
    finally:
        db.close()

    resp = client.get("/dashboard/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["agent_id"] == agent.agent_id
    assert item["name"] == "HighQualityAgent"
    assert abs(item["trust_score"] - 0.82) < 1e-6
    assert item["total_tasks"] == 1
    assert abs(item["total_reward"] - 0.05) < 1e-6
    assert abs(item["avg_score"] - 0.9) < 1e-6
    assert len(item["task_history"]) == 1
    history = item["task_history"][0]
    assert history["task_id"] == task.task_id
    assert abs(history["score"] - 0.9) < 1e-6
    assert abs(history["reward"] - 0.05) < 1e-6


def test_dashboard_agents_multiple_subtasks(client):
    """複数サブタスクがあるとき avg_score と total_reward が正しく集計される。"""
    db = TestingSessionLocal()
    try:
        agent = _make_agent(db, name="AgentA", trust_score=0.7)
        task1 = _make_task(db, status="completed")
        task2 = _make_task(db, status="completed")
        _make_subtask(db, task_id=task1.task_id, agent_id=agent.agent_id, score=0.8, reward=0.04)
        _make_subtask(db, task_id=task2.task_id, agent_id=agent.agent_id, score=0.6, reward=0.02)
    finally:
        db.close()

    resp = client.get("/dashboard/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["total_tasks"] == 2
    assert abs(item["total_reward"] - 0.06) < 1e-6
    assert abs(item["avg_score"] - 0.7) < 1e-6  # (0.8 + 0.6) / 2


# ---------------------------------------------------------------------------
# GET /dashboard/agents/{agent_id}
# ---------------------------------------------------------------------------


def test_dashboard_agent_detail(client):
    """特定エージェントの詳細が取得できる。"""
    db = TestingSessionLocal()
    try:
        agent = _make_agent(db, name="DetailAgent", trust_score=0.75)
        task = _make_task(db, status="completed")
        _make_subtask(db, task_id=task.task_id, agent_id=agent.agent_id, score=0.85, reward=0.03)
        agent_id = agent.agent_id
    finally:
        db.close()

    resp = client.get(f"/dashboard/agents/{agent_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent_id
    assert data["name"] == "DetailAgent"
    assert abs(data["trust_score"] - 0.75) < 1e-6
    assert data["total_tasks"] == 1
    assert len(data["task_history"]) == 1


def test_dashboard_agent_not_found(client):
    """存在しないagent_idで 404 を返す。"""
    resp = client.get("/dashboard/agents/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /dashboard/tasks
# ---------------------------------------------------------------------------


def test_dashboard_tasks_empty(client):
    """タスク0件のとき 200 で空配列を返す。"""
    resp = client.get("/dashboard/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_tasks(client):
    """タスク一覧が取得できる。各タスクにstatus・causal_chain_countが含まれる。"""
    db = TestingSessionLocal()
    try:
        task1 = _make_task(db, prompt="task one", status="completed")
        task2 = _make_task(db, prompt="task two", status="pending")
        # task1 に因果連鎖エントリを2件追加
        entry1 = CausalChainEntry(task_id=task1.task_id, layer="worker", score=0.8)
        entry2 = CausalChainEntry(task_id=task1.task_id, layer="coordinator", score=0.9)
        db.add(entry1)
        db.add(entry2)
        db.commit()
        task1_id = task1.task_id
        task2_id = task2.task_id
    finally:
        db.close()

    resp = client.get("/dashboard/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_id = {item["task_id"]: item for item in data}
    assert by_id[task1_id]["status"] == "completed"
    assert by_id[task1_id]["causal_chain_count"] == 2
    assert by_id[task2_id]["status"] == "pending"
    assert by_id[task2_id]["causal_chain_count"] == 0
