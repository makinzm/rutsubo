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

# risk_level ごとの重み付け（タスクのリスクレベルに応じた非対称損失の倍率）
# - high: 見逃しペナルティを3倍重くする
# - medium: 見逃しペナルティを2倍重くする
# - low: 標準（1倍）
_RISK_WEIGHT = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
}


def _build_system_prompt(risk_level: str) -> str:
    """
    risk_level に応じた評価プロンプトを生成する。

    非対称損失関数のパラメータをプロンプトに組み込み、
    LLM評価者がリスクレベルを考慮した採点を行えるようにする。

    Args:
        risk_level: タスクのリスクレベル（low/medium/high）

    Returns:
        システムプロンプト文字列
    """
    risk = risk_level if risk_level in _RISK_WEIGHT else "medium"
    risk_weight = _RISK_WEIGHT[risk]

    return (
        "あなたはタスク品質評価AIです。ワーカーエージェントのサブタスク実行結果を評価してください。\n\n"
        "【評価基準】\n"
        "- タスクの要件を満たしているか\n"
        "- 結果の品質・正確性\n"
        "- 重要な問題の見落としがないか（見逃しは重大なペナルティ）\n\n"
        "【非対称損失原則】\n"
        f"現在のリスクレベル: {risk}（見逃しペナルティ倍率: {risk_weight}x）\n"
        "- 重要な問題を見逃した場合: 非線形に重いペナルティ（スコアを大幅に下げる）\n"
        f"  ※ リスクレベル {risk} では見逃しを {risk_weight}x 倍重く扱う\n"
        "- 過検出（問題なしを問題ありと判定）: 軽微なペナルティ\n\n"
        "必ずJSON形式のみで返してください。\n"
        '例: {"score": 0.85, "reason": "要件を概ね満たしているが軽微な問題あり"}'
    )


async def evaluate_subtask(prompt: str, result: str, risk_level: str = "medium") -> float:
    """
    サブタスクの結果を Claude API で評価し、0.0〜1.0 のスコアを返す。

    非対称損失関数の考慮:
    - risk_level が high のとき、見逃し（重要問題の看過）は3倍のペナルティ
    - risk_level が medium のとき、見逃しは2倍のペナルティ
    - risk_level が low のとき、標準（1倍）
    - 過検出（問題なしを問題ありと判定）は比較的軽い扱い

    Args:
        prompt: サブタスクの内容（何を達成すべきか）
        result: ワーカーエージェントが返した結果テキスト
        risk_level: タスクのリスクレベル（low/medium/high）

    Returns:
        0.0〜1.0 のスコア（1.0が最高品質）
    """
    client = anthropic.Anthropic()
    system = _build_system_prompt(risk_level)
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
