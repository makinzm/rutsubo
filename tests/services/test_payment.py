"""
payment.distribute_rewards tests.

With PAYMENT_ENABLED=false (the default), rewards are only logged and not sent on-chain.
Verifies proportional distribution and equal-split fallback for zero scores.
"""

import asyncio
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# test_distribute_rewards_proportional
# ---------------------------------------------------------------------------


def test_distribute_rewards_proportional():
    """Budget is distributed proportionally to each agent's score."""
    from app.services.payment import distribute_rewards

    scores = {"agent1": 0.8, "agent2": 0.2}
    wallets = {
        "agent1": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "agent2": "Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    }

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.run(
            distribute_rewards(
                task_id="task-001",
                scores=scores,
                wallets=wallets,
                budget=1.0,
            )
        )

    assert rewards["agent1"] == pytest.approx(0.8)
    assert rewards["agent2"] == pytest.approx(0.2)
    assert sum(rewards.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# test_distribute_rewards_zero_scores
# ---------------------------------------------------------------------------


def test_distribute_rewards_zero_scores():
    """When all scores are zero, the budget is split equally among agents."""
    from app.services.payment import distribute_rewards

    scores = {"agent1": 0.0, "agent2": 0.0}
    wallets = {
        "agent1": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "agent2": "Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    }

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.run(
            distribute_rewards(
                task_id="task-002",
                scores=scores,
                wallets=wallets,
                budget=1.0,
            )
        )

    assert rewards["agent1"] == pytest.approx(0.5)
    assert rewards["agent2"] == pytest.approx(0.5)
    assert sum(rewards.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# test_distribute_rewards_single_agent
# ---------------------------------------------------------------------------


def test_distribute_rewards_single_agent():
    """The full budget is assigned to a single agent."""
    from app.services.payment import distribute_rewards

    scores = {"agent1": 0.9}
    wallets = {"agent1": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.run(
            distribute_rewards(
                task_id="task-003",
                scores=scores,
                wallets=wallets,
                budget=0.5,
            )
        )

    assert rewards["agent1"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# test_distribute_rewards_empty
# ---------------------------------------------------------------------------


def test_distribute_rewards_empty():
    """Returns an empty dict when no agents are provided."""
    from app.services.payment import distribute_rewards

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.run(
            distribute_rewards(
                task_id="task-004",
                scores={},
                wallets={},
                budget=1.0,
            )
        )

    assert rewards == {}
