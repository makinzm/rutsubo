"""
因果連鎖エントリモデル。

タスク失敗の原因がどのレイヤー（task_definition / coordinator / worker / reviewer）
にあるかを記録する。評価結果と照合することで責任の所在を逆引きできる。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CausalChainEntry(Base):
    __tablename__ = "causal_chain_entries"

    entry_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.task_id"), nullable=False
    )
    # "task_definition" | "coordinator" | "worker" | "reviewer"
    layer: Mapped[str] = mapped_column(String, nullable=False)
    # worker の場合はエージェント ID、それ以外は None
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # 0.0〜1.0（高いほど良い）
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 問題の説明
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
