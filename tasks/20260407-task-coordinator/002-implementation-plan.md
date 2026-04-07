# 実装計画 - タスク投入とコーディネーター（Step 2）

## ブランチ名
`feat/task-coordinator`

## タスクファイル
`tasks/20260407-task-coordinator/TODO.md`

## 概要
`POST /tasks` エンドポイントを実装し、コーディネーターがClaude APIを使って難易度判定・サブタスク分解・ε-greedyエージェント選択を行う。

---

## ファイル構成（追加・変更）

```
app/
  models/
    task.py          # Task, SubTask モデル（新規）
  schemas/
    task.py          # TaskCreateRequest, TaskResponse, SubTaskResponse（新規）
  services/
    task_service.py  # タスクCRUD（新規）
    coordinator.py   # コーディネーターロジック（新規）
  routers/
    tasks.py         # /tasks ルーター（新規）
  main.py            # tasks ルーター登録（変更）
tests/
  test_tasks.py      # タスクAPIテスト（新規）
```

---

## DBモデル設計

### Task テーブル
| カラム | 型 | 説明 |
|---|---|---|
| task_id | String (UUID) | PK |
| prompt | String | ユーザーのタスク内容 |
| budget | Float | 予算（SOL/USDC） |
| status | String | pending / running / completed / failed |
| difficulty | String | low / medium / high（Claude推定） |
| risk_level | String | low / medium / high（Claude推定） |
| created_at | DateTime | 作成日時 |

### SubTask テーブル
| カラム | 型 | 説明 |
|---|---|---|
| subtask_id | String (UUID) | PK |
| task_id | String (FK) | 親タスク |
| agent_id | String (FK) | 割当エージェント |
| prompt | String | サブタスク内容 |
| status | String | pending / running / completed / failed |
| result | String / NULL | 実行結果 |
| created_at | DateTime | 作成日時 |

---

## コーディネーターロジック設計

### 難易度・リスクレベル判定（Claude API）
- Claude API（claude-sonnet-4-6）を呼び出し、JSONで `difficulty` / `risk_level` を返す
- レスポンスのJSONをパースして Task に保存

### ε-greedy エージェント選択
- ε = 0.2 固定（将来のアニーリングを見据えて定数として定義）
- 選択数: min(登録エージェント数, 3)
- ε確率でランダム選択、残りは trust_score 降順から選択
- エージェントが0件の場合は `400 Bad Request`

### サブタスク分解（Claude API）
- タスクの prompt と選択エージェント一覧（名前・説明）を渡し、各エージェント向けサブタスクをJSON配列で取得
- Claude APIの呼び出しをモック可能にするため、coordinator.py 内に依存注入可能な構造にする

### ワーカーへの送信
- `httpx.AsyncClient` で各エージェントの `endpoint/execute` に `POST` 送信
- バックグラウンドタスク（`asyncio.create_task`）で非同期実行
- HTTP失敗時は SubTask.status を `failed` に更新

---

## コミット計画

1. `[test] Task/SubTaskモデルとAPIのテストを追加 because of TDDサイクル開始`（--no-verify）
2. `[fix] Task/SubTaskモデル・スキーマ・サービス実装 because of テストをGREENにする`
3. `[fix] コーディネーターのε-greedy選択とサブタスク分解を実装 because of テストをGREENにする`
4. `[refactor] コーディネーターのコード整理とドキュメント追加 because of 可読性向上`

---

## テストケース一覧

### POST /tasks

| テスト名 | 検証内容 | 期待結果 |
|---|---|---|
| test_create_task_success | 正常なデータでタスク作成 | 201, task_id/status=pending/difficulty/risk_level含む |
| test_create_task_no_agents | エージェント0件でタスク作成 | 400 Bad Request |
| test_create_task_missing_prompt | promptなし | 422 |
| test_create_task_invalid_budget | budget < 0 | 422 |
| test_create_task_triggers_coordinator | コーディネーターが非同期で起動することを確認 | Claude APIとhttpxが呼ばれる |

### GET /tasks/{task_id}

| テスト名 | 検証内容 | 期待結果 |
|---|---|---|
| test_get_task_success | 存在するtask_idで取得 | 200, 正しいタスク情報 |
| test_get_task_not_found | 存在しないtask_idで取得 | 404 |

### コーディネーターユニットテスト

| テスト名 | 検証内容 | 期待結果 |
|---|---|---|
| test_select_agents_exploit | trust_score上位が選ばれる（ε=0時） | 上位3件が選択される |
| test_select_agents_explore | ε=1.0時にランダム選択 | 全エージェントから選択される |
| test_select_agents_less_than_3 | 2エージェントのみ存在する場合 | 2件選択 |

---

## fixture設計

- Claude APIは `unittest.mock.patch` でモック（`anthropic.Anthropic().messages.create`）
  - 難易度判定のレスポンス: `{"difficulty": "medium", "risk_level": "low"}`
  - サブタスク分解のレスポンス: サブタスクのJSON配列
- httpxは `pytest-mock` or `unittest.mock` で `AsyncClient.post` をモック
- DBはインメモリSQLite（既存のconftest.pyのパターンを継承）

---

✅ この計画で進めてよいですか？変更点があれば教えてください。
