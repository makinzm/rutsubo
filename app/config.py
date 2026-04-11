"""
Application settings aggregation module.

Loads configuration from environment variables or default values.
"""

import os


# ---------------------------------------------------------------------------
# ε-greedy simulated annealing settings
# ---------------------------------------------------------------------------

# Initial epsilon value (exploration rate when task count is 0)
EPSILON_INITIAL: float = float(os.getenv("EPSILON_INITIAL", "0.3"))

# Decay coefficient (larger values decay faster)
EPSILON_LAMBDA: float = float(os.getenv("EPSILON_LAMBDA", "0.01"))

# Minimum epsilon value (ensures exploration never fully stops)
EPSILON_MIN: float = float(os.getenv("EPSILON_MIN", "0.05"))
