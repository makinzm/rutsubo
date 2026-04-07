# TODO: タスク投入とコーディネーター（Step 2）

## 概要
`POST /tasks` エンドポイントとコーディネーターを実装する。
コーディネーターはClaude APIで難易度判定・サブタスク分解を行い、
ε-greedyでエージェントを選択してサブタスクを配布する。

## タスクリスト

### モデル・スキーマ
- [ ] `app/models/task.py` — Task, SubTask SQLAlchemyモデル
- [ ] `app/schemas/task.py` — TaskCreateRequest, TaskResponse, SubTaskResponse

### サービス
- [ ] `app/services/task_service.py` — タスクCRUD（create_task, get_task）
- [ ] `app/services/coordinator.py` — ε-greedy選択, Claude API難易度判定, サブタスク分解, ワーカー送信

### ルーター
- [ ] `app/routers/tasks.py` — POST /tasks, GET /tasks/{task_id}
- [ ] `app/main.py` — tasks ルーター登録

### テスト
- [ ] `tests/test_tasks.py` — APIテスト + コーディネーターユニットテスト

### 依存追加
- [ ] `uv add anthropic httpx`

## 完了条件
- 全テストがGREEN
- lefthookが通過
- DAレビューでLGTM

## ブランチ
`feat/task-coordinator`
