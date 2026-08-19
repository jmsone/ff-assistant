"""Survival probability: P(player available at your next pick).

Model: ADP ~ Normal(mu=adp, sigma=stddev). Player "survives" if his actual pick
falls after target_pick. P(survive) = P(X > target_pick) = 1 - Phi((target - mu)/sigma).

Notes:
- Missing stddev falls back to floor value (default 6 picks) so unknown-variance
  players still get a reasonable estimate rather than 0 or 1.
- Already-drafted players get 0 (caller strips them before scoring).
"""
from __future__ import annotations

import math

import pandas as pd

DEFAULT_STDDEV_FLOOR = 6.0
DEFAULT_STDDEV_MISSING = 12.0  # unknown -> assume volatile


def _norm_sf(x: float) -> float:
    """Survival function of standard normal: 1 - Phi(x)."""
    return 0.5 * math.erfc(x / math.sqrt(2))


def survival_prob(adp: float, stddev: float, target_pick: float) -> float:
    """P(player still available at target_pick, given ADP dist)."""
    if pd.isna(adp):
        return 0.0
    sigma = stddev if (stddev and not pd.isna(stddev)) else DEFAULT_STDDEV_MISSING
    sigma = max(sigma, DEFAULT_STDDEV_FLOOR)
    z = (target_pick - adp) / sigma
    return _norm_sf(z)


def add_survival(
    df: pd.DataFrame,
    target_pick: int,
    adp_col: str = "adp",
    stddev_col: str = "stddev",
    out_col: str = "p_survive",
) -> pd.DataFrame:
    """Add P(survive to target_pick) column. Vectorized."""
    out = df.copy()
    adp = pd.to_numeric(out[adp_col], errors="coerce")
    if stddev_col in out.columns:
        sigma = pd.to_numeric(out[stddev_col], errors="coerce").fillna(DEFAULT_STDDEV_MISSING)
    else:
        sigma = pd.Series([DEFAULT_STDDEV_MISSING] * len(out), index=out.index)
    sigma = sigma.clip(lower=DEFAULT_STDDEV_FLOOR)
    import numpy as np
    z = ((target_pick - adp) / sigma).to_numpy()
    _erfc = np.frompyfunc(math.erfc, 1, 1)
    p = 0.5 * _erfc(z / math.sqrt(2)).astype(float)
    p = pd.Series(p, index=out.index).where(adp.notna(), 0.0)
    out[out_col] = p
    return out
