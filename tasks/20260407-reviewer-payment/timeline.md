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

### 次のステップ
- フェーズ2-C: GREEN フェーズ（実装）
