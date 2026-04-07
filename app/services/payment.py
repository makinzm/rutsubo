"""
報酬分配サービス — スコア比例分配とSolana送金（モック）。

PAYMENT_ENABLED=true の場合は実際の Solana devnet に送金する（将来実装）。
PAYMENT_ENABLED=false（デフォルト）の場合はログのみ。
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
    スコアに比例して budget を分配する。

    - 全スコアが 0 の場合は均等分配
    - PAYMENT_ENABLED=true の場合は Solana devnet に送金（将来実装）
    - PAYMENT_ENABLED=false の場合はログのみ

    Args:
        task_id: タスクID（ログ用）
        scores: {agent_id: score} のマッピング
        wallets: {agent_id: wallet_address} のマッピング
        budget: 分配するSOL/USDC総額

    Returns:
        {agent_id: reward_amount} のマッピング
    """
    if not scores:
        return {}

    total_score = sum(scores.values())

    if total_score == 0.0:
        # 全スコアが0の場合は均等分配
        n = len(scores)
        rewards = {agent_id: budget / n for agent_id in scores}
    else:
        rewards = {
            agent_id: budget * (score / total_score)
            for agent_id, score in scores.items()
        }

    payment_enabled = os.environ.get("PAYMENT_ENABLED", "false").lower() == "true"

    if payment_enabled:
        # 将来実装: x402-solana SDK を使ったdevnet送金
        logger.info(
            "PAYMENT_ENABLED=true: Solana送金（将来実装）task_id=%s rewards=%s",
            task_id,
            rewards,
        )
        # TODO: Solana devnet 送金実装
        # for agent_id, amount in rewards.items():
        #     wallet = wallets.get(agent_id)
        #     await solana_transfer(wallet, amount)
    else:
        logger.info(
            "PAYMENT_ENABLED=false: 送金スキップ（ログのみ）task_id=%s rewards=%s",
            task_id,
            rewards,
        )

    return rewards
