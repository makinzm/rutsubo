"""
タスク投入・コーディネーター API のテスト。

各テストは独立したインメモリ SQLite セッションで実行される。
Claude API および httpx への外部呼び出しは unittest.mock でモックする。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_agent(client, *, name="AgentA", wallet="Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", endpoint="https://agent-a.example.com"):
    return client.post("/agents/register", json={
        "name": name,
        "description": f"{name}の説明",
        "wallet_address": wallet,
        "endpoint": endpoint,
    }).json()


def _mock_claude_difficulty():
    """難易度判定のモックレスポンスを返すMagicMock。"""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text='{"difficulty": "medium", "risk_level": "low"}')]
    return mock_resp


def _mock_claude_subtasks(agent_names: list[str]):
    """サブタスク分解のモックレスポンスを返すMagicMock。"""
    import json
    subtasks = [{"agent_name": name, "subtask": f"{name}へのサブタスク"} for name in agent_names]
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(subtasks))]
    return mock_resp


# ---------------------------------------------------------------------------
# POST /tasks
# ---------------------------------------------------------------------------


def test_create_task_success(client):
    """正常なデータでタスクを作成すると 201 と task 情報を返す。"""
    _make_agent(client)

    import json as _json
    subtasks_json = _json.dumps([{"agent_name": "AgentA", "subtask": "AgentAへのサブタスク"}])
    with patch("app.services.llm.complete", side_effect=[
            '{"difficulty": "medium", "risk_level": "low"}',
            subtasks_json,
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx:
        # httpx のモック設定（非同期）
        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200, text="done"))

        response = client.post("/tasks", json={"prompt": "テストタスク", "budget": 0.1})

    assert response.status_code == 201
    data = response.json()
    assert "task_id" in data
    assert data["prompt"] == "テストタスク"
    assert data["budget"] == 0.1
    # コーディネーターはバックグラウンド実行のため、レスポンス時点では pending / None が正常
    assert data["status"] == "pending"
    assert "difficulty" in data
    assert "risk_level" in data
    assert "created_at" in data


def test_create_task_no_agents(client):
    """エージェントが0件のとき 400 Bad Request を返す。"""
    with patch("app.services.llm.complete", return_value='{"difficulty": "medium", "risk_level": "low"}'):
        response = client.post("/tasks", json={"prompt": "タスク", "budget": 0.05})

    assert response.status_code == 400


def test_create_task_missing_prompt(client):
    """prompt が欠落している場合は 422 を返す。"""
    response = client.post("/tasks", json={"budget": 0.1})

    assert response.status_code == 422


def test_create_task_invalid_budget_negative(client):
    """budget が負の場合は 422 を返す。"""
    response = client.post("/tasks", json={"prompt": "テスト", "budget": -0.1})

    assert response.status_code == 422


def test_create_task_invalid_budget_zero(client):
    """budget が 0 の場合は 422 を返す。"""
    response = client.post("/tasks", json={"prompt": "テスト", "budget": 0.0})

    assert response.status_code == 422


def test_create_task_empty_prompt(client):
    """prompt が空文字の場合は 422 を返す。"""
    response = client.post("/tasks", json={"prompt": "", "budget": 0.1})

    assert response.status_code == 422


def test_create_task_triggers_coordinator(client):
    """タスク作成後にコーディネーターのバックグラウンドタスクが起動することを確認する。"""
    _make_agent(client)

    # バックグラウンドタスクのラッパー関数をモックして、起動されたことだけ確認する
    with patch("app.routers.tasks._run_coordinator_sync") as mock_coordinator:
        response = client.post("/tasks", json={"prompt": "コーディネーターのテスト", "budget": 0.2})

    assert response.status_code == 201
    # コーディネーターが1回起動された
    mock_coordinator.assert_called_once()


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------


def test_get_task_success(client):
    """存在する task_id でタスクを取得すると 200 と正しい情報を返す。"""
    _make_agent(client)

    import json as _json
    subtasks_json = _json.dumps([{"agent_name": "AgentA", "subtask": "AgentAへのサブタスク"}])
    with patch("app.services.llm.complete", side_effect=[
            '{"difficulty": "medium", "risk_level": "low"}',
            subtasks_json,
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx:
        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200, text="done"))

        created = client.post("/tasks", json={"prompt": "取得テスト", "budget": 0.1}).json()

    task_id = created["task_id"]
    response = client.get(f"/tasks/{task_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["prompt"] == "取得テスト"


def test_get_task_not_found(client):
    """存在しない task_id で取得すると 404 を返す。"""
    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# コーディネーター ユニットテスト（ε-greedy選択）
# ---------------------------------------------------------------------------


def test_select_agents_exploit():
    """ε=0のとき trust_score 上位3件が選択される。"""
    from app.services.coordinator import select_agents

    agents = [
        MagicMock(agent_id="a1", trust_score=0.9),
        MagicMock(agent_id="a2", trust_score=0.5),
        MagicMock(agent_id="a3", trust_score=0.7),
        MagicMock(agent_id="a4", trust_score=0.3),
    ]
    selected = select_agents(agents, epsilon=0.0)

    assert len(selected) == 3
    selected_ids = {a.agent_id for a in selected}
    # trust_score 上位3件（a1=0.9, a3=0.7, a2=0.5）が選ばれるはず
    assert selected_ids == {"a1", "a3", "a2"}


def test_select_agents_explore():
    """ε=1.0のとき全エージェントからランダム選択される（上位3に限定されない）。"""
    from app.services.coordinator import select_agents

    # trust_score を極端に設定して、活用なら必ず上位3になるようにする
    agents = [
        MagicMock(agent_id="a1", trust_score=0.9),
        MagicMock(agent_id="a2", trust_score=0.9),
        MagicMock(agent_id="a3", trust_score=0.9),
        MagicMock(agent_id="a4", trust_score=0.0),  # 活用なら絶対選ばれない
    ]
    # ε=1.0 で何度か試して a4 が選ばれることを確認（確率的テスト）
    selected_ids_set = set()
    for _ in range(50):
        selected = select_agents(agents, epsilon=1.0)
        for a in selected:
            selected_ids_set.add(a.agent_id)

    assert "a4" in selected_ids_set, "ε=1.0 のとき低スコアエージェントも選ばれるはず"


def test_select_agents_less_than_3():
    """登録エージェントが3件未満のとき、全件選択される。"""
    from app.services.coordinator import select_agents

    agents = [
        MagicMock(agent_id="a1", trust_score=0.8),
        MagicMock(agent_id="a2", trust_score=0.6),
    ]
    selected = select_agents(agents, epsilon=0.0)

    assert len(selected) == 2
