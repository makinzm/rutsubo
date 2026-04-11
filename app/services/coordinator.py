"""
Coordinator service.

Responsibilities:
1. Assess task difficulty and risk level using the Claude API
2. Select agents using ε-greedy (simulated annealing)
3. Decompose the task into subtasks using the Claude API
4. Send subtasks asynchronously to each agent's endpoint
5. Record evaluation results as causal chain entries
"""

import asyncio
import json
import logging
import math
import random

import httpx
from sqlalchemy.orm import Session

from app.config import EPSILON_INITIAL, EPSILON_LAMBDA, EPSILON_MIN
from app.services import llm as _llm
from app.models.agent import Agent
from app.models.causal_chain import CausalChainEntry
from app.models.task import SubTask, Task
from app.services import agent_service
from app.services.payment import distribute_rewards
from app.services.reviewer import evaluate_subtask
from app.services.task_service import update_task_assessment, update_task_status

logger = logging.getLogger(__name__)

# Maximum number of agents to select
MAX_AGENTS = 3
# Valid values for difficulty and risk level
_VALID_LEVELS = {"low", "medium", "high"}
# Claude API model name
_CLAUDE_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# ε-greedy simulated annealing
# ---------------------------------------------------------------------------


def compute_epsilon(n_tasks: int) -> float:
    """
    Compute epsilon based on the number of completed tasks (simulated annealing).

    ε = max(EPSILON_MIN, EPSILON_INITIAL * exp(-EPSILON_LAMBDA * n_tasks))

    Args:
        n_tasks: Number of tasks completed so far

    Returns:
        Epsilon value in the range [EPSILON_MIN, EPSILON_INITIAL]
    """
    eps = EPSILON_INITIAL * math.exp(-EPSILON_LAMBDA * n_tasks)
    return max(EPSILON_MIN, eps)


# ---------------------------------------------------------------------------
# ε-greedy agent selection
# ---------------------------------------------------------------------------


def select_agents(agents: list[Agent], epsilon: float | None = None) -> list[Agent]:
    """
    Select agents using ε-greedy.

    - With probability ε: random selection (exploration)
    - With probability 1-ε: top agents by trust_score (exploitation)
    - Number selected: min(len(agents), MAX_AGENTS)
    - If epsilon is None, the default value (EPSILON_INITIAL) is used

    Args:
        agents: List of candidate agents
        epsilon: Exploration rate (0.0–1.0). Uses default if None.

    Returns:
        List of selected agents
    """
    n = min(len(agents), MAX_AGENTS)
    if n == 0:
        return []

    eps = epsilon if epsilon is not None else EPSILON_INITIAL

    if random.random() < eps:
        # Exploration: pick n agents at random
        return random.sample(agents, n)
    else:
        # Exploitation: top n agents sorted by trust_score descending
        return sorted(agents, key=lambda a: a.trust_score, reverse=True)[:n]


# ---------------------------------------------------------------------------
# Claude API — difficulty and risk level assessment
# ---------------------------------------------------------------------------


def assess_task(prompt: str) -> dict[str, str]:
    """
    Use the LLM to assess the task's difficulty and risk_level.

    Returns:
        {"difficulty": "low"|"medium"|"high", "risk_level": "low"|"medium"|"high"}
    """
    system = (
        "You are a task assessment AI. Analyze the user's task and return "
        "difficulty (low/medium/high) and risk_level (low/medium/high) "
        "as JSON only. "
        'Example: {"difficulty": "medium", "risk_level": "low"}'
    )
    raw = _llm.complete(system, f"Task: {prompt}", max_tokens=100)
    try:
        candidate = raw.strip()
        if not candidate.startswith("{"):
            # Strip Markdown code fences or leading text
            import re as _re
            m = _re.search(r'\{[^{}]*"difficulty"[^{}]*\}', candidate, _re.DOTALL)
            if m:
                candidate = m.group(0)
        data = json.loads(candidate)
    except json.JSONDecodeError:
        data = {}

    difficulty = data.get("difficulty", "medium")
    risk_level = data.get("risk_level", "medium")
    # Fall back to "medium" for invalid values
    if difficulty not in _VALID_LEVELS:
        difficulty = "medium"
    if risk_level not in _VALID_LEVELS:
        risk_level = "medium"

    return {"difficulty": difficulty, "risk_level": risk_level}


# ---------------------------------------------------------------------------
# Claude API — subtask decomposition
# ---------------------------------------------------------------------------


def decompose_task(prompt: str, agents: list[Agent]) -> list[dict[str, str]]:
    """
    Decompose a task into subtasks for each agent.

    Returns:
        [{"agent_name": "...", "subtask": "..."}, ...]
    """
    agent_profiles = "\n".join(
        f"- {a.name}: {a.description}" for a in agents
    )
    system = (
        "You are a task decomposition AI. Break the user's task into subtasks "
        "for each specified agent. Return a JSON array only. "
        'Example: [{"agent_name": "AgentA", "subtask": "..."}]'
    )
    user_message = (
        f"Task: {prompt}\n\n"
        f"Available agents:\n{agent_profiles}"
    )
    raw = _llm.complete(system, user_message, max_tokens=500)
    try:
        candidate = raw.strip()
        if not candidate.startswith("["):
            # Strip Markdown code fences or leading text and extract the JSON array
            import re as _re
            m = _re.search(r'\[.*\]', candidate, _re.DOTALL)
            if m:
                candidate = m.group(0)
        subtasks = json.loads(candidate)
        if not isinstance(subtasks, list):
            raise ValueError("expected list")
    except (json.JSONDecodeError, ValueError):
        # Fallback: assign the same task to all agents
        subtasks = [{"agent_name": a.name, "subtask": prompt} for a in agents]

    return subtasks


