"""
レビュアーサービス — LLM-as-a-Judge によるサブタスク評価。

非対称損失関数を考慮したプロンプト設計:
- 見逃し（重要な問題を看過）は非線形に重いペナルティ → 厳しめに評価する
- 過検出（問題なしを問題ありと判定）は軽微なペナルティ
"""

import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_CLAUDE_MODEL = "claude-sonnet-4-6"

# risk_level ごとの重み付け（高リスクほど見逃しを厳しく扱う）
_RISK_WEIGHT = {
    "low": 1.0,
    "medium": 1.5,
    "high": 2.0,
}


async def evaluate_subtask(prompt: str, result: str, risk_level: str = "medium") -> float:
    """
    サブタスクの結果を Claude API で評価し、0.0〜1.0 のスコアを返す。

    非対称損失関数の考慮:
    - risk_level が high のとき、見逃し（重要問題の看過）はより重くペナルティを受ける
    - 過検出（問題なしを問題ありと判定）は比較的軽い扱い

    Args:
        prompt: サブタスクの内容（何を達成すべきか）
        result: ワーカーエージェントが返した結果テキスト
        risk_level: タスクのリスクレベル（low/medium/high）

    Returns:
        0.0〜1.0 のスコア（1.0が最高品質）
    """
    risk = risk_level if risk_level in _RISK_WEIGHT else "medium"
    risk_weight = _RISK_WEIGHT[risk]

    client = anthropic.Anthropic()
    system = (
        "あなたはタスク品質評価AIです。ワーカーエージェントのサブタスク実行結果を評価してください。\n\n"
        "【評価基準】\n"
        "- タスクの要件を満たしているか\n"
        "- 結果の品質・正確性\n"
        "- 重要な問題の見落としがないか（見逃しは重大なペナルティ）\n\n"
        "【非対称損失原則】\n"
        f"現在のリスクレベル: {risk}（重み: {risk_weight}x）\n"
        "- 重要な問題を見逃した場合: 非線形に重いペナルティ（スコアを大幅に下げる）\n"
        "- 過検出（問題なしを問題ありと判定）: 軽微なペナルティ\n\n"
        "必ずJSON形式のみで返してください。\n"
        '例: {"score": 0.85, "reason": "要件を概ね満たしているが軽微な問題あり"}'
    )
    user_message = (
        f"【サブタスク】\n{prompt}\n\n"
        f"【実行結果】\n{result}"
    )

    try:
        response = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        data = json.loads(raw)
        score = float(data.get("score", 0.5))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning("Failed to parse reviewer response: %s", exc)
        score = 0.5  # パース失敗時はデフォルト

    # 0.0〜1.0 にクランプ
    return max(0.0, min(1.0, score))
