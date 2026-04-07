# Timeline: reviewer-payment

## 2026-04-07

### フェーズ2-A: 準備
- mainブランチから `feat/reviewer-payment` ブランチを作成
- TODO.md と timeline.md を作成

### フェーズ2-B: RED フェーズ
- テスト3ファイルを実装
  - tests/test_reviewer.py（8テスト）
  - tests/test_payment.py（4テスト）
  - tests/test_coordinator_integration.py（2テスト）
- 全14テストが期待通りにFAIL（ModuleNotFoundError）を確認

```
FAILED tests/test_reviewer.py::test_reviewer_returns_score - ModuleNotFoundError: No module named 'app.services.reviewer'
FAILED tests/test_payment.py::test_distribute_rewards_proportional - ModuleNotFoundError: No module named 'app.services.payment'
FAILED tests/test_coordinator_integration.py::test_coordinator_completes_task - ModuleNotFoundError: No module named 'app.services.reviewer'
...（14件すべてFAIL）
```

### フェーズ2-C: GREEN フェーズ
- app/models/task.py: SubTask に score/reward フィールドを追加
- app/services/reviewer.py: evaluate_subtask 実装（非対称損失関数プロンプト）
- app/services/payment.py: distribute_rewards 実装（スコア比例、PAYMENT_ENABLED対応）
- app/services/agent_service.py: update_trust_score 追加（指数移動平均）
- app/services/coordinator.py: 評価・分配・trust_score更新フローを統合
- 全43テストがGREEN（新規14テスト含む）

### 次のステップ
- フェーズ2-D: REFACTOR フェーズ
