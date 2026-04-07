# タイムライン: タスク投入とコーディネーター（Step 2）

## 2026-04-07

### ブランチ作成・準備完了
- `feat/task-coordinator` ブランチを作成
- TODO.md, timeline.md を作成

---

## RED フェーズ — 完了
- tests/test_tasks.py を実装（12テスト）
- 実行結果: **11 failed, 1 passed**
- 失敗理由: `app.services.coordinator` が存在しない / `/tasks` ルートが未登録
- 偶然PASS: `test_get_task_not_found`（404はルートが未登録のため）
- エラーログ:
  ```
  AttributeError: module 'app.services' has no attribute 'coordinator'
  ModuleNotFoundError: No module named 'app.services.coordinator'
  ```

## GREEN フェーズ — 完了
- 実装ファイル:
  - `app/models/task.py` — Task, SubTask SQLAlchemyモデル
  - `app/schemas/task.py` — TaskCreateRequest, TaskResponse
  - `app/services/task_service.py` — タスクCRUD
  - `app/services/coordinator.py` — ε-greedy選択, Claude API難易度判定, サブタスク分解, ワーカー送信
  - `app/routers/tasks.py` — POST /tasks, GET /tasks/{task_id}
  - `app/main.py` — tasks ルーター登録
- 修正点: test_create_task_success のレスポンス期待値を修正
  - バックグラウンド実行のため difficulty/risk_level はレスポンス時点で None が正しい
- 実行結果: **29 passed**

## REFACTOR フェーズ — 完了
- 不要インポート（`Any`）除去
- `_VALID_LEVELS`, `_CLAUDE_MODEL` 定数に切り出し
- `assess_task` のフォールバックロジックを `_VALID_LEVELS` で統一
- 実行結果: **29 passed**（変更なし）
