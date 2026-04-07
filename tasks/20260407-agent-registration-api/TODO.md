# TODO — エージェント登録API

## 概要
RutsuboプロジェクトのStep 1として、AIエージェントを登録・管理するAPIを実装する。

## タスク一覧

### フェーズ2-A: 準備
- [x] mainブランチから `feat/agent-registration-api` ブランチを作成
- [x] TODO.md 作成
- [x] timeline.md 作成

### フェーズ2-B: RED フェーズ（テスト実装）
- [ ] requirements.txt / requirements-dev.txt 作成
- [ ] tests/conftest.py 作成（インメモリSQLiteフィクスチャ）
- [ ] tests/test_agents.py 作成（全9テストケース）
- [ ] テストが失敗することを確認

### フェーズ2-C: GREEN フェーズ（実装）
- [ ] app/db/database.py — DB接続・セッション管理
- [ ] app/models/agent.py — SQLAlchemy ORM モデル
- [ ] app/schemas/agent.py — Pydantic スキーマ
- [ ] app/services/agent_service.py — ビジネスロジック
- [ ] app/routers/agents.py — エンドポイント実装
- [ ] app/main.py — FastAPI アプリ定義
- [ ] 全テストが GREEN になることを確認

### フェーズ2-D: REFACTOR フェーズ
- [ ] コード構造の整理
- [ ] ドキュメントコメント整備
- [ ] テストが引き続き GREEN であることを確認

### フェーズ3: PR作成
- [ ] README.md 更新
- [ ] DAレビュー実施
- [ ] PR作成

## エンドポイント仕様

### POST /agents/register
リクエスト:
```json
{
  "name": "MyAgent",
  "description": "得意なこと・専門領域",
  "wallet_address": "Solanaウォレットアドレス",
  "endpoint": "https://example.com/agent"
}
```
レスポンス (201 Created):
```json
{
  "agent_id": "uuid",
  "name": "MyAgent",
  "description": "...",
  "wallet_address": "...",
  "endpoint": "...",
  "trust_score": 0.5,
  "created_at": "2026-04-07T..."
}
```

### GET /agents
レスポンス (200 OK):
```json
[
  { ...agent... }
]
```

### GET /agents/{agent_id}
レスポンス (200 OK): agent オブジェクト
エラー (404): agent_id が存在しない場合
