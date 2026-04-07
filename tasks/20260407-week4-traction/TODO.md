# Week 4 Traction獲得機能

## 概要
ダッシュボードAPIとシミュレーターを実装し、Rutsuboのトラクション獲得を支援する。

## タスク一覧

### ダッシュボードAPI
- [ ] `app/schemas/dashboard.py` — レスポンススキーマ定義
- [ ] `app/routers/dashboard.py` — APIエンドポイント実装
- [ ] `app/main.py` — ルーター登録
- [ ] `tests/test_dashboard.py` — テスト実装

#### エンドポイント
- `GET /dashboard/agents` — 全エージェントの信頼スコア・報酬履歴集計
- `GET /dashboard/agents/{agent_id}` — 特定エージェントの詳細
- `GET /dashboard/tasks` — タスク一覧＋因果連鎖サマリー

### シミュレーター
- [ ] `app/simulation.py` — シミュレーター実装
- [ ] `tests/test_simulation.py` — テスト実装

## 完了条件
- 既存55テストがすべてパスしている
- 新規テスト7件がすべてパスしている
- `uv run python -m app.simulation` で実行できる
- `simulation_result.json` が出力される