# ---------------------------------------------------------------------------
# Causal chain entry recording
# ---------------------------------------------------------------------------


def _record_causal_entry(
    db: Session,
    *,
    task_id: str,
    layer: str,
    agent_id: str | None = None,
    score: float | None = None,
    note: str | None = None,
) -> CausalChainEntry:
    """
    Save a causal chain entry to the database and return it.

    Args:
        db: Database session
        task_id: ID of the target task
        layer: Layer name (task_definition / coordinator / worker / reviewer)
        agent_id: Agent ID (for the worker layer)
        score: Evaluation score (0.0–1.0)
        note: Description of the issue (optional)

    Returns:
        The saved CausalChainEntry
    """
    entry = CausalChainEntry(
        task_id=task_id,
        layer=layer,
        agent_id=agent_id,
        score=score,
        note=note,
    )
    db.add(entry)
    db.commit()
    return entry


# ---------------------------------------------------------------------------
# Dispatching to worker agents
# ---------------------------------------------------------------------------


async def _send_subtask(
    db: Session,
    subtask: SubTask,
    endpoint: str,
    subtask_prompt: str,
) -> None:
    """Send a subtask asynchronously to the agent's endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            resp = await http_client.post(
                f"{endpoint.rstrip('/')}/execute",
                json={"subtask": subtask_prompt},
            )
            subtask.result = resp.text
            subtask.status = "completed"
        except Exception as exc:
            logger.warning("Failed to send subtask %s: %s", subtask.subtask_id, exc)
            subtask.result = str(exc)
            subtask.status = "failed"
        finally:
            db.commit()


# ---------------------------------------------------------------------------
# Coordinator main flow
# ---------------------------------------------------------------------------


async def run_coordinator(db: Session, task: Task) -> None:
    """
    Accept a task and execute: difficulty assessment → agent selection → subtask decomposition → dispatch.
    Intended to be called as a background task.
    """
    try:
        # 1. Assess difficulty and risk level
        assessment = assess_task(task.prompt)
        update_task_assessment(
            db, task,
            difficulty=assessment["difficulty"],
            risk_level=assessment["risk_level"],
        )

        # 2. Fetch registered agents and select via ε-greedy (simulated annealing)
        all_agents = agent_service.list_agents(db)
        n_completed = (
            db.query(Task)
            .filter(Task.status == "completed")
            .count()
        )
        epsilon = compute_epsilon(n_completed)
        selected = select_agents(all_agents, epsilon=epsilon)

        # 3. Decompose into subtasks
        subtask_defs = decompose_task(task.prompt, selected)

        # Mapping of agent_name → Agent
        agent_map = {a.name: a for a in selected}

        # 4. Create SubTask records and dispatch asynchronously
        send_tasks = []
        for st_def in subtask_defs:
            agent_name = st_def.get("agent_name", "")
            agent = agent_map.get(agent_name)
            if agent is None:
                continue
            subtask = SubTask(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                prompt=st_def.get("subtask", task.prompt),
            )
            db.add(subtask)
            db.commit()
            db.refresh(subtask)
            send_tasks.append(
                _send_subtask(db, subtask, agent.endpoint, subtask.prompt)
            )

        # Dispatch to all agents asynchronously
        await asyncio.gather(*send_tasks, return_exceptions=True)

        # 5. Evaluate each subtask result with the reviewer
        completed_subtasks = (
            db.query(SubTask)
            .filter(SubTask.task_id == task.task_id, SubTask.status == "completed")
            .all()
        )

        # Mapping of agent_id → scores (averaged if multiple subtasks)
        agent_scores: dict[str, list[float]] = {}
        for subtask in completed_subtasks:
            score = await evaluate_subtask(
                prompt=subtask.prompt,
                result=subtask.result or "",
                risk_level=task.risk_level or "medium",
            )
            subtask.score = score
            # TODO: Improve design to commit in bulk after all subtasks are evaluated.
            # Currently commits per subtask; a mid-run error may leave only partial scores saved.
            # Acceptable for the MVP stage.
            db.commit()

            # Record as a worker-layer causal chain entry
            _record_causal_entry(
                db,
                task_id=task.task_id,
                layer="worker",
                agent_id=subtask.agent_id,
                score=score,
            )

            if subtask.agent_id not in agent_scores:
                agent_scores[subtask.agent_id] = []
            agent_scores[subtask.agent_id].append(score)

        # Average scores per agent
        avg_scores = {
            agent_id: sum(scores) / len(scores)
            for agent_id, scores in agent_scores.items()
        }

        # 6. Distribute budget proportional to scores
        wallets = {
            a.agent_id: a.wallet_address
            for a in selected
            if a.agent_id in avg_scores
        }
        rewards = await distribute_rewards(
            task_id=task.task_id,
            scores=avg_scores,
            wallets=wallets,
            budget=task.budget,
        )

        # Record reward on each subtask
        for subtask in completed_subtasks:
            subtask.reward = rewards.get(subtask.agent_id)
            db.commit()

        # 7. Update each agent's trust_score
        for agent_id, score in avg_scores.items():
            agent_service.update_trust_score(db, agent_id, eval_score=score)

        update_task_status(db, task, "completed")

    except Exception as exc:
        logger.error("Coordinator failed for task %s: %s", task.task_id, exc)
        update_task_status(db, task, "failed")
