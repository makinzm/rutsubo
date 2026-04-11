"""
Reviewer service and agent_service.update_trust_score tests.

Also covers asymmetric loss function risk weight parameterization (Week 3).

External dependencies (Claude API) are mocked with unittest.mock.
DB uses StaticPool in-memory SQLite.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.agent import Agent


# ---------------------------------------------------------------------------
# Test DB setup (local, independent from conftest.py)
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
# evaluate_subtask
# ---------------------------------------------------------------------------


def test_reviewer_returns_score():
    """evaluate_subtask returns a float score when the Claude API is mocked."""
    from app.services.reviewer import evaluate_subtask

    with patch("app.services.llm.complete", return_value='{"score": 0.85}'):
        score = asyncio.run(
            evaluate_subtask(
                prompt="Please implement fizzbuzz in Python",
                result="def fizzbuzz(n): ...",
                risk_level="medium",
            )
        )

    assert isinstance(score, float)
    assert score == pytest.approx(0.85)


@pytest.mark.parametrize("raw_score,expected", [
    (0.0, 0.0),
    (1.0, 1.0),
    (0.5, 0.5),
    (-0.1, 0.0),   # clamped to lower bound
    (1.5, 1.0),    # clamped to upper bound
])
def test_reviewer_score_range(raw_score, expected):
    """Scores returned by the Claude API are clamped to the [0.0, 1.0] range."""
    from app.services.reviewer import evaluate_subtask

    with patch("app.services.llm.complete", return_value=f'{{"score": {raw_score}}}'):
        score = asyncio.run(
            evaluate_subtask(
                prompt="task",
                result="result",
                risk_level="low",
            )
        )

    assert 0.0 <= score <= 1.0
    assert score == pytest.approx(expected)


# ---------------------------------------------------------------------------
# update_trust_score
# ---------------------------------------------------------------------------


def test_update_trust_score(db):
    """Trust score is updated using EMA: new = 0.8 * old + 0.2 * eval_score."""
    from app.services.agent_service import update_trust_score

    agent = Agent(
        name="TestAgent",
        description="Test agent",
        wallet_address="Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        endpoint="https://example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    updated = update_trust_score(db, agent.agent_id, eval_score=1.0)

    # 0.8 * 0.5 + 0.2 * 1.0 = 0.6
    assert updated.trust_score == pytest.approx(0.6)


def test_update_trust_score_decreasing(db):
    """Trust score decreases when eval_score is lower than the current value."""
    from app.services.agent_service import update_trust_score

    agent = Agent(
        name="TestAgent2",
        description="Test agent 2",
        wallet_address="Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        endpoint="https://example2.com",
        trust_score=0.8,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    updated = update_trust_score(db, agent.agent_id, eval_score=0.0)

    # 0.8 * 0.8 + 0.2 * 0.0 = 0.64
    assert updated.trust_score == pytest.approx(0.64)


# ---------------------------------------------------------------------------
# Asymmetric loss function — risk weight parameterization (Week 3)
# ---------------------------------------------------------------------------


def test_reviewer_high_risk_prompt():
    """The system prompt for risk_level='high' contains the 3x penalty factor."""
    from app.services.reviewer import _build_system_prompt

    prompt = _build_system_prompt("high")
    assert "3" in prompt or "3.0" in prompt or "3x" in prompt


def test_reviewer_low_risk_prompt():
    """The system prompt for risk_level='low' contains the standard (1x) penalty factor."""
    from app.services.reviewer import _build_system_prompt

    prompt = _build_system_prompt("low")
    assert "1" in prompt or "1.0" in prompt or "1x" in prompt


def test_reviewer_high_risk_weight():
    """The risk weight for 'high' risk level is 3.0."""
    from app.services.reviewer import _RISK_WEIGHT

    assert _RISK_WEIGHT["high"] == pytest.approx(3.0)


def test_reviewer_medium_risk_weight():
    """The risk weight for 'medium' risk level is 2.0."""
    from app.services.reviewer import _RISK_WEIGHT

    assert _RISK_WEIGHT["medium"] == pytest.approx(2.0)


def test_reviewer_low_risk_weight():
    """The risk weight for 'low' risk level is 1.0."""
    from app.services.reviewer import _RISK_WEIGHT

    assert _RISK_WEIGHT["low"] == pytest.approx(1.0)
