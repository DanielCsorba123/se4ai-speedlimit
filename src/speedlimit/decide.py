"""Decision logic. REQ1 part (backlog Task 5): candidate sweep with monotone guard.

Selection (D7, D25, D33): among candidates <= req1_max_limit, take the highest
whose guarded rate is <= target. If none, take the highest within epsilon of
the lowest guarded rate and flag the target as not reachable.
"""
from __future__ import annotations

from speedlimit.config import Config
from speedlimit.domain import Req1Result, RuleResult, Situation
from speedlimit.features import situation_to_frame
from speedlimit.model import ModelArtefact, baseline_predict, monotone_guard, predict_rate
from speedlimit.rules import evaluate


def _condition(rule: RuleResult) -> str:
    return "dark" if rule.dark else "black_ice"


def select_limit(guarded: dict[int, float], cfg: Config) -> tuple[int, bool]:
    d = cfg.decide
    allowed = {l: r for l, r in guarded.items() if l <= d.req1_max_limit}            # D33
    reachable = [l for l, r in allowed.items() if r <= d.target_rate]
    if reachable:
        return max(reachable), True
    best = min(allowed.values())
    return max(l for l, r in allowed.items() if r <= best + d.unreachable_epsilon), False   # D25


def req1_limit(s: Situation, art: ModelArtefact | None, cfg: Config, rule: RuleResult | None = None,
               baseline: dict | None = None) -> Req1Result:
    rule = rule or evaluate(s, cfg.rules)
    limits = list(cfg.decide.candidate_limits)
    if not rule.req1_active:
        return Req1Result(active=False, limit=cfg.decide.default_limit, rates_raw={}, rates_guarded={},
                          target_reachable=True, source="inactive")

    cond = _condition(rule)
    if art is not None:
        raw = predict_rate(art, situation_to_frame(s, limits, cfg.features))
        source = "model"
        cells = art.cell_counts
    elif baseline is not None:
        raw = baseline_predict(baseline, [cond] * len(limits), limits)
        source = "baseline_table"
        cells = {}
    else:
        raise ValueError("REQ1 needs a model artefact or a baseline table")

    rates_raw = {l: float(r) for l, r in zip(limits, raw)}
    guarded = monotone_guard(rates_raw)                                                # D9
    limit, reachable = select_limit(guarded, cfg)
    extrapolated = tuple(l for l in limits if cells and cells.get((cond, l), 0) == 0)  # D32
    return Req1Result(active=True, limit=limit, rates_raw=rates_raw, rates_guarded=guarded,
                      target_reachable=reachable, source=source, extrapolated=extrapolated)
