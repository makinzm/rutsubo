# Week 3 差別化機能 — TODO

## 概要

Week 3で実装する3つの差別化機能。

## 機能1: ε-greedy焼きなまし

### 要件
- `app/config.py` を新規作成して設定を集約
  - `EPSILON_INITIAL = 0.3`
  - `EPSILON_LAMBDA = 0.01`
  - `EPSILON_MIN = 0.05`
- `app/services/coordinator.py` の `select_agents` を修正
  - ε計算式: `ε = max(0.05, ε_initial * exp(-λ * n_tasks))`
  - `n_tasks` = DBから完了タスク数を取得
  - `compute_epsilon(n_tasks)` 関数を新規作成

### テストケース
- [ ] `test_epsilon_decreases_with_tasks` — タスク数が増えるとεが減る
- [ ] `test_epsilon_minimum_floor` — 大量タスク後もε≥0.05

---

## 機能2: 因果連鎖の可視化

### 要件
- `app/models/causal_chain.py` を新規作成（CausalChainEntryモデル）
- `app/schemas/causal_chain.py` を新規作成（レスポンススキーマ）
- `app/routers/tasks.py` にエンドポイント追加
  - `GET /tasks/{task_id}/causal-chain`
- `app/services/coordinator.py` でサブタスク評価後にエントリを保存
- `app/main.py` でモデル登録

### テストケース
- [ ] `test_causal_chain_entries_created` — タスク完了後にCausalChainEntryが作成される
- [ ] `test_get_causal_chain_api` — `GET /tasks/{task_id}/causal-chain` が200を返す
- [ ] `test_causal_chain_not_found` — 存在しないtask_idで404

---

## 機能3: 非対称損失関数のパラメータ化

### 要件
- `app/services/reviewer.py` の `_RISK_WEIGHT` を更新
  - `"high": 3.0`（現在2.0 → 3倍に変更）
  - `"medium": 2.0`（現在1.5 → 2倍に変更）
  - `"low": 1.0`（変更なし）
- プロンプト内に具体的な倍率を明記

### テストケース
- [ ] `test_reviewer_high_risk_prompt` — risk_level="high"のときプロンプトに3倍ペナルティが含まれる
- [ ] `test_reviewer_low_risk_prompt` — risk_level="low"のときプロンプトが標準（1倍）

---

## 完了条件

- 全テスト（43+新規テスト）がパス
- `uv run pytest` グリーン
- PRが作成されている
