import re
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, field_validator

# Basic Solana Base58 address check (alphanumeric only, 32–44 characters)
_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class AgentRegisterRequest(BaseModel):
    name: str
    description: str
    wallet_address: str
    endpoint: AnyHttpUrl

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v

    @field_validator("description")
    @classmethod
    def description_length(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description must not be empty")
        if len(v) > 500:
            raise ValueError("description must be 500 characters or fewer")
        return v

    @field_validator("wallet_address")
    @classmethod
    def wallet_address_format(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("wallet_address must not be empty")
        if not _BASE58_RE.match(v):
            raise ValueError("wallet_address must be a valid Solana Base58 address (32–44 chars)")
        return v


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    description: str
    wallet_address: str
    endpoint: str
    trust_score: float
    created_at: datetime

    model_config = {"from_attributes": True}
