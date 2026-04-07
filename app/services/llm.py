"""
LLMクライアント抽象化レイヤー。

LLM_BACKEND 環境変数で実装を切り替える:
  - "api"  : anthropic SDK（ANTHROPIC_API_KEY 必要）
  - "cli"  : claude CLI サブプロセス（Claude Code の認証をそのまま利用）
  - "mock" : モックレスポンス（テスト・シミュレーション用）
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

LLM_BACKEND = os.getenv("LLM_BACKEND", "api")


def complete(system: str, user: str, max_tokens: int = 500) -> str:
    """
    LLMにメッセージを送り、レスポンスのテキストを返す。

    Args:
        system: システムプロンプト
        user: ユーザーメッセージ
        max_tokens: 最大トークン数（api バックエンドのみ有効）

    Returns:
        LLMのレスポンステキスト
    """
    backend = LLM_BACKEND

    if backend == "cli":
        return _complete_cli(system, user)
    elif backend == "mock":
        return _complete_mock(system, user)
    else:
        return _complete_api(system, user, max_tokens)


def _complete_api(system: str, user: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def _complete_cli(system: str, user: str) -> str:
    """claude CLIサブプロセス経由でレスポンスを取得する。"""
    prompt = f"{system}\n\n{user}"
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI error: {result.stderr.strip()}")
    return result.stdout.strip()


def _complete_mock(system: str, user: str) -> str:
    """
    モックレスポンスを返す（テスト・シミュレーション用）。

    システムプロンプトの内容からタスク種別を判定して適切なJSONを返す。
    結果テキストに "QUALITY:<float>" タグが含まれる場合はその値をスコアとして使用する。
    """
    import re
    if "difficulty" in system and "risk_level" in system:
        # 難易度・リスク判定
        return json.dumps({"difficulty": "medium", "risk_level": "low"})
    elif "agent_name" in system or "サブタスクに分解" in system:
        # サブタスク分解（ユーザーメッセージからエージェント名を抽出）
        agents = []
        for line in user.split("\n"):
            if line.startswith("- ") and ":" in line:
                name = line[2:].split(":")[0].strip()
                agents.append({"agent_name": name, "subtask": f"Subtask for {name}: {user[:50]}"})
        return json.dumps(agents if agents else [])
    elif "score" in system or "品質評価" in system:
        # サブタスク評価 — 結果テキストに品質タグがあればそれを使用
        quality_match = re.search(r"QUALITY:([\d.]+)", user)
        score = float(quality_match.group(1)) if quality_match else 0.75
        return json.dumps({"score": score, "reason": "mock evaluation"})
    else:
        return json.dumps({"result": "mock response"})
