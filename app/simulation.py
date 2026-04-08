"""
シミュレーター — ε-greedy 採用ロジックの学習曲線を可視化するためのシミュレーション。

## 何をしているか

実際のワーカーエージェントサーバーを用意せずに、Rutsubo の採用ロジックが
「良いエージェントを自動的に優先するようになる」様子をデモする。

### 流れ

1. **エージェント登録**
   品質レベルが異なる4つのダミーエージェントをDBに登録する。
   各エージェントには固有の quality 値（0.0〜1.0）が設定されており、
   これがワーカーとしての「実力」を表す。

   | エージェント名    | quality | 意味                   |
   |------------------|---------|------------------------|
   | HighQualityAgent | 0.9     | 優秀なエージェント      |
   | MediumAgent      | 0.6     | 普通のエージェント      |
   | PoorAgent        | 0.3     | 低品質なエージェント    |
   | NewAgent         | None    | 未知（毎回ランダム）    |

2. **タスクの繰り返し投入**
   20件のタスクをループで投入し、各タスクでコーディネーターを動かす。
   コーディネーターは ε-greedy（焼きなまし）で担当エージェントを選び、
   サブタスクを割り当てる。

3. **品質ベースのモック実行**
   ワーカーエンドポイントへの HTTP 送信は実在しないため、
   `httpx.AsyncClient.post` をモックし、エンドポイント URL から
   そのエージェントの quality を引いた結果テキスト（`QUALITY:0.90 result...`）を返す。
   これにより「高品質エージェントは良い結果を出す」という前提を再現する。

4. **評価・trust_score 更新**
   コーディネーター内のレビュアー（LLM-as-a-Judge）が結果を評価する。
   モード `LLM_BACKEND=mock` では、結果テキストの `QUALITY:X` タグを
   そのままスコアとして使うため、実際の Claude API 呼び出しは不要。
   評価スコアに基づいて各エージェントの `trust_score` が
   指数移動平均（`0.8 * old + 0.2 * eval`）で更新される。

5. **学習曲線の出力**
   各タスク完了後に全エージェントの `trust_score` を記録し、
   最終的に `simulation_result.json` へ出力する。

### 期待される結果

タスク数が増えるにつれて：
- HighQualityAgent の trust_score が上昇し採用されやすくなる
- PoorAgent の trust_score が下降し採用されにくくなる
- ε が減衰（焼きなまし）することで探索より活用が優先されるようになる

### 環境変数

| 変数            | デフォルト | 説明                                          |
|----------------|-----------|-----------------------------------------------|
| `LLM_BACKEND`  | `mock`    | `mock` / `cli` / `api` を切り替え可能         |
| `PAYMENT_ENABLED` | `false` | `true` にすると Solana devnet への送金が有効  |

### 実行方法

    uv run python -m app.simulation          # デフォルト20タスク
    uv run python -m app.simulation 50       # 50タスクで実行

### 出力

    simulation_result.json — 学習曲線データ（task_index ごとの trust_score スナップショット）
"""

import asyncio
import json
import logging
import os
import random
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

# シミュレーターはデフォルトでモックLLMを使用する
# 実際のClaude APIやCLIを使いたい場合は LLM_BACKEND=api or cli を設定
os.environ.setdefault("LLM_BACKEND", "mock")

from app.db.database import Base, SessionLocal, engine
from app.models import agent as _agent_models  # noqa: F401
from app.models import causal_chain as _causal_chain_models  # noqa: F401
from app.models import task as _task_models  # noqa: F401
from app.models.agent import Agent

# テーブルが存在しない場合は作成する
Base.metadata.create_all(bind=engine)
from app.schemas.task import TaskCreateRequest
from app.services.coordinator import run_coordinator
from app.services.task_service import create_task

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

    # エンドポイント→品質のマッピングを構築
    endpoint_quality = {
        a["endpoint"]: (a["quality"] if a["quality"] is not None else random.uniform(0.0, 1.0))
        for a in DUMMY_AGENTS
    }

    def _make_httpx_mock():
        """エンドポイントURLに基づいて品質タグ付きレスポンスを返すhttpxモック。"""
        mock_http_client = AsyncMock()

        async def _mock_post(url, **kwargs):
            # URL からエンドポイントベース (scheme://host:port) を抽出
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            quality = endpoint_quality.get(base, 0.5)
            # NewAgent は毎回ランダム
            if quality is None:
                quality = random.uniform(0.0, 1.0)
            resp = MagicMock()
            resp.status_code = 200
            resp.text = f"QUALITY:{quality:.2f} result for task"
            return resp

        mock_http_client.post = _mock_post
        return mock_http_client

    # 2. タスクをループ投入
    for i in range(n_tasks):
        prompt = _TASK_PROMPTS[i % len(_TASK_PROMPTS)]
        req = TaskCreateRequest(prompt=prompt, budget=0.1)
        task = create_task(db, req)

        mock_http_client = _make_httpx_mock()
        with patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
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
