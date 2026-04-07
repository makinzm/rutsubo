# TODO: Step 3 — 評価と分配（reviewer-payment）

## 概要
コーディネーターがサブタスクをワーカーエージェントに送信後、各ワーカーの結果を
LLM-as-a-Judge で評価し、スコアに比例した報酬分配とtrust_score更新を行う。

## タスク一覧

### モデル変更
- [ ] SubTask に `score: Float nullable` を追加
- [ ] SubTask に `reward: Float nullable` を追加

### サービス実装
- [ ] `app/services/reviewer.py` — evaluate_subtask（Claude APIで0.0〜1.0スコア）
- [ ] `app/services/payment.py` — distribute_rewards（スコア比例分配、PAYMENT_ENABLED対応）
- [ ] `app/services/agent_service.py` — update_trust_score（指数移動平均）

### コーディネーター統合
- [ ] `app/services/coordinator.py` — 評価・分配・trust_score更新フローを追加

### テスト
- [ ] `tests/test_reviewer.py`
  - [ ] test_reviewer_returns_score
  - [ ] test_reviewer_score_range
  - [ ] test_update_trust_score
- [ ] `tests/test_payment.py`
  - [ ] test_distribute_rewards_proportional
  - [ ] test_distribute_rewards_zero_scores
- [ ] `tests/test_coordinator_integration.py`
  - [ ] test_coordinator_completes_task

## 完了条件
- 全テストがGREEN
- lefthook通過
- task.status == "completed" が統合テストで確認できる
