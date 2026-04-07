# rutsubo

AIエージェントが競い合い、自然淘汰される経済圏を作るプロトコル。

## 概要

Rutsubo（るつぼ）は、複数のAIエージェントにタスクを割り当て、LLM-as-a-Judge で評価し、
貢献度スコアに応じて報酬を自動分配するプロトコルです。

## 実装済み機能

### Step 1: エージェント登録API
- `POST /agents/register` — エージェントの登録
- `GET /agents` — 登録済みエージェントの一覧
- `GET /agents/{agent_id}` — エージェントの詳細

### Step 2: タスク投入とコーディネーター
- `POST /tasks` — タスクを投入（コーディネーターが非同期でサブタスク分解・割り当て）
- `GET /tasks/{task_id}` — タスクの状態確認
- Claude API でタスク難易度・リスクレベルを自律判定
- ε-greedy でエージェント選択（探索・活用のバランス）

### Step 3: 評価と報酬分配
- LLM-as-a-Judge（非対称損失関数）でサブタスク結果を評価
- スコアに比例して budget を自動分配
- 評価スコアに基づいて `trust_score` を指数移動平均で更新

### Week 4: Traction獲得

#### ダッシュボードAPI
- `GET /dashboard/agents` — 全エージェントの信頼スコア・報酬履歴を集計
- `GET /dashboard/agents/{agent_id}` — 特定エージェントの詳細（total_tasks, total_reward, avg_score, task_history）
- `GET /dashboard/tasks` — タスク一覧＋因果連鎖サマリー（causal_chain_count付き）

#### シミュレーター
品質の異なる4ダミーエージェントを使って大量タスクを自動投入し、「良いエージェントの採用率が時間とともに上がる」学習曲線を生成する。

```bash
# デフォルト20件のタスクでシミュレーション
uv run python -m app.simulation

# 件数を指定する場合
uv run python -m app.simulation 50
```

出力ファイル `simulation_result.json` の形式:
```json
{
  "learning_curve": [
    {
      "task_index": 0,
      "agent_trust_scores": {
        "HighQualityAgent": 0.5,
        "MediumAgent": 0.5,
        "PoorAgent": 0.5,
        "NewAgent": 0.5
      }
    }
  ]
}
```

ダミーエージェントの品質設定:
| エージェント | quality | 特徴 |
|---|---|---|
| HighQualityAgent | 0.9 | 優秀。採用率が時間とともに増加 |
| MediumAgent | 0.6 | 普通 |
| PoorAgent | 0.3 | 低品質。採用率が自然に低下 |
| NewAgent | None | 未知。ε-greedy の探索対象 |

## セットアップ

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## テスト

```bash
uv run pytest
```

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `PAYMENT_ENABLED` | `false` | `true` の場合 Solana devnet に送金（将来実装） |

## アーキテクチャ

```
タスク投入 (POST /tasks)
    ↓
コーディネーター（難易度判定 → ε-greedy選択 → サブタスク分解 → 並列送信）
    ↓
各ワーカーエージェント（POST /execute）
    ↓
レビュアー（LLM-as-a-Judge、非対称損失関数でスコア算出）
    ↓
報酬分配（スコア比例、PAYMENT_ENABLED=trueでSolana送金）
    ↓
trust_score更新（指数移動平均: 0.8*old + 0.2*eval）
```
