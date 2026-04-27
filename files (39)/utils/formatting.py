"""
utils/formatting.py
───────────────────
Number / percentage formatters and variance colour helpers
used across multiple tabs.
"""

import numpy as np


def fmt_num(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        v = float(v)
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:,.2f}M"
        if abs(v) >= 1_000:
            return f"{v/1_000:,.1f}K"
        return f"{v:,.0f}"
    except Exception:
        return str(v)


def fmt_num_full(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return str(v)


def fmt_pct(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        return f"{float(v)*100:+.2f}%"
    except Exception:
        return str(v)


def variance_color_class(v, favorable_is_lower: bool = True) -> str:
    try:
        f = float(v)
        if f == 0:
            return "neutral"
        if favorable_is_lower:
            return "fav" if f < 0 else "adv"
        return "fav" if f > 0 else "adv"
    except Exception:
        return "neutral"
