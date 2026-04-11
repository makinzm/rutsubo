"""
Response schema for causal chain entries.
"""

from datetime import datetime

from pydantic import BaseModel


class CausalChainEntryResponse(BaseModel):
    entry_id: str
    task_id: str
    layer: str
    agent_id: str | None
    score: float | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
