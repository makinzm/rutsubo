"""
コーディネーターサービス。

役割:
1. Claude APIで難易度・リスクレベルを判定する
2. ε-greedy（焼きなまし）でエージェントを選択する
3. Claude APIでサブタスクに分解する
4. 各エージェントの endpoint に非同期でサブタスクを送信する
5. 評価結果を因果連鎖エントリとして記録する
"""

import asyncio
import json
import logging
import math
import random

import httpx
from sqlalchemy.orm import Session

from app.config import EPSILON_INITIAL, EPSILON_LAMBDA, EPSILON_MIN
from app.services import llm as _llm
from app.models.agent import Agent
from app.models.causal_chain import CausalChainEntry
from app.models.task import SubTask, Task
from app.services import agent_service
from app.services.payment import distribute_rewards
from app.services.reviewer import evaluate_subtask
from app.services.task_service import update_task_assessment, update_task_status

logger = logging.getLogger(__name__)

# 最大選択エージェント数
MAX_AGENTS = 3
# 難易度・リスクレベルの有効値
_VALID_LEVELS = {"low", "medium", "high"}
# Claude API モデル名
_CLAUDE_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# ε-greedy 焼きなまし
# ---------------------------------------------------------------------------


def compute_epsilon(n_tasks: int) -> float:
    """
    完了タスク数に基づいてεを計算する（焼きなまし）。

    ε = max(EPSILON_MIN, EPSILON_INITIAL * exp(-EPSILON_LAMBDA * n_tasks))

    Args:
        n_tasks: これまでの完了タスク数

    Returns:
        0.05〜EPSILON_INITIAL の範囲のε値
    """
    eps = EPSILON_INITIAL * math.exp(-EPSILON_LAMBDA * n_tasks)
    return max(EPSILON_MIN, eps)


# ---------------------------------------------------------------------------
# ε-greedy エージェント選択
# ---------------------------------------------------------------------------


