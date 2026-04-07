# Timeline — Week 3 差別化機能

## 2026-04-07

### 開始
- ブランチ `feat/week3-differentiators` を `main` から作成
- 既存43テストがすべてパスすることを確認
- TODO.md / timeline.md 作成・コミット

### RED フェーズ（完了）
- `tests/test_week3_differentiators.py` を作成
- 12テストのうち10が失敗（うち2は既に通る: `test_causal_chain_not_found`、`test_reviewer_low_risk_weight`）
- コミット: `[test] add week3 differentiators test suite (RED)`

### GREEN フェーズ（完了）
- `app/config.py` 作成（EPSILON_INITIAL=0.3, LAMBDA=0.01, MIN=0.05）
- `app/models/causal_chain.py` 作成（CausalChainEntry モデル）
- `app/schemas/causal_chain.py` 作成（レスポンススキーマ）
- `coordinator.py`: `compute_epsilon()` 関数追加、焼きなましε使用、因果連鎖保存
- `reviewer.py`: `_build_system_prompt()` 抽出、`_RISK_WEIGHT` を high=3x, medium=2x, low=1x に更新
- `routers/tasks.py`: `GET /tasks/{task_id}/causal-chain` エンドポイント追加
- `main.py`: causal_chain モデルをインポート
- 55テスト全パス
- コミット: `[fix] implement week3 differentiators: epsilon annealing, causal chain, asymmetric loss`

### REFACTOR フェーズ（完了）
- `_record_causal_entry` ヘルパー関数を `coordinator.py` に抽出
- 55テスト全パス維持
- コミット: `[refactor] extract _record_causal_entry helper`

### DAレビュー（完了）
- 判定: LGTM
- 軽微指摘2件（MVP段階では許容）
- `da-review.md` に記録

---

（PR作成へ）
