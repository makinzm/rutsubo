from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.schemas.agent import AgentRegisterRequest


class AgentNameConflictError(Exception):
    pass


def register_agent(db: Session, req: AgentRegisterRequest) -> Agent:
    agent = Agent(
        name=req.name,
        description=req.description,
        wallet_address=req.wallet_address,
        endpoint=str(req.endpoint),
    )
    db.add(agent)
    try:
        db.commit()
        db.refresh(agent)
    except IntegrityError:
        db.rollback()
        raise AgentNameConflictError(f"Agent name '{req.name}' already exists")
    return agent


def list_agents(db: Session) -> list[Agent]:
    return db.query(Agent).all()


def get_agent(db: Session, agent_id: str) -> Agent | None:
    return db.query(Agent).filter(Agent.agent_id == agent_id).first()
