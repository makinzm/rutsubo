# DA レビュー — タスク投入とコーディネーター（Step 2）

## レビュー日: 2026-04-07
## レビュワー: DA（Devil's Advocate）

---

## 変更差分サマリー

- `app/models/task.py` — Task, SubTask SQLAlchemyモデル
- `app/schemas/task.py` — TaskCreateRequest, TaskResponse
- `app/services/task_service.py` — タスクCRUD
- `app/services/coordinator.py` — ε-greedy選択, Claude API難易度判定, サブタスク分解, ワーカー送信
- `app/routers/tasks.py` — POST /tasks, GET /tasks/{task_id}
- `app/main.py` — tasks ルーター登録
- `tests/test_tasks.py` — 12テスト（29 passed確認済み）

---

## 指摘事項

### [中] tasks.py の `_run_coordinator_sync` でのDB Session共有問題

**問題:**
```python
def _run_coordinator_sync(task_id: str, db: Session) -> None:
    asyncio.run(run_coordinator(db, task))
```
`BackgroundTasks` に渡された `db` セッションは、レスポンス完了後にFastAPIが閉じる可能性がある。
バックグラウンドタスク実行中にセッションが無効になるリスクがある。

**推奨:**
バックグラウンドタスク内で新たなDB sessionを作成する。

```python
from app.db.database import SessionLocal

def _run_coordinator_sync(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = get_task(db, task_id)
        if task:
            asyncio.run(run_coordinator(db, task))
    finally:
        db.close()
```

ルーターの呼び出し側も `task_id` のみ渡すように変更する。

### [低] `test_create_task_triggers_coordinator` がコーディネーターの副作用を深く検証していない

**問題:**
Claude APIが「少なくとも1回呼ばれた」という確認のみ。
サブタスクが作成されたかどうかの検証がない。

**現状での許容理由:**
バックグラウンド実行の非同期性から、テスト中でのサブタスク検証は複雑になる。
`test_select_agents_*` でコーディネーターのコアロジックはカバーされている。
現時点では許容範囲とする。

### [低] `app/schemas/task.py` の未使用インポート

```python
from typing import Literal  # 未使用
```

削除すること。

---

## 修正必須項目

1. **[中] DB Session共有問題** — バックグラウンドタスクで独立したSessionを作成する
2. **[低] 未使用インポートの削除** — `from typing import Literal`

---

## 判定: **要修正**（初回）→ **LGTM**（修正後）

### 修正内容
1. **DB Session共有問題**: `_run_coordinator_sync` を `task_id` のみ受け取り、内部で `SessionLocal()` を生成するように変更
2. **未使用インポート削除**: `from typing import Literal` を削除
3. **テスト修正**: `test_create_task_triggers_coordinator` を `_run_coordinator_sync` のモック方式に変更（Session分離による副作用）

修正後テスト結果: **29 passed**

### 再レビュー判定: LGTM
- 中程度の問題（DB Session共有）が解消された
- テストが適切なレイヤーでモックするよう修正された
- 全テストがGREEN
