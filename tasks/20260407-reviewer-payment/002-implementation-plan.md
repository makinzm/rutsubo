# 実装計画: Step 3 — 評価と分配（reviewer-payment）

## ブランチ名
`feat/reviewer-payment`

## タスクファイル
`tasks/20260407-reviewer-payment/TODO.md`

---

## 変更ファイル一覧

### 新規作成
- `app/services/reviewer.py` — LLM-as-a-Judge によるサブタスク評価
- `app/services/payment.py` — Solana 送金モック（スコア比例分配）
- `tests/test_reviewer.py` — レビュアーのテスト
- `tests/test_payment.py` — 報酬分配のテスト
- `tests/test_coordinator_integration.py` — コーディネーター統合テスト

### 変更
- `app/models/task.py` — SubTask に `score`（Float nullable）、`reward`（Float nullable）を追加
- `app/services/agent_service.py` — `update_trust_score` 関数を追加
- `app/services/coordinator.py` — タスク完了フローに評価・分配・trust_score更新を追加

---

## コミット計画

1. `[test] add tests for reviewer, payment, trust_score, and coordinator integration because of TDD RED phase`（--no-verify）
2. `[fix] add SubTask.score/reward fields and reviewer/payment services because of GREEN phase`
3. `[fix] integrate reviewer and payment into coordinator flow because of complete task flow`
4. `[refactor] clean up logging and error handling in reviewer/payment/coordinator`

---

## テストケース一覧

### レビュアー（`tests/test_reviewer.py`）
1. `test_reviewer_returns_score`
   - 前提: Claude API をモックして `{"score": 0.85}` を返す
   - 期待: float 型のスコア 0.85 が返る
2. `test_reviewer_score_range`
   - 前提: Claude API をモックして境界値（0.0, 1.0）・中間値を返す
   - 期待: スコアが 0.0〜1.0 の範囲に収まる

### trust_score 更新（`tests/test_reviewer.py` または `tests/test_agent_service.py`）
3. `test_update_trust_score`
   - 前提: trust_score=0.5 のエージェント、eval_score=1.0
   - 期待: `0.8 * 0.5 + 0.2 * 1.0 = 0.6`

### 報酬分配（`tests/test_payment.py`）
4. `test_distribute_rewards_proportional`
   - 前提: scores={"a1": 0.8, "a2": 0.2}、budget=1.0
   - 期待: a1=0.8, a2=0.2
5. `test_distribute_rewards_zero_scores`
   - 前提: scores={"a1": 0.0, "a2": 0.0}、budget=1.0
   - 期待: a1=0.5, a2=0.5（均等分配）

### コーディネーター統合（`tests/test_coordinator_integration.py`）
6. `test_coordinator_completes_task`
   - 前提: エージェント1件登録、Claude APIモック（難易度判定・サブタスク分解・評価）、httpxモック
   - 期待: run_coordinator 完了後、task.status == "completed"

---

## SubTask モデル変更

```python
score: Mapped[float | None] = mapped_column(Float, nullable=True)
reward: Mapped[float | None] = mapped_column(Float, nullable=True)
```

## reviewer.py の設計

```python
async def evaluate_subtask(prompt: str, result: str, risk_level: str) -> float:
    # 非対称損失関数を考慮したプロンプトで Claude API を呼び出す
    # score: 0.0〜1.0
```

## payment.py の設計

```python
async def distribute_rewards(
    task_id: str,
    scores: dict[str, float],  # agent_id -> score
    wallets: dict[str, str],    # agent_id -> wallet_address
    budget: float
) -> dict[str, float]:          # agent_id -> reward_amount
    # PAYMENT_ENABLED=false の場合はログのみ
```

---

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `PAYMENT_ENABLED` | `false` | `true` の場合 Solana devnet に送金（将来実装） |

---

この計画で進めてよいですか？変更点があれば教えてください。
