"""
payment.distribute_rewards のテスト。

PAYMENT_ENABLED=false（デフォルト）ではログのみ。
スコア比例分配・ゼロスコア均等分配を検証する。
"""

import asyncio
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# test_distribute_rewards_proportional
# ---------------------------------------------------------------------------


def test_distribute_rewards_proportional():
    """スコアに比例してbudgetが分配されることを確認する。"""
    from app.services.payment import distribute_rewards

    scores = {"agent1": 0.8, "agent2": 0.2}
    wallets = {
        "agent1": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "agent2": "Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    }

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.get_event_loop().run_until_complete(
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
    """全スコアが0の場合は均等分配されることを確認する。"""
    from app.services.payment import distribute_rewards

    scores = {"agent1": 0.0, "agent2": 0.0}
    wallets = {
        "agent1": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "agent2": "Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    }

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.get_event_loop().run_until_complete(
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
    """エージェント1件の場合はbudget全額が割り当てられる。"""
    from app.services.payment import distribute_rewards

    scores = {"agent1": 0.9}
    wallets = {"agent1": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.get_event_loop().run_until_complete(
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
    """エージェントが空の場合は空dictを返す。"""
    from app.services.payment import distribute_rewards

    with patch.dict(os.environ, {"PAYMENT_ENABLED": "false"}):
        rewards = asyncio.get_event_loop().run_until_complete(
            distribute_rewards(
                task_id="task-004",
                scores={},
                wallets={},
                budget=1.0,
            )
        )

    assert rewards == {}
