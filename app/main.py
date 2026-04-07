from fastapi import FastAPI

from app.db.database import Base, engine
from app.models import agent as _agent_models  # noqa: F401 — registers models with Base
from app.routers.agents import router as agents_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Rutsubo API", version="0.1.0")

app.include_router(agents_router)
