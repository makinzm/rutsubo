# Timeline — Week 3 差別化機能

## 2026-04-07

### 開始
- ブランチ `feat/week3-differentiators` を `main` から作成
- 既存43テストがすべてパスすることを確認
- TODO.md / timeline.md 作成・コミット

### RED フェーズ（予定）
- 機能1: ε-greedy焼きなましのテストを書く
- 機能2: 因果連鎖のテストを書く
- 機能3: 非対称損失関数パラメータ化のテストを書く
- テストが失敗することを確認してからコミット

### GREEN フェーズ（予定）
- app/config.py 作成
- compute_epsilon 関数実装
- CausalChainEntry モデル作成
- 因果連鎖APIエンドポイント追加
- reviewer.py の _RISK_WEIGHT 更新

### REFACTOR フェーズ（予定）
- コードの整理・ドキュメントコメント整備

---

（以降、各フェーズ完了時に追記）
