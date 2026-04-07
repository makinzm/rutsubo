# TODO: Step 3 — 評価と分配（reviewer-payment）

## 概要
コーディネーターがサブタスクをワーカーエージェントに送信後、各ワーカーの結果を
LLM-as-a-Judge で評価し、スコアに比例した報酬分配とtrust_score更新を行う。

## タスク一覧

### モデル変更
- [x] SubTask に `score: Float nullable` を追加
- [x] SubTask に `reward: Float nullable` を追加

### サービス実装
- [x] `app/services/reviewer.py` — evaluate_subtask（Claude APIで0.0〜1.0スコア）
- [x] `app/services/payment.py` — distribute_rewards（スコア比例分配、PAYMENT_ENABLED対応）
- [x] `app/services/agent_service.py` — update_trust_score（指数移動平均）

### コーディネーター統合
- [x] `app/services/coordinator.py` — 評価・分配・trust_score更新フローを追加

### テスト
- [x] `tests/test_reviewer.py`
  - [x] test_reviewer_returns_score
  - [x] test_reviewer_score_range
  - [x] test_update_trust_score
- [x] `tests/test_payment.py`
  - [x] test_distribute_rewards_proportional
  - [x] test_distribute_rewards_zero_scores
- [x] `tests/test_coordinator_integration.py`
  - [x] test_coordinator_completes_task

## 完了条件
- 全テストがGREEN
- lefthook通過
- task.status == "completed" が統合テストで確認できる
