"""
Simulator — simulation for visualizing the learning curve of the ε-greedy hiring logic.

## What it does

Demonstrates how Rutsubo's hiring logic naturally starts prioritizing better agents,
without needing real worker agent servers.

### Flow

1. **Agent registration**
   Registers 4 dummy agents with different quality levels into the DB.
   Each agent has a unique quality value (0.0–1.0) representing their capability as a worker.

   | Agent name       | quality | Meaning                        |
   |------------------|---------|--------------------------------|
   | HighQualityAgent | 0.9     | High-performing agent          |
   | MediumAgent      | 0.6     | Average agent                  |
   | PoorAgent        | 0.3     | Low-quality agent              |
   | NewAgent         | None    | Unknown (random each time)     |

2. **Repeated task submission**
   Submits 20 tasks in a loop, running the coordinator for each task.
   The coordinator selects the assigned agent via ε-greedy (simulated annealing)
   and assigns subtasks.

3. **Quality-based mock execution**
   Since there are no real worker endpoints to send HTTP requests to,
   `httpx.AsyncClient.post` is mocked to return a result text
   (`QUALITY:0.90 result...`) derived from the agent's quality for that endpoint URL.
   This reproduces the premise that "high-quality agents produce better results."

4. **Evaluation and trust_score update**
   The reviewer inside the coordinator (LLM-as-a-Judge) evaluates the results.
   In `LLM_BACKEND=mock` mode, the `QUALITY:X` tag in the result text is used
   directly as the score, so no real Claude API call is needed.
   Each agent's `trust_score` is updated via exponential moving average
   (`0.8 * old + 0.2 * eval`) based on the evaluation score.

5. **Learning curve output**
   After each task completes, all agents' `trust_score` values are recorded,
   and the final result is written to `simulation_result.json`.

### Expected results

As the number of tasks increases:
- HighQualityAgent's trust_score rises and it is selected more often
- PoorAgent's trust_score falls and it is selected less often
- As ε decays (simulated annealing), exploitation is prioritized over exploration

### Environment variables

| Variable            | Default | Description                                         |
|---------------------|---------|-----------------------------------------------------|
| `LLM_BACKEND`       | `mock`  | Switch between `mock` / `cli` / `api`               |
| `PAYMENT_ENABLED`   | `false` | Set to `true` to enable Solana devnet transfers     |

### How to run

    uv run python -m app.simulation          # default 20 tasks
    uv run python -m app.simulation 50       # run with 50 tasks

### Output

    simulation_result.json — learning curve data (trust_score snapshot per task_index)
"""

import asyncio
import json
import logging
import os
import random
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

# The simulator uses the mock LLM by default.
# Set LLM_BACKEND=api or cli to use the real Claude API or CLI.
os.environ.setdefault("LLM_BACKEND", "mock")

from app.db.database import Base, SessionLocal, engine
from app.models import agent as _agent_models  # noqa: F401
from app.models import causal_chain as _causal_chain_models  # noqa: F401
from app.models import task as _task_models  # noqa: F401
from app.models.agent import Agent

# Create tables if they do not exist
Base.metadata.create_all(bind=engine)
from app.schemas.task import TaskCreateRequest
from app.services.coordinator import run_coordinator
from app.services.task_service import create_task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dummy agent definitions
# ---------------------------------------------------------------------------

DUMMY_AGENTS = [
    {
        "name": "HighQualityAgent",
        "description": "An excellent agent specializing in high-quality code generation and analysis",
        "wallet_address": "So11111111111111111111111111111111111111112",
        "endpoint": "http://localhost:9001",
        "quality": 0.9,
    },
    {
        "name": "MediumAgent",
        "description": "An average agent capable of handling general-purpose tasks",
        "wallet_address": "So11111111111111111111111111111111111111113",
        "endpoint": "http://localhost:9002",
        "quality": 0.6,
    },
    {
        "name": "PoorAgent",
        "description": "An agent that frequently produces low-quality output",
        "wallet_address": "So11111111111111111111111111111111111111114",
        "endpoint": "http://localhost:9003",
        "quality": 0.3,
    },
    {
        "name": "NewAgent",
        "description": "A newly entered agent with unknown track record; target for exploration",
        "wallet_address": "So11111111111111111111111111111111111111115",
        "endpoint": "http://localhost:9004",
        "quality": None,  # Unknown (random)
    },
]

# Task prompts for simulation
_TASK_PROMPTS = [
    "Implement a sorting algorithm in Python",
    "Explain evaluation metrics for machine learning models",
    "List best practices for RESTful API design",
    "Explain methods for database index optimization",
    "Analyze the pros and cons of microservice architecture",
]


# ---------------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------------


