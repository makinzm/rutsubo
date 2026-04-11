"""
Reward distribution service — proportional score-based distribution and Solana transfer (mock).

When PAYMENT_ENABLED=true, transfers to the actual Solana devnet (future implementation).
When PAYMENT_ENABLED=false (default), logs only.
"""

import logging
import os

logger = logging.getLogger(__name__)


async def distribute_rewards(
    task_id: str,
    scores: dict[str, float],
    wallets: dict[str, str],
    budget: float,
) -> dict[str, float]:
    """
    Distribute budget proportional to scores.

    - If all scores are 0, distribute equally
    - When PAYMENT_ENABLED=true, transfer to Solana devnet (future implementation)
    - When PAYMENT_ENABLED=false, log only

    Args:
        task_id: Task ID (for logging)
        scores: Mapping of {agent_id: score}
        wallets: Mapping of {agent_id: wallet_address}
        budget: Total SOL/USDC amount to distribute

    Returns:
        Mapping of {agent_id: reward_amount}
    """
    if not scores:
        return {}

    total_score = sum(scores.values())

    if total_score == 0.0:
        # Equal distribution when all scores are 0
        n = len(scores)
        rewards = {agent_id: budget / n for agent_id in scores}
    else:
        rewards = {
            agent_id: budget * (score / total_score)
            for agent_id, score in scores.items()
        }

    payment_enabled = os.environ.get("PAYMENT_ENABLED", "false").lower() == "true"

    if payment_enabled:
        # Future implementation: devnet transfer using the x402-solana SDK
        logger.info(
            "PAYMENT_ENABLED=true: Solana transfer (future implementation) task_id=%s rewards=%s",
            task_id,
            rewards,
        )
        # TODO: Implement Solana devnet transfer
        # for agent_id, amount in rewards.items():
        #     wallet = wallets.get(agent_id)
        #     await solana_transfer(wallet, amount)
    else:
        logger.info(
            "PAYMENT_ENABLED=false: transfer skipped (log only) task_id=%s rewards=%s",
            task_id,
            rewards,
        )

    return rewards
