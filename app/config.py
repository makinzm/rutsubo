"""
アプリケーション設定の集約モジュール。

環境変数またはデフォルト値から設定を読み込む。
"""

import os


# ---------------------------------------------------------------------------
# ε-greedy 焼きなまし設定
# ---------------------------------------------------------------------------

# εの初期値（タスク数0のときの探索率）
EPSILON_INITIAL: float = float(os.getenv("EPSILON_INITIAL", "0.3"))

# 減衰係数（大きいほど速く減衰する）
EPSILON_LAMBDA: float = float(os.getenv("EPSILON_LAMBDA", "0.01"))

# εの最小値（完全に収束しないよう保証）
EPSILON_MIN: float = float(os.getenv("EPSILON_MIN", "0.05"))
