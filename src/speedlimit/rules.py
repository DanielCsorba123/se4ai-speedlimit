"""SPEC1 / SPEC2 condition rules (D5): deterministic code, never learned."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from speedlimit.config import RulesConfig
from speedlimit.domain import RuleResult, Situation


def is_dark(lux_mean: float, cfg: RulesConfig) -> bool:
    """SPEC1: dark when illuminance is below 500 millilux (strict)."""
    return bool(lux_mean < cfg.dark_lux_threshold)


def is_black_ice(water_mean: float, temp_mean: float, cfg: RulesConfig) -> bool:
    """SPEC2: more than 1000 um water and below 0 degC (both strict)."""
    return bool(water_mean > cfg.ice_water_um_threshold and temp_mean < cfg.ice_temp_c_threshold)


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def evaluate(s: Situation, cfg: RulesConfig) -> RuleResult:
    """Apply SPEC1/SPEC2; a missing input counts as the condition being met (D30)."""
    missing = tuple(n for n in ("lux", "water_um", "temp_c") if _missing(getattr(s, n)))
    dark = True if "lux" in missing else is_dark(s.lux, cfg)
    if "water_um" in missing or "temp_c" in missing:
        ice = True
    else:
        ice = is_black_ice(s.water_um, s.temp_c, cfg)
    return RuleResult(dark=dark, black_ice=ice, missing_inputs=missing)


def label_conditions(hourly: pd.DataFrame, cfg: RulesConfig) -> pd.DataFrame:
    """Add dark, black_ice, condition (dark > black_ice > normal) and C17 flag."""
    out = hourly.copy()
    out["dark"] = out["lux"] < cfg.dark_lux_threshold
    out["black_ice"] = (out["water"] > cfg.ice_water_um_threshold) & (out["temp"] < cfg.ice_temp_c_threshold)
    out["condition"] = np.where(out["dark"], "dark", np.where(out["black_ice"], "black_ice", "normal"))
    out["unexplained_reduction"] = (out["condition"] == "normal") & (out["speed_limit"] < 80)   # C17, D10
    return out
