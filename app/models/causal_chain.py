"""
Causal chain entry model.

Records which layer (task_definition / coordinator / worker / reviewer) is responsible
for a task failure. Cross-referencing with evaluation results allows tracing accountability.
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
    # Agent ID for the worker layer; None for other layers
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # 0.0–1.0 (higher is better)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Description of the issue
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