def select_agents(agents: list[Agent], epsilon: float | None = None) -> list[Agent]:
    """
    ε-greedy でエージェントを選択する。

    - ε 確率でランダム選択（探索）
    - 1-ε 確率で trust_score 上位から選択（活用）
    - 選択数は min(len(agents), MAX_AGENTS)
    - epsilon が None の場合はデフォルト値（EPSILON_INITIAL）を使用する

    Args:
        agents: 選択候補のエージェントリスト
        epsilon: 探索率（0.0〜1.0）。None の場合はデフォルト値を使用

    Returns:
        選択されたエージェントのリスト
    """
    n = min(len(agents), MAX_AGENTS)
    if n == 0:
        return []

    eps = epsilon if epsilon is not None else EPSILON_INITIAL

    if random.random() < eps:
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
    タスクの難易度（difficulty）とリスクレベル（risk_level）を LLM で判定する。

    Returns:
        {"difficulty": "low"|"medium"|"high", "risk_level": "low"|"medium"|"high"}
    """
    system = (
        "あなたはタスク評価AIです。ユーザーのタスク内容を分析して、"
        "difficulty（low/medium/high）と risk_level（low/medium/high）を"
        "必ずJSON形式のみで返してください。"
        '例: {"difficulty": "medium", "risk_level": "low"}'
    )
    raw = _llm.complete(system, f"タスク: {prompt}", max_tokens=100)
    try:
        candidate = raw.strip()
        if not candidate.startswith("{"):
            # Markdownコードブロックや前置きテキストを除去
            import re as _re
            m = _re.search(r'\{[^{}]*"difficulty"[^{}]*\}', candidate, _re.DOTALL)
            if m:
                candidate = m.group(0)
        data = json.loads(candidate)
    except json.JSONDecodeError:
        data = {}

    difficulty = data.get("difficulty", "medium")
    risk_level = data.get("risk_level", "medium")
    # 無効な値はmediumにフォールバック
    if difficulty not in _VALID_LEVELS:
        difficulty = "medium"
    if risk_level not in _VALID_LEVELS:
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
    raw = _llm.complete(system, user_message, max_tokens=500)
    try:
        candidate = raw.strip()
        if not candidate.startswith("["):
            # Markdownコードブロックや前置きテキストを除去してJSON配列を抽出
            import re as _re
            m = _re.search(r'\[.*\]', candidate, _re.DOTALL)
            if m:
                candidate = m.group(0)
        subtasks = json.loads(candidate)
        if not isinstance(subtasks, list):
            raise ValueError("expected list")
    except (json.JSONDecodeError, ValueError):
        # フォールバック: 全エージェントに同じタスクを割り当て
        subtasks = [{"agent_name": a.name, "subtask": prompt} for a in agents]

    return subtasks


# ---------------------------------------------------------------------------
# 因果連鎖エントリ記録
# ---------------------------------------------------------------------------


def _record_causal_entry(
    db: Session,
    *,
    task_id: str,
    layer: str,
    agent_id: str | None = None,
    score: float | None = None,
    note: str | None = None,
) -> CausalChainEntry:
    """
    因果連鎖エントリを DB に保存して返す。

    Args:
        db: DBセッション
        task_id: 対象タスクのID
        layer: レイヤー名（task_definition / coordinator / worker / reviewer）
        agent_id: エージェントID（worker レイヤーの場合）
        score: 評価スコア（0.0〜1.0）
        note: 問題の説明（省略可）

    Returns:
        保存された CausalChainEntry
    """
    entry = CausalChainEntry(
        task_id=task_id,
        layer=layer,
        agent_id=agent_id,
        score=score,
        note=note,
    )
    db.add(entry)
    db.commit()
    return entry


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

        # 2. 登録済みエージェントを取得してε-greedy選択（焼きなまし）
        all_agents = agent_service.list_agents(db)
        n_completed = (
            db.query(Task)
            .filter(Task.status == "completed")
            .count()
        )
        epsilon = compute_epsilon(n_completed)
        selected = select_agents(all_agents, epsilon=epsilon)

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

        # 5. 各サブタスクの結果をレビュアーで評価
        completed_subtasks = (
            db.query(SubTask)
            .filter(SubTask.task_id == task.task_id, SubTask.status == "completed")
            .all()
        )

        # agent_id → score のマッピング（複数サブタスクがある場合は平均）
        agent_scores: dict[str, list[float]] = {}
        for subtask in completed_subtasks:
            score = await evaluate_subtask(
                prompt=subtask.prompt,
                result=subtask.result or "",
                risk_level=task.risk_level or "medium",
            )
            subtask.score = score
            # TODO: 全サブタスク評価後に一括コミットする設計に改善する
            # 現状はサブタスクごとにコミットしており、途中エラー時に一部スコアのみ
            # 保存される可能性がある。MVP段階では許容範囲。
            db.commit()

            # 因果連鎖エントリを worker レイヤーとして記録
            _record_causal_entry(
                db,
                task_id=task.task_id,
                layer="worker",
                agent_id=subtask.agent_id,
                score=score,
            )

            if subtask.agent_id not in agent_scores:
                agent_scores[subtask.agent_id] = []
            agent_scores[subtask.agent_id].append(score)

        # エージェントごとのスコアを平均化
        avg_scores = {
            agent_id: sum(scores) / len(scores)
            for agent_id, scores in agent_scores.items()
        }

        # 6. スコアに比例して budget を分配
        wallets = {
            a.agent_id: a.wallet_address
            for a in selected
            if a.agent_id in avg_scores
        }
        rewards = await distribute_rewards(
            task_id=task.task_id,
            scores=avg_scores,
            wallets=wallets,
            budget=task.budget,
        )

        # サブタスクに reward を記録
        for subtask in completed_subtasks:
            subtask.reward = rewards.get(subtask.agent_id)
            db.commit()

        # 7. 各エージェントの trust_score を更新
        for agent_id, score in avg_scores.items():
            agent_service.update_trust_score(db, agent_id, eval_score=score)

        update_task_status(db, task, "completed")

    except Exception as exc:
        logger.error("Coordinator failed for task %s: %s", task.task_id, exc)
        update_task_status(db, task, "failed")
