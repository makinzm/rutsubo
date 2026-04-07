# Week 4 Traction獲得機能

## 概要
ダッシュボードAPIとシミュレーターを実装し、Rutsuboのトラクション獲得を支援する。

## タスク一覧

### ダッシュボードAPI
- [x] `app/schemas/dashboard.py` — レスポンススキーマ定義
- [x] `app/routers/dashboard.py` — APIエンドポイント実装
- [x] `app/main.py` — ルーター登録
- [x] `tests/test_dashboard.py` — テスト実装

#### エンドポイント
- `GET /dashboard/agents` — 全エージェントの信頼スコア・報酬履歴集計
- `GET /dashboard/agents/{agent_id}` — 特定エージェントの詳細
- `GET /dashboard/tasks` — タスク一覧＋因果連鎖サマリー

### シミュレーター
- [x] `app/simulation.py` — シミュレーター実装
- [x] `tests/test_simulation.py` — テスト実装

## 完了条件
- [x] 既存55テストがすべてパスしている（64件全パス）
- [x] 新規テスト9件がすべてパスしている（dashboard 7件 + simulation 2件）
- [x] `uv run python -m app.simulation` で実行できる
- [x] `simulation_result.json` が出力される
