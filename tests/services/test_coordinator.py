"""
Coordinator service tests — integration flow and epsilon-greedy annealing.

Covers:
- Full coordinator flow: difficulty assessment -> subtask decomposition -> execution -> review -> payment -> trust_score update
- epsilon-greedy annealing (compute_epsilon)
- CausalChainEntry creation after coordinator run

External dependencies (Claude API, httpx) are fully mocked.
DB uses StaticPool in-memory SQLite.
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
from app.models.task import SubTask, Task


# ---------------------------------------------------------------------------
# Test DB setup
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
# Helpers
# ---------------------------------------------------------------------------


def _make_claude_mock(difficulty_resp: str, subtasks_resp: str, review_score: str):
    """Mock Claude API messages.create with sequential side_effect responses."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=difficulty_resp)]),  # assess_task
        MagicMock(content=[MagicMock(text=subtasks_resp)]),    # decompose_task
        MagicMock(content=[MagicMock(text=review_score)]),     # evaluate_subtask
    ]
    return mock_client


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_coordinator_completes_task(db):
    """
    After the full coordinator flow, task.status == 'completed'.

    Flow:
    - 1 agent registered
    - coordinator assesses difficulty -> decomposes subtasks -> dispatches -> reviews -> pays -> updates trust_score
    """
    from app.services.coordinator import run_coordinator

    agent = Agent(
        name="IntegrationAgent",
        description="Agent for integration test",
        wallet_address="Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        endpoint="https://agent-integration.example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    task = Task(
        prompt="integration test task",
        budget=1.0,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    difficulty_resp = '{"difficulty": "medium", "risk_level": "low"}'
    subtasks_resp = json.dumps([{"agent_name": "IntegrationAgent", "subtask": "subtask content"}])
    review_score = '{"score": 0.8}'

    with patch("app.services.llm.complete", side_effect=[
            difficulty_resp, subtasks_resp, review_score
         ]), \
         patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx, \
         patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):

        mock_http_client = AsyncMock()
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(status_code=200, text="subtask execution result")
        )

        asyncio.run(run_coordinator(db, task))

    db.refresh(task)
    assert task.status == "completed"


def test_coordinator_updates_subtask_score(db):
    """After coordinator completes, the SubTask score field is populated."""
    from app.services.coordinator import run_coordinator

    agent = Agent(
        name="ScoreAgent",
        description="Agent for score test",
        wallet_address="Wa11etCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        endpoint="https://agent-score.example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    task = Task(
        prompt="score test task",
        budget=0.5,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    difficulty_resp = '{"difficulty": "low", "risk_level": "low"}'
    subtasks_resp = json.dumps([{"agent_name": "ScoreAgent", "subtask": "score subtask"}])
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
            return_value=MagicMock(status_code=200, text="execution result")
        )

        asyncio.run(run_coordinator(db, task))

    subtasks = db.query(SubTask).filter(SubTask.task_id == task.task_id).all()
    assert len(subtasks) == 1
    assert subtasks[0].score == pytest.approx(0.9)
    assert subtasks[0].reward is not None


# ---------------------------------------------------------------------------
# epsilon-greedy annealing (compute_epsilon)
# ---------------------------------------------------------------------------


def test_epsilon_decreases_with_tasks():
    """Epsilon decreases monotonically as the number of completed tasks increases."""
    from app.services.coordinator import compute_epsilon

    eps_0 = compute_epsilon(0)
    eps_10 = compute_epsilon(10)
    eps_50 = compute_epsilon(50)
    eps_100 = compute_epsilon(100)

    assert eps_0 > eps_10 > eps_50
    assert eps_50 >= eps_100


def test_epsilon_minimum_floor():
    """Epsilon never drops below the minimum floor of 0.05, even at very large task counts."""
    from app.services.coordinator import compute_epsilon

    eps = compute_epsilon(10000)
    assert eps >= 0.05


def test_epsilon_initial_value():
    """At n_tasks=0, epsilon equals the initial value of 0.3."""
    from app.services.coordinator import compute_epsilon

    eps = compute_epsilon(0)
    assert eps == pytest.approx(0.3)


def test_epsilon_formula():
    """epsilon = max(0.05, 0.3 * exp(-0.01 * n)) matches the expected formula."""
    from app.services.coordinator import compute_epsilon

    n = 30
    expected = max(0.05, 0.3 * math.exp(-0.01 * n))
    assert compute_epsilon(n) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# Causal chain entry creation
# ---------------------------------------------------------------------------


def test_causal_chain_entries_created(db):
    """
    After coordinator completes a task, CausalChainEntry rows are persisted to the DB.
    At minimum one 'worker' layer entry must be present.
    """
    from app.models.causal_chain import CausalChainEntry
    from app.services.coordinator import run_coordinator

    agent = Agent(
        name="CausalAgent",
        description="Agent for causal chain test",
        wallet_address="Wa11etCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        endpoint="https://causal-agent.example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    task = Task(
        prompt="causal chain test task",
        budget=1.0,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    difficulty_resp = '{"difficulty": "medium", "risk_level": "medium"}'
    subtasks_resp = json.dumps([{"agent_name": "CausalAgent", "subtask": "subtask"}])
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
            return_value=MagicMock(status_code=200, text="execution result")
        )

        asyncio.run(run_coordinator(db, task))

    entries = db.query(CausalChainEntry).filter(
        CausalChainEntry.task_id == task.task_id
    ).all()
    assert len(entries) > 0
    # At least one 'worker' layer entry must exist
    worker_entries = [e for e in entries if e.layer == "worker"]
    assert len(worker_entries) > 0
    assert worker_entries[0].score is not None
