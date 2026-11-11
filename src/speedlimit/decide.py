"""Decision logic: REQ1 candidate sweep with monotone guard (Task 5) and the router / combiner (Task 7).

Selection (D7, D25, D33): among candidates <= req1_max_limit, take the highest
whose guarded rate is <= target. If none, take the highest within epsilon of
the lowest guarded rate and flag the target as not reachable.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from speedlimit.config import Config
from speedlimit.domain import AQSummary, Decision, Req1Result, Req2Result, RuleResult, Situation
from speedlimit.llm_advisor import advise, manual_limit
from speedlimit.features import situation_to_frame
from speedlimit.model import ModelArtefact, baseline_predict, monotone_guard, predict_rate
from speedlimit.rules import evaluate


def _condition(rule: RuleResult) -> str:
    return "dark" if rule.dark else "black_ice"


def guard_candidates(rates_raw: dict[int, float], cfg: Config) -> dict[int, float]:
    """D9 over the REQ1 candidates only (<= req1_max_limit, D33).

    Limits above the cap (80, never chosen and without dark/ice training data, D32) keep their raw
    value for display and do not feed the running minimum - otherwise an extrapolated 80 km/h
    prediction would pull 70..40 down and fake a reachable target.
    """
    cap = cfg.decide.req1_max_limit
    guarded = monotone_guard({l: r for l, r in rates_raw.items() if l <= cap})
    guarded |= {l: r for l, r in rates_raw.items() if l > cap}
    return dict(sorted(guarded.items()))


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
    table = baseline if baseline is not None else (art.baseline_table if art is not None else None)
    if art is not None and not rule.missing_inputs:
        raw = predict_rate(art, situation_to_frame(s, limits, cfg.features))
        source = "model"
        cells = art.cell_counts
    elif table:
        # no model, or an input is missing (D30): the network cannot run on NaN, the per-condition
        # baseline still gives a fail-safe decision
        raw = baseline_predict(table, [cond] * len(limits), limits)
        source = "baseline_table"
        cells = {}
    else:
        raise ValueError("REQ1 needs a model artefact or a baseline table")

    rates_raw = {l: float(r) for l, r in zip(limits, raw)}
    guarded = guard_candidates(rates_raw, cfg)                                         # D9, D33
    limit, reachable = select_limit(guarded, cfg)
    extrapolated = tuple(l for l in limits if cells and cells.get((cond, l), 0) == 0)  # D32
    return Req1Result(active=True, limit=limit, rates_raw=rates_raw, rates_guarded=guarded,
                      target_reachable=reachable, source=source, extrapolated=extrapolated)


# --- router + combiner (backlog Task 7, D16) --------------------------------------------

@dataclass
class RuntimeContext:
    cfg: Config
    art: ModelArtefact | None = None
    baseline: dict | None = None
    aq_summary: AQSummary | None = None
    manual_aqi: float | None = None          # D26 step 2 / D31
    llm_client: object | None = None
    llm_log: Path | None = None


def _explain(final: int, reasons: list[str], rule: RuleResult, r1: Req1Result, r2: Req2Result) -> str:
    if reasons == ["REQ3"]:
        return "No reason to reduce: daylight, no black-ice danger, air quality not poor. Limit stays 80 km/h (REQ3)."
    parts = []
    if r1.active:
        cond = " and ".join(c for c, on in (("dark", rule.dark), ("black-ice danger", rule.black_ice)) if on)
        rate = r1.rates_guarded.get(r1.limit)
        target = "target <= 1/h reached" if r1.target_reachable else "target <= 1/h NOT reachable"
        parts.append(f"REQ1 ({cond}): {r1.limit} km/h, predicted {rate:.2f} near-accidents/h, {target}"
                     if rate is not None else f"REQ1 ({cond}): {r1.limit} km/h")
    if r2.limit < 80 or r2.source in ("llm", "manual"):
        parts.append(f"REQ2 (air, {r2.source}): {r2.limit} km/h")
    return f"Limit {final} km/h set by {' + '.join(reasons)}. " + "; ".join(parts) + "."


def combine(rule: RuleResult, r1: Req1Result, r2: Req2Result, model_version: str | None = None,
            default_limit: int = 80) -> Decision:
    """D16: the most restrictive reason wins; ties list every determining reason."""
    candidates = {"REQ1": r1.limit if r1.active else default_limit, "REQ2": r2.limit}
    final = min([default_limit, *candidates.values()])
    reasons = [k for k, v in candidates.items() if v == final] if final < default_limit else ["REQ3"]
    return Decision(limit=final, winning_reasons=reasons, rule=rule, req1=r1, req2=r2,
                    explanation=_explain(final, reasons, rule, r1, r2), model_version=model_version)


def decide(s: Situation, ctx: RuntimeContext) -> Decision:
    cfg = ctx.cfg
    rule = evaluate(s, cfg.rules)
    r1 = req1_limit(s, ctx.art, cfg, rule=rule, baseline=ctx.baseline)
    if ctx.manual_aqi is not None:
        r2 = manual_limit(ctx.manual_aqi, cfg)
    else:
        r2 = advise(ctx.aq_summary, cfg, client=ctx.llm_client, log_path=ctx.llm_log)
    d = combine(rule, r1, r2, model_version=ctx.art.version if ctx.art else None,
                default_limit=cfg.decide.default_limit)
    return dataclasses.replace(d, situation=s, decided_at=datetime.now())
