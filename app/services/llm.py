"""
LLM client abstraction layer.

Switch implementations via the LLM_BACKEND environment variable:
  - "api"  : anthropic SDK (requires ANTHROPIC_API_KEY)
  - "cli"  : claude CLI subprocess (reuses Claude Code authentication)
  - "mock" : mock responses (for tests and simulation)
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

LLM_BACKEND = os.getenv("LLM_BACKEND", "api")


def complete(system: str, user: str, max_tokens: int = 500) -> str:
    """
    Send a message to the LLM and return the response text.

    Args:
        system: System prompt
        user: User message
        max_tokens: Maximum number of tokens (only effective for the api backend)

    Returns:
        Response text from the LLM
    """
    backend = LLM_BACKEND

    if backend == "cli":
        return _complete_cli(system, user)
    elif backend == "mock":
        return _complete_mock(system, user)
    else:
        return _complete_api(system, user, max_tokens)


def _complete_api(system: str, user: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def _complete_cli(system: str, user: str) -> str:
    """Retrieve a response via the claude CLI subprocess."""
    prompt = f"{system}\n\n{user}"
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI error: {result.stderr.strip()}")
    return result.stdout.strip()


def _complete_mock(system: str, user: str) -> str:
    """
    Return a mock response (for tests and simulation).

    Determines the task type from the system prompt content and returns appropriate JSON.
    If the result text contains a "QUALITY:<float>" tag, that value is used as the score.
    """
    import re
    if "difficulty" in system and "risk_level" in system:
        # Difficulty/risk assessment
        return json.dumps({"difficulty": "medium", "risk_level": "low"})
    elif "agent_name" in system or "subtask" in system.lower():
        # Subtask decomposition (extract agent names from the user message)
        agents = []
        for line in user.split("\n"):
            if line.startswith("- ") and ":" in line:
                name = line[2:].split(":")[0].strip()
                agents.append({"agent_name": name, "subtask": f"Subtask for {name}: {user[:50]}"})
        return json.dumps(agents if agents else [])
    elif "score" in system or "quality" in system.lower():
        # Subtask evaluation — use the quality tag from the result text if present
        quality_match = re.search(r"QUALITY:([\d.]+)", user)
        score = float(quality_match.group(1)) if quality_match else 0.75
        return json.dumps({"score": score, "reason": "mock evaluation"})
    else:
        return json.dumps({"result": "mock response"})
