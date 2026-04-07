from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.agent import AgentRegisterRequest, AgentResponse
from app.services.agent_service import (
    AgentNameConflictError,
    get_agent,
    list_agents,
    register_agent,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/register", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def register(req: AgentRegisterRequest, db: Session = Depends(get_db)):
    try:
        agent = register_agent(db, req)
    except AgentNameConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent name already exists")
    return agent


@router.get("", response_model=list[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    return list_agents(db)


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent_by_id(agent_id: str, db: Session = Depends(get_db)):
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent
