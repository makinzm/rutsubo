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
    評価スコアに基づいてエージェントの trust_score を指数移動平均で更新する。

    new_score = 0.8 * old_score + 0.2 * eval_score

    Args:
        db: DBセッション
        agent_id: 更新するエージェントのID
        eval_score: レビュアーが算出した評価スコア（0.0〜1.0）

    Returns:
        更新後のエージェント
    """
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise ValueError(f"Agent not found: {agent_id}")
    agent.trust_score = 0.8 * agent.trust_score + 0.2 * eval_score
    db.commit()
    db.refresh(agent)
    return agent
