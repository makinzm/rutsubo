"""
シミュレーター — 品質の異なるダミーエージェントを使って大量タスクを自動投入し、
「良いエージェントの採用率が時間とともに上がる」学習曲線を生成する。

実行方法:
    uv run python -m app.simulation

出力:
    simulation_result.json — 学習曲線データ
"""

import asyncio
import json
import logging

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.agent import Agent
from app.models.task import Task
from app.services.coordinator import run_coordinator
from app.services.task_service import create_task
from app.schemas.task import TaskCreateRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ダミーエージェント定義
# ---------------------------------------------------------------------------

DUMMY_AGENTS = [
    {
        "name": "HighQualityAgent",
        "description": "高品質なコード生成・分析が得意な優秀なエージェント",
        "wallet_address": "So11111111111111111111111111111111111111112",
        "endpoint": "http://localhost:9001",
        "quality": 0.9,
    },
    {
        "name": "MediumAgent",
        "description": "汎用的なタスクをこなす普通のエージェント",
        "wallet_address": "So11111111111111111111111111111111111111113",
        "endpoint": "http://localhost:9002",
        "quality": 0.6,
    },
    {
        "name": "PoorAgent",
        "description": "低品質な出力を返すことが多いエージェント",
        "wallet_address": "So11111111111111111111111111111111111111114",
        "endpoint": "http://localhost:9003",
        "quality": 0.3,
    },
    {
        "name": "NewAgent",
        "description": "新規参入エージェント。実績未知のため探索対象",
        "wallet_address": "So11111111111111111111111111111111111111115",
        "endpoint": "http://localhost:9004",
        "quality": None,  # 未知（ランダム）
    },
]

# シミュレーション用タスクプロンプト
_TASK_PROMPTS = [
    "Pythonでソートアルゴリズムを実装してください",
    "機械学習モデルの評価指標を説明してください",
    "RESTful APIの設計ベストプラクティスを列挙してください",
    "データベースのインデックス最適化方法を説明してください",
    "マイクロサービスアーキテクチャのメリット・デメリットを分析してください",
]


# ---------------------------------------------------------------------------
# エージェント登録
# ---------------------------------------------------------------------------


def _register_dummy_agents(db: Session) -> dict[str, str]:
    """
    ダミーエージェントをDBに登録する（既存の場合はスキップ）。

    Returns:
        {agent_name: agent_id} のマッピング
    """
    name_to_id: dict[str, str] = {}
    for agent_def in DUMMY_AGENTS:
        existing = db.query(Agent).filter(Agent.name == agent_def["name"]).first()
        if existing:
            name_to_id[agent_def["name"]] = existing.agent_id
            continue

        agent = Agent(
            name=agent_def["name"],
            description=agent_def["description"],
            wallet_address=agent_def["wallet_address"],
            endpoint=agent_def["endpoint"],
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        name_to_id[agent_def["name"]] = agent.agent_id
        logger.info("Registered agent: %s (%s)", agent.name, agent.agent_id)

    return name_to_id


# ---------------------------------------------------------------------------
# 学習曲線スナップショット
# ---------------------------------------------------------------------------


def _snapshot_trust_scores(db: Session, task_index: int) -> dict:
    """現在の全エージェントの trust_score をスナップショットとして返す。"""
    agents = db.query(Agent).all()
    return {
        "task_index": task_index,
        "agent_trust_scores": {a.name: round(a.trust_score, 4) for a in agents},
    }


# ---------------------------------------------------------------------------
# シミュレーション本体
# ---------------------------------------------------------------------------


async def run_simulation(
    db: Session,
    n_tasks: int = 20,
    output_file: str = "simulation_result.json",
) -> dict:
    """
    シミュレーションを実行し、学習曲線データを返す。

    1. 4ダミーエージェントを登録
    2. n_tasks件のタスクをループ投入
    3. 各タスク後にtrust_scoreをスナップショット
    4. 結果をJSONファイルに出力

    Args:
        db: DBセッション
        n_tasks: 投入するタスク数（デフォルト20）
        output_file: 出力JSONファイルパス

    Returns:
        {"learning_curve": [...]} 形式の結果dict
    """
    # 1. エージェント登録
    _register_dummy_agents(db)

    learning_curve = []

    # 初期スナップショット
    learning_curve.append(_snapshot_trust_scores(db, 0))

    # 2. タスクをループ投入
    for i in range(n_tasks):
        prompt = _TASK_PROMPTS[i % len(_TASK_PROMPTS)]
        req = TaskCreateRequest(prompt=prompt, budget=0.1)
        task = create_task(db, req)

        try:
            await run_coordinator(db, task)
        except Exception as exc:
            logger.warning("Task %d failed: %s", i + 1, exc)

        # 3. trust_score スナップショット
        db.expire_all()  # DBから最新値を再取得
        snapshot = _snapshot_trust_scores(db, i + 1)
        learning_curve.append(snapshot)
        logger.info("Task %d/%d done. Scores: %s", i + 1, n_tasks, snapshot["agent_trust_scores"])

    result = {"learning_curve": learning_curve}

    # 4. JSONファイルに出力
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("Simulation complete. Output: %s", output_file)
    return result


def run_simulation_sync(
    db: Session | None = None,
    n_tasks: int = 20,
    output_file: str = "simulation_result.json",
) -> dict:
    """
    run_simulation の同期ラッパー。テストおよびCLI実行から呼び出す。

    Args:
        db: DBセッション（None の場合は本番DBセッションを生成）
        n_tasks: 投入するタスク数
        output_file: 出力JSONファイルパス

    Returns:
        {"learning_curve": [...]} 形式の結果dict
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        return asyncio.run(run_simulation(db=db, n_tasks=n_tasks, output_file=output_file))
    finally:
        if close_db:
            db.close()


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    run_simulation_sync(n_tasks=n)
