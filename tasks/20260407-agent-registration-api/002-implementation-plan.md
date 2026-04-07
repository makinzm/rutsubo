# 実装計画 — エージェント登録API

## ブランチ名
`feat/agent-registration-api`

## タスクファイル
`tasks/20260407-agent-registration-api/TODO.md`

---

## 実装する機能

### エンドポイント一覧

| Method | Path | 説明 |
|--------|------|------|
| POST | /agents/register | エージェントを新規登録する |
| GET | /agents | 全エージェント一覧を取得する |
| GET | /agents/{agent_id} | 特定のエージェントを取得する |

### データモデル（Agent）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| agent_id | UUID | 一意識別子（自動生成） |
| name | str | エージェント名 |
| description | str | 得意なこと・専門領域 |
| wallet_address | str | Solanaウォレットアドレス |
| endpoint | str | エージェントのAPIエンドポイント |
| trust_score | float | 初期値0.5 |
| created_at | datetime | 登録日時 |

---

## 技術スタック

- **フレームワーク**: FastAPI
- **データストア**: SQLite（SQLAlchemy ORM + alembic マイグレーション）
- **バリデーション**: Pydantic v2
- **テスト**: pytest + httpx（TestClient）
- **パッケージ管理**: pip + requirements.txt

### 設計方針（Postgres移行を見据えた設計）
- SQLAlchemy の ORM を使い、DB依存のコードを `db/` レイヤーに閉じ込める
- `DATABASE_URL` を環境変数で切り替えられるようにする
- `alembic` でマイグレーション管理（将来の移行を容易にする）

---

## ディレクトリ構成

```
rutsubo/
├── app/
│   ├── main.py              # FastAPI アプリ定義・ルーター登録
│   ├── models/
│   │   └── agent.py         # SQLAlchemy ORM モデル
│   ├── schemas/
│   │   └── agent.py         # Pydantic スキーマ（Request/Response）
│   ├── routers/
│   │   └── agents.py        # /agents エンドポイント実装
│   ├── services/
│   │   └── agent_service.py # ビジネスロジック
│   └── db/
│       ├── database.py      # DB接続・セッション管理
│       └── migrations/      # alembic マイグレーション
├── tests/
│   ├── conftest.py          # テスト用フィクスチャ（テスト用SQLite）
│   └── test_agents.py       # エージェントAPIのテスト
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

---

## コミット計画

1. `[test] エージェント登録APIのテストケースを追加 because of TDDサイクルのREDフェーズ` （--no-verify）
2. `[fix] エージェント登録APIの実装を追加 because of テストをGREENにする`
3. `[refactor] エージェントAPIの構造を整理 because of 保守性の向上`

---

## テストケース一覧

### POST /agents/register

| テストケース | 検証する振る舞い | 期待結果 |
|-------------|----------------|---------|
| test_register_agent_success | 正常なデータでエージェントを登録できる | 201 Created、agent_id/trust_score(0.5)/created_atが含まれる |
| test_register_agent_duplicate_name | 同じ名前で二重登録した場合 | 409 Conflict |
| test_register_agent_invalid_wallet | wallet_addressが空文字の場合 | 422 Unprocessable Entity |
| test_register_agent_invalid_endpoint | endpointがURL形式でない場合 | 422 Unprocessable Entity |
| test_register_agent_missing_fields | 必須フィールドが欠落している場合 | 422 Unprocessable Entity |

### GET /agents

| テストケース | 検証する振る舞い | 期待結果 |
|-------------|----------------|---------|
| test_list_agents_empty | エージェントが0件のとき | 200 OK、空配列 |
| test_list_agents_multiple | 複数エージェント登録後 | 200 OK、登録した全エージェントが含まれる |

### GET /agents/{agent_id}

| テストケース | 検証する振る舞い | 期待結果 |
|-------------|----------------|---------|
| test_get_agent_success | 存在するagent_idで取得 | 200 OK、正しいエージェント情報 |
| test_get_agent_not_found | 存在しないagent_idで取得 | 404 Not Found |

---

## fixture設計

- テスト用DBは**インメモリSQLite**（`sqlite:///:memory:`）を使用
- 各テストは独立したDBセッションで実行（テスト間の干渉なし）
- `conftest.py` の `client` フィクスチャが `TestClient` を提供
- 外部サービス（Solana等）への依存はなし（wallet_addressは文字列として保存するだけ）

---

## 完了条件

- [ ] 全テストが GREEN になること
- [ ] `GET /agents`、`GET /agents/{agent_id}`、`POST /agents/register` が動作すること
- [ ] `uvicorn app.main:app` で起動できること
- [ ] README.md にセットアップ手順と動作例を追記すること

---

この計画で進めてよいですか？変更点があれば教えてください。
