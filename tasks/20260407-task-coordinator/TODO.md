# TODO: タスク投入とコーディネーター（Step 2）

## 概要
`POST /tasks` エンドポイントとコーディネーターを実装する。
コーディネーターはClaude APIで難易度判定・サブタスク分解を行い、
ε-greedyでエージェントを選択してサブタスクを配布する。

## タスクリスト

### モデル・スキーマ
- [x] `app/models/task.py` — Task, SubTask SQLAlchemyモデル
- [x] `app/schemas/task.py` — TaskCreateRequest, TaskResponse

### サービス
- [x] `app/services/task_service.py` — タスクCRUD（create_task, get_task）
- [x] `app/services/coordinator.py` — ε-greedy選択, Claude API難易度判定, サブタスク分解, ワーカー送信

### ルーター
- [x] `app/routers/tasks.py` — POST /tasks, GET /tasks/{task_id}
- [x] `app/main.py` — tasks ルーター登録

### テスト
- [x] `tests/test_tasks.py` — APIテスト + コーディネーターユニットテスト（29 passed）

### 依存追加
- [x] `uv add anthropic httpx`

## 完了条件
- [x] 全テストがGREEN（29 passed）
- [x] lefthook設定なし（pytestで代替）
- [x] DAレビューでLGTM

## ブランチ
`feat/task-coordinator`