def _register_dummy_agents(db: Session) -> dict[str, str]:
    """
    Register dummy agents in the DB (skip if they already exist).

    Returns:
        Mapping of {agent_name: agent_id}
    """
    name_to_id: dict[str, str] = {}
    for agent_def in DUMMY_AGENTS:
        existing = db.query(Agent).filter(Agent.name == agent_def["name"]).first()
        if existing:
            name_to_id[agent_def["name"]] = existing.agent_id
            continue

        agent = Agent(
            name=agent_def["name"],
            description=agent_def["description"],
            wallet_address=agent_def["wallet_address"],
            endpoint=agent_def["endpoint"],
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        name_to_id[agent_def["name"]] = agent.agent_id
        logger.info("Registered agent: %s (%s)", agent.name, agent.agent_id)

    return name_to_id


# ---------------------------------------------------------------------------
# Learning curve snapshot
# ---------------------------------------------------------------------------


def _snapshot_trust_scores(db: Session, task_index: int) -> dict:
    """Return a snapshot of the current trust_score for all agents."""
    agents = db.query(Agent).all()
    return {
        "task_index": task_index,
        "agent_trust_scores": {a.name: round(a.trust_score, 4) for a in agents},
    }


# ---------------------------------------------------------------------------
# Simulation body
# ---------------------------------------------------------------------------


async def run_simulation(
    db: Session,
    n_tasks: int = 20,
    output_file: str = "simulation_result.json",
) -> dict:
    """
    Run the simulation and return learning curve data.

    1. Register 4 dummy agents
    2. Submit n_tasks tasks in a loop
    3. Take a trust_score snapshot after each task
    4. Write results to a JSON file

    Args:
        db: Database session
        n_tasks: Number of tasks to submit (default 20)
        output_file: Output JSON file path

    Returns:
        Result dict in the format {"learning_curve": [...]}
    """
    # 1. Register agents
    _register_dummy_agents(db)

    learning_curve = []

    # Initial snapshot
    learning_curve.append(_snapshot_trust_scores(db, 0))

    # Build endpoint → quality mapping
    endpoint_quality = {
        a["endpoint"]: (a["quality"] if a["quality"] is not None else random.uniform(0.0, 1.0))
        for a in DUMMY_AGENTS
    }

    def _quality_response(quality: float, subtask: str) -> str:
        """
        Generate a plausible response text based on quality level.

        When LLM_BACKEND=cli/api, Claude actually evaluates the text,
        so the response must convey the quality level meaningfully.
        When using the mock backend, the QUALITY:X tag is used for evaluation.
        """
        if quality >= 0.8:
            return (
                f"[Complete answer] {subtask}\n\n"
                "Providing a detailed implementation that satisfies all requirements. "
                "The code is optimized and accounts for edge cases. "
                "Production-ready quality including test cases. "
                "Complexity analysis (time and space) is also included."
                f" QUALITY:{quality:.2f}"
            )
        elif quality >= 0.5:
            return (
                f"[Partial answer] {subtask}\n\n"
                "Basic requirements are met but some optimizations are lacking. "
                "Main cases work but edge case handling is incomplete."
                f" QUALITY:{quality:.2f}"
            )
        else:
            return (
                f"[Incomplete answer] {subtask}\n\n"
                "Requirements are not fully understood and the implementation is incomplete. "
                "Contains many bugs and cannot be used as-is."
                f" QUALITY:{quality:.2f}"
            )

    def _make_httpx_mock():
        """httpx mock that returns quality-based response text based on the endpoint URL."""
        mock_http_client = AsyncMock()

        async def _mock_post(url, **kwargs):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            quality = endpoint_quality.get(base, 0.5)
            if quality is None:
                quality = random.uniform(0.0, 1.0)
            subtask = (kwargs.get("json") or {}).get("subtask", "task")
            resp = MagicMock()
            resp.status_code = 200
            resp.text = _quality_response(quality, subtask)
            return resp

        mock_http_client.post = _mock_post
        return mock_http_client

    # 2. Submit tasks in a loop
    for i in range(n_tasks):
        prompt = _TASK_PROMPTS[i % len(_TASK_PROMPTS)]
        req = TaskCreateRequest(prompt=prompt, budget=0.1)
        task = create_task(db, req)

        mock_http_client = _make_httpx_mock()
        with patch("app.services.coordinator.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
            try:
                await run_coordinator(db, task)
            except Exception as exc:
                logger.warning("Task %d failed: %s", i + 1, exc)

        # 3. trust_score snapshot
        db.expire_all()  # Reload latest values from the DB
        snapshot = _snapshot_trust_scores(db, i + 1)
        learning_curve.append(snapshot)
        logger.info("Task %d/%d done. Scores: %s", i + 1, n_tasks, snapshot["agent_trust_scores"])

    result = {"learning_curve": learning_curve}

    # 4. Write to JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("Simulation complete. Output: %s", output_file)
    return result


def run_simulation_sync(
    db: Session | None = None,
    n_tasks: int = 20,
    output_file: str = "simulation_result.json",
) -> dict:
    """
    Synchronous wrapper for run_simulation. Called from tests and CLI.

    Args:
        db: Database session (a production session is created if None)
        n_tasks: Number of tasks to submit
        output_file: Output JSON file path

    Returns:
        Result dict in the format {"learning_curve": [...]}
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        return asyncio.run(run_simulation(db=db, n_tasks=n_tasks, output_file=output_file))
    finally:
        if close_db:
            db.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    run_simulation_sync(n_tasks=n)
