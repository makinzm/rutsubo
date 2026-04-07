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

## GREEN フェーズ（予定）
- 最小限の実装でテストを通す

## REFACTOR フェーズ（予定）
- コードの整理・ドキュメント追加
