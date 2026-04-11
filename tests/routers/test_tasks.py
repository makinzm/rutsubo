"""
Task submission and coordinator API tests.

Each test runs in an independent in-memory SQLite session.
External calls (Claude API, httpx) are mocked with unittest.mock.

Also covers causal-chain API endpoints (from Week 3 differentiators).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(client, *, name="AgentA", wallet="Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", endpoint="https://agent-a.example.com"):
    return client.post("/agents/register", json={
        "name": name,
        "description": f"{name} description",
        "wallet_address": wallet,
        "endpoint": endpoint,
    }).json()


def _mock_claude_difficulty():
    """Return a MagicMock response for difficulty assessment."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text='{"difficulty": "medium", "risk_level": "low"}')]
    return mock_resp


def _mock_claude_subtasks(agent_names: list[str]):
    """Return a MagicMock response for subtask decomposition."""
    import json
    subtasks = [{"agent_name": name, "subtask": f"subtask for {name}"} for name in agent_names]
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(subtasks))]
    return mock_resp


# ---------------------------------------------------------------------------
# POST /tasks
# ---------------------------------------------------------------------------


def test_create_task_success(client):
    """A valid payload creates a task and returns 201 with task info."""
    _make_agent(client)

    import json as _json
    subtasks_json = _json.dumps([{"agent_name": "AgentA", "subtask": "subtask for AgentA"}])
    with patch("app.services.llm.complete", side_effect=[
            '{"difficulty": "medium", "risk_level": "low"}',
            subtasks_json,
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx:
        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200, text="done"))

        response = client.post("/tasks", json={"prompt": "test task", "budget": 0.1})

    assert response.status_code == 201
    data = response.json()
    assert "task_id" in data
    assert data["prompt"] == "test task"
    assert data["budget"] == 0.1
    # Coordinator runs in background, so status is pending at response time
    assert data["status"] == "pending"
    assert "difficulty" in data
    assert "risk_level" in data
    assert "created_at" in data


def test_create_task_no_agents(client):
    """Returns 400 Bad Request when no agents are registered."""
    with patch("app.services.llm.complete", return_value='{"difficulty": "medium", "risk_level": "low"}'):
        response = client.post("/tasks", json={"prompt": "task", "budget": 0.05})

    assert response.status_code == 400


def test_create_task_missing_prompt(client):
    """Returns 422 when prompt is missing."""
    response = client.post("/tasks", json={"budget": 0.1})

    assert response.status_code == 422


def test_create_task_invalid_budget_negative(client):
    """Returns 422 when budget is negative."""
    response = client.post("/tasks", json={"prompt": "test", "budget": -0.1})

    assert response.status_code == 422


def test_create_task_invalid_budget_zero(client):
    """Returns 422 when budget is zero."""
    response = client.post("/tasks", json={"prompt": "test", "budget": 0.0})

    assert response.status_code == 422


def test_create_task_empty_prompt(client):
    """Returns 422 when prompt is an empty string."""
    response = client.post("/tasks", json={"prompt": "", "budget": 0.1})

    assert response.status_code == 422


def test_create_task_triggers_coordinator(client):
    """Confirms the coordinator background task is triggered after task creation."""
    _make_agent(client)

    with patch("app.routers.tasks._run_coordinator_sync") as mock_coordinator:
        response = client.post("/tasks", json={"prompt": "coordinator trigger test", "budget": 0.2})

    assert response.status_code == 201
    mock_coordinator.assert_called_once()


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------


def test_get_task_success(client):
    """Returns 200 and correct task info for an existing task_id."""
    _make_agent(client)

    import json as _json
    subtasks_json = _json.dumps([{"agent_name": "AgentA", "subtask": "subtask for AgentA"}])
    with patch("app.services.llm.complete", side_effect=[
            '{"difficulty": "medium", "risk_level": "low"}',
            subtasks_json,
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx:
        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200, text="done"))

        created = client.post("/tasks", json={"prompt": "retrieval test", "budget": 0.1}).json()

    task_id = created["task_id"]
    response = client.get(f"/tasks/{task_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["prompt"] == "retrieval test"


def test_get_task_not_found(client):
    """Returns 404 for a non-existent task_id."""
    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Coordinator unit tests (epsilon-greedy selection)
# ---------------------------------------------------------------------------


def test_select_agents_exploit():
    """With epsilon=0 the top 3 agents by trust_score are selected."""
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
    # Top 3 by trust_score: a1=0.9, a3=0.7, a2=0.5
    assert selected_ids == {"a1", "a3", "a2"}


def test_select_agents_explore():
    """With epsilon=1.0 agents are selected randomly (not limited to top 3)."""
    from app.services.coordinator import select_agents

    agents = [
        MagicMock(agent_id="a1", trust_score=0.9),
        MagicMock(agent_id="a2", trust_score=0.9),
        MagicMock(agent_id="a3", trust_score=0.9),
        MagicMock(agent_id="a4", trust_score=0.0),  # would never be chosen by exploit
    ]
    # With epsilon=1.0, run many trials to confirm low-score agent can be selected
    selected_ids_set = set()
    for _ in range(50):
        selected = select_agents(agents, epsilon=1.0)
        for a in selected:
            selected_ids_set.add(a.agent_id)

    assert "a4" in selected_ids_set, "With epsilon=1.0 low-score agents should be reachable"


def test_select_agents_less_than_3():
    """When fewer than 3 agents are registered, all of them are selected."""
    from app.services.coordinator import select_agents

    agents = [
        MagicMock(agent_id="a1", trust_score=0.8),
        MagicMock(agent_id="a2", trust_score=0.6),
    ]
    selected = select_agents(agents, epsilon=0.0)

    assert len(selected) == 2


# ---------------------------------------------------------------------------
# Causal-chain API endpoints (Week 3)
# ---------------------------------------------------------------------------


def test_get_causal_chain_api(client):
    """
    GET /tasks/{task_id}/causal-chain returns 200 for an existing task.
    Returns an empty list when no CausalChainEntry rows exist yet.
    """
    client.post("/agents/register", json={
        "name": "CausalAPIAgent",
        "description": "API test agent",
        "wallet_address": "Wa11etDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
        "endpoint": "https://causal-api-agent.example.com",
    })

    with patch("app.routers.tasks.run_coordinator"):
        resp = client.post("/tasks", json={"prompt": "test task", "budget": 0.5})
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    causal_resp = client.get(f"/tasks/{task_id}/causal-chain")
    assert causal_resp.status_code == 200
    data = causal_resp.json()
    assert isinstance(data, list)


def test_causal_chain_not_found(client):
    """GET /tasks/{task_id}/causal-chain returns 404 for a non-existent task_id."""
    resp = client.get("/tasks/nonexistent-task-id/causal-chain")
    assert resp.status_code == 404
