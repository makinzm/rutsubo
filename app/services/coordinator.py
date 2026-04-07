"""
コーディネーターサービス。

役割:
1. Claude APIで難易度・リスクレベルを判定する
2. ε-greedy でエージェントを選択する
3. Claude APIでサブタスクに分解する
4. 各エージェントの endpoint に非同期でサブタスクを送信する
"""

import asyncio
import json
import logging
import random
from typing import Any

import anthropic
import httpx
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.task import SubTask, Task
from app.services import agent_service
from app.services.task_service import update_task_assessment, update_task_status

logger = logging.getLogger(__name__)

# ε-greedy の探索率（将来アニーリング可能な設計にするため定数として定義）
DEFAULT_EPSILON = 0.2
# 最大選択エージェント数
MAX_AGENTS = 3


# ---------------------------------------------------------------------------
# ε-greedy エージェント選択
# ---------------------------------------------------------------------------


def select_agents(agents: list[Agent], epsilon: float = DEFAULT_EPSILON) -> list[Agent]:
    """
    ε-greedy でエージェントを選択する。

    - ε 確率でランダム選択（探索）
    - 1-ε 確率で trust_score 上位から選択（活用）
    - 選択数は min(len(agents), MAX_AGENTS)
    """
    n = min(len(agents), MAX_AGENTS)
    if n == 0:
        return []

    if random.random() < epsilon:
        # 探索: ランダムに n 件選ぶ
        return random.sample(agents, n)
    else:
        # 活用: trust_score 降順で上位 n 件
        return sorted(agents, key=lambda a: a.trust_score, reverse=True)[:n]


# ---------------------------------------------------------------------------
# Claude API — 難易度・リスクレベル判定
# ---------------------------------------------------------------------------


def assess_task(prompt: str) -> dict[str, str]:
    """
    タスクの難易度（difficulty）とリスクレベル（risk_level）を Claude API で判定する。

    Returns:
        {"difficulty": "low"|"medium"|"high", "risk_level": "low"|"medium"|"high"}
    """
    client = anthropic.Anthropic()
    system = (
        "あなたはタスク評価AIです。ユーザーのタスク内容を分析して、"
        "difficulty（low/medium/high）と risk_level（low/medium/high）を"
        "必ずJSON形式のみで返してください。"
        '例: {"difficulty": "medium", "risk_level": "low"}'
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system=system,
        messages=[{"role": "user", "content": f"タスク: {prompt}"}],
    )
    raw = response.content[0].text.strip()
    # JSON部分だけ抽出（余分なテキストがあった場合に備えて）
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # フォールバック
        data = {"difficulty": "medium", "risk_level": "medium"}

    difficulty = data.get("difficulty", "medium")
    risk_level = data.get("risk_level", "medium")
    # 無効な値のフォールバック
    valid = {"low", "medium", "high"}
    if difficulty not in valid:
        difficulty = "medium"
    if risk_level not in valid:
        risk_level = "medium"

    return {"difficulty": difficulty, "risk_level": risk_level}


# ---------------------------------------------------------------------------
# Claude API — サブタスク分解
# ---------------------------------------------------------------------------


def decompose_task(prompt: str, agents: list[Agent]) -> list[dict[str, str]]:
    """
    タスクを各エージェント向けサブタスクに分解する。

    Returns:
        [{"agent_name": "...", "subtask": "..."}, ...]
    """
    client = anthropic.Anthropic()
    agent_profiles = "\n".join(
        f"- {a.name}: {a.description}" for a in agents
    )
    system = (
        "あなたはタスク分解AIです。ユーザーのタスクを、指定されたエージェントそれぞれへのサブタスクに分解してください。"
        "必ずJSON配列のみを返してください。"
        '例: [{"agent_name": "AgentA", "subtask": "..."}]'
    )
    user_message = (
        f"タスク: {prompt}\n\n"
        f"利用可能なエージェント:\n{agent_profiles}"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = response.content[0].text.strip()
    try:
        subtasks = json.loads(raw)
        if not isinstance(subtasks, list):
            raise ValueError("expected list")
    except (json.JSONDecodeError, ValueError):
        # フォールバック: 全エージェントに同じタスクを割り当て
        subtasks = [{"agent_name": a.name, "subtask": prompt} for a in agents]

    return subtasks


# ---------------------------------------------------------------------------
# ワーカーエージェントへの送信
# ---------------------------------------------------------------------------


async def _send_subtask(
    db: Session,
    subtask: SubTask,
    endpoint: str,
    subtask_prompt: str,
) -> None:
    """サブタスクを非同期でエージェントの endpoint に送信する。"""
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            resp = await http_client.post(
                f"{endpoint}/execute",
                json={"subtask": subtask_prompt},
            )
            subtask.result = resp.text
            subtask.status = "completed"
        except Exception as exc:
            logger.warning("Failed to send subtask %s: %s", subtask.subtask_id, exc)
            subtask.result = str(exc)
            subtask.status = "failed"
        finally:
            db.commit()


# ---------------------------------------------------------------------------
# コーディネーターメインフロー
# ---------------------------------------------------------------------------


async def run_coordinator(db: Session, task: Task) -> None:
    """
    タスクを受け取り、難易度判定 → エージェント選択 → サブタスク分解 → 送信 を実行する。
    バックグラウンドタスクとして呼び出されることを想定している。
    """
    try:
        # 1. 難易度・リスクレベル判定
        assessment = assess_task(task.prompt)
        update_task_assessment(
            db, task,
            difficulty=assessment["difficulty"],
            risk_level=assessment["risk_level"],
        )

        # 2. 登録済みエージェントを取得してε-greedy選択
        all_agents = agent_service.list_agents(db)
        selected = select_agents(all_agents, epsilon=DEFAULT_EPSILON)

        # 3. サブタスクに分解
        subtask_defs = decompose_task(task.prompt, selected)

        # agent_name → Agent のマッピング
        agent_map = {a.name: a for a in selected}

        # 4. SubTask レコード作成 + 非同期送信
        send_tasks = []
        for st_def in subtask_defs:
            agent_name = st_def.get("agent_name", "")
            agent = agent_map.get(agent_name)
            if agent is None:
                continue
            subtask = SubTask(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                prompt=st_def.get("subtask", task.prompt),
            )
            db.add(subtask)
            db.commit()
            db.refresh(subtask)
            send_tasks.append(
                _send_subtask(db, subtask, agent.endpoint, subtask.prompt)
            )

        # 非同期で全エージェントに送信
        await asyncio.gather(*send_tasks, return_exceptions=True)

        update_task_status(db, task, "completed")

    except Exception as exc:
        logger.error("Coordinator failed for task %s: %s", task.task_id, exc)
        update_task_status(db, task, "failed")
