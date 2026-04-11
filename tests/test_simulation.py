"""
Simulator tests.

test_simulation_registers_agents  — agents are registered after a simulation run
test_simulation_output_format     — output JSON contains the 'learning_curve' key
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers — Claude API mock responses
# ---------------------------------------------------------------------------


def _make_claude_assess_response(difficulty="medium", risk_level="medium"):
    """Mock Claude API response for assess_task."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]
    mock_resp.content[0].text = json.dumps(
        {"difficulty": difficulty, "risk_level": risk_level}
    )
    return mock_resp


def _make_claude_decompose_response(agent_names: list[str], subtask: str = "do the task"):
    """Mock Claude API response for decompose_task."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]
    mock_resp.content[0].text = json.dumps(
        [{"agent_name": name, "subtask": subtask} for name in agent_names]
    )
    return mock_resp


def _make_claude_review_response(score: float = 0.7):
    """Mock Claude API response for evaluate_subtask."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]
    mock_resp.content[0].text = json.dumps({"score": score, "reason": "mock review"})
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_simulation_registers_agents(tmp_path):
    """After a simulation run, exactly 4 agents are registered in the DB."""
    from app.db.database import Base
    from tests.conftest import TestingSessionLocal, test_engine

    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    output_file = str(tmp_path / "simulation_result.json")

    with patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch("httpx.AsyncClient") as mock_httpx_cls:

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_claude_assess_response(),
            _make_claude_decompose_response(["HighQualityAgent"]),
            _make_claude_review_response(0.9),
        ] * 20  # enough for 20 tasks

        mock_http_instance = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_response = MagicMock()
        mock_http_response.text = "mock result"
        mock_http_instance.post = AsyncMock(return_value=mock_http_response)

        from app.simulation import run_simulation_sync
        run_simulation_sync(db=db, n_tasks=1, output_file=output_file)

    from app.models.agent import Agent
    agents = db.query(Agent).all()
    agent_names = {a.name for a in agents}

    db.close()
    Base.metadata.drop_all(bind=test_engine)

    assert len(agents) == 4
    assert "HighQualityAgent" in agent_names
    assert "MediumAgent" in agent_names
    assert "PoorAgent" in agent_names
    assert "NewAgent" in agent_names


def test_simulation_output_format(tmp_path):
    """The simulation output JSON contains a 'learning_curve' key with the expected structure."""
    from app.db.database import Base
    from tests.conftest import TestingSessionLocal, test_engine

    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    output_file = str(tmp_path / "simulation_result.json")

    with patch("anthropic.Anthropic") as mock_anthropic_cls, \
         patch("httpx.AsyncClient") as mock_httpx_cls:

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_claude_assess_response(),
            _make_claude_decompose_response(["HighQualityAgent", "MediumAgent"]),
            _make_claude_review_response(0.8),
            _make_claude_review_response(0.6),
        ] * 10

        mock_http_instance = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http_response = MagicMock()
        mock_http_response.text = "mock result"
        mock_http_instance.post = AsyncMock(return_value=mock_http_response)

        from app.simulation import run_simulation_sync
        run_simulation_sync(db=db, n_tasks=2, output_file=output_file)

    db.close()
    Base.metadata.drop_all(bind=test_engine)

    assert os.path.exists(output_file)
    with open(output_file) as f:
        result = json.load(f)

    assert "learning_curve" in result
    assert isinstance(result["learning_curve"], list)
    # Each learning_curve entry must contain task_index and agent trust scores
    for entry in result["learning_curve"]:
        assert "task_index" in entry
        assert "agent_trust_scores" in entry
