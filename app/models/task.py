import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    prompt: Mapped[str] = mapped_column(String, nullable=False)
    budget: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    difficulty: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    subtasks: Mapped[list["SubTask"]] = relationship("SubTask", back_populates="task")


class SubTask(Base):
    __tablename__ = "subtasks"

    subtask_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(String, ForeignKey("tasks.task_id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agents.agent_id"), nullable=False)
    prompt: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    result: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    task: Mapped["Task"] = relationship("Task", back_populates="subtasks")
