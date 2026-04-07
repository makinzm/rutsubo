# Timeline — Week 4 Traction

## 2026-04-07

### フェーズ2-A: 準備
- mainからfeat/week4-tractionブランチを作成
- tasks/20260407-week4-traction/TODO.md, timeline.md を作成

### フェーズ2-B: RED（ダッシュボード）
- tests/test_dashboard.py を作成
- 6件失敗（エンドポイント未実装のため404）、1件パス（test_dashboard_agent_not_found）
- エラー: AssertionError: assert 404 == 200（/dashboard/agents, /dashboard/tasks が存在しない）
- RED確認 OK

### フェーズ2-C: GREEN（ダッシュボード）
- app/schemas/dashboard.py 作成（AgentDashboardResponse, TaskDashboardResponse, TaskHistoryItem）
- app/routers/dashboard.py 作成（/dashboard/agents, /dashboard/agents/{id}, /dashboard/tasks）
- app/main.py に dashboard_router を登録
- DetachedInstanceError: セッションclose後にagentを参照していた → agent_idをセッション内で取り出すよう修正
- 全62件パス（既存55 + 新規7）GREEN確認 OK

### フェーズ2-B: RED（シミュレーター）
- tests/test_simulation.py を作成
- 2件失敗（ModuleNotFoundError: No module named 'app.simulation'）
- asyncio_mode未設定のため async test から sync wrapper（run_simulation_sync）に変更
- RED確認 OK

### フェーズ2-C: GREEN（シミュレーター）
- app/simulation.py 作成（run_simulation async + run_simulation_sync 同期ラッパー + CLI）
- DUMMY_AGENTS 4件定義（quality 0.9/0.6/0.3/None）
- 全64件パス GREEN確認 OK
