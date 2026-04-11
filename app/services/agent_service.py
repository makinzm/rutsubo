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


def update_trust_score(db: Session, agent_id: str, eval_score: float) -> Agent:
    """
    Update an agent's trust_score using exponential moving average based on the evaluation score.

    new_score = 0.8 * old_score + 0.2 * eval_score

    Args:
        db: Database session
        agent_id: ID of the agent to update
        eval_score: Evaluation score computed by the reviewer (0.0–1.0)

    Returns:
        The updated agent
    """
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise ValueError(f"Agent not found: {agent_id}")
    agent.trust_score = 0.8 * agent.trust_score + 0.2 * eval_score
    db.commit()
    db.refresh(agent)
    return agent
