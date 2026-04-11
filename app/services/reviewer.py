"""
Reviewer service — subtask evaluation using LLM-as-a-Judge.

Prompt design incorporating an asymmetric loss function:
- Misses (overlooking important issues) carry a non-linearly heavy penalty → evaluate strictly
- False positives (flagging no-issue results as problematic) carry a mild penalty
"""

import json
import logging
import re

from app.services import llm as _llm

logger = logging.getLogger(__name__)

# Matches the outermost {...} block that contains "score" — handles nested braces in reason strings
_JSON_RE = re.compile(r'\{(?:[^{}]|\{[^{}]*\})*"score"(?:[^{}]|\{[^{}]*\})*\}', re.DOTALL)

# Weight per risk_level (multiplier for asymmetric loss based on task risk level)
# - high:   miss penalty is 3x heavier
# - medium: miss penalty is 2x heavier
# - low:    standard (1x)
_RISK_WEIGHT = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
}


def _build_system_prompt(risk_level: str) -> str:
    """
    Build an evaluation prompt tailored to the given risk_level.

    Embeds asymmetric loss function parameters into the prompt so that
    the LLM evaluator can score with the risk level in mind.

    Args:
        risk_level: Task risk level (low/medium/high)

    Returns:
        System prompt string
    """
    risk = risk_level if risk_level in _RISK_WEIGHT else "medium"
    risk_weight = _RISK_WEIGHT[risk]

    return (
        "You are a task quality evaluation AI. Evaluate the subtask execution result of a worker agent.\n\n"
        "[Evaluation criteria]\n"
        "- Does the result satisfy the task requirements?\n"
        "- Quality and accuracy of the result\n"
        "- Are there any overlooked critical issues? (misses carry a severe penalty)\n\n"
        "[Asymmetric loss principle]\n"
        f"Current risk level: {risk} (miss penalty multiplier: {risk_weight}x)\n"
        "- Overlooking a critical issue: non-linearly heavy penalty (score drops sharply)\n"
        f"  * At risk level {risk}, misses are weighted {risk_weight}x heavier\n"
        "- False positive (flagging no-issue as issue): mild penalty\n\n"
        "Return JSON only.\n"
        'Example: {"score": 0.85, "reason": "Requirements mostly met but minor issues found"}'
    )


async def evaluate_subtask(prompt: str, result: str, risk_level: str = "medium") -> float:
    """
    Evaluate a subtask result using the Claude API and return a score from 0.0 to 1.0.

    Asymmetric loss function considerations:
    - When risk_level is high, misses (overlooking critical issues) carry a 3x penalty
    - When risk_level is medium, misses carry a 2x penalty
    - When risk_level is low, standard (1x)
    - False positives (flagging no-issue as issue) are treated leniently

    Args:
        prompt: Subtask content (what needs to be accomplished)
        result: Result text returned by the worker agent
        risk_level: Task risk level (low/medium/high)

    Returns:
        Score from 0.0 to 1.0 (1.0 is highest quality)
    """
    system = _build_system_prompt(risk_level)
    user_message = (
        f"[Subtask]\n{prompt}\n\n"
        f"[Execution result]\n{result}"
    )

    try:
        raw = _llm.complete(system, user_message, max_tokens=200)
        # Handle Markdown code fences (```json\n...\n```) or surrounding prose.
        # 1. Strip code fences first
        candidate = re.sub(r"```(?:json)?\s*", "", raw).strip()
        # 2. If not a bare JSON object, extract the first {...} containing "score"
        if not candidate.startswith("{"):
            m = _JSON_RE.search(candidate)
            if m:
                candidate = m.group(0)
        data = json.loads(candidate)
        score = float(data.get("score", 0.5))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning("Failed to parse reviewer response: %s | raw=%r", exc, raw[:200])
        score = 0.5  # Default on parse failure

    # Clamp to 0.0–1.0
    return max(0.0, min(1.0, score))
