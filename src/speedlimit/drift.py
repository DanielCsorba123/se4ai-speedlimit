"""Retraining check: does year N+1 differ from the training year N? (D13, slide 19)

    python -m speedlimit.drift --config config.yaml

Per feature: two-sample KS test and standardised mean shift; a feature drifts
when both fire (p < alpha and |mean shift| > mean_shift_sd standard deviations).
Verdict: retrain if any core feature drifts. Also reports whether the two
readings files are row-for-row identical (C21).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from speedlimit.config import DriftConfig, load_config
from speedlimit.features import FEATURES, build_features
from speedlimit.io_load import READING_COLS, load_readings

CORE = ["log_lux", "water", "temp", "traffic", "speed_limit"]


@dataclass
class DriftReport:
    per_feature: pd.DataFrame
    retrain: bool
    reason: str
    identical_rows: int | None = None
    duplicate_dataset: bool = False
    drifting: list[str] = field(default_factory=list)


def _hash(df: pd.DataFrame) -> str:
    cols = [c for c in ("day", "hour", "sensor", "value") if c in df.columns]
    canon = df[cols].sort_values(cols).to_csv(index=False)
    return hashlib.sha256(canon.encode()).hexdigest()


def drift_report(ref: pd.DataFrame, new: pd.DataFrame, features: list[str], cfg: DriftConfig,
                 ref_raw: pd.DataFrame | None = None, new_raw: pd.DataFrame | None = None) -> DriftReport:
    rows = []
    for f in features:
        a, b = ref[f].astype(float).dropna(), new[f].astype(float).dropna()
        ks = ks_2samp(a, b)
        sd = a.std()
        shift = abs(b.mean() - a.mean()) / sd if sd > 0 else (0.0 if b.mean() == a.mean() else np.inf)
        rows.append({"feature": f, "core": f in CORE, "ks_stat": float(ks.statistic), "p_value": float(ks.pvalue),
                     "mean_ref": float(a.mean()), "mean_new": float(b.mean()), "shift_sd": float(shift),
                     "drift": bool(ks.pvalue < cfg.alpha and shift > cfg.mean_shift_sd)})
    per = pd.DataFrame(rows).set_index("feature")
    drifting = per.index[per.drift].tolist()
    core_drift = per.index[per.drift & per.core].tolist()

    identical, duplicate = None, False
    if ref_raw is not None and new_raw is not None:
        if len(ref_raw) == len(new_raw):
            cols = [c for c in READING_COLS if c in ref_raw.columns and c in new_raw.columns] or list(ref_raw.columns)
            a, b = ref_raw[cols].reset_index(drop=True), new_raw[cols].reset_index(drop=True)
            identical = int((a.eq(b) | (a.isna() & b.isna())).all(axis=1).sum())
        else:
            identical = 0
        duplicate = identical == len(ref_raw) and _hash(ref_raw) == _hash(new_raw)

    if core_drift:
        reason = f"Core feature(s) drifted: {', '.join(core_drift)}. Retrain on the new data."
    else:
        reason = "No core feature drifted"
        reason += f" (non-core drift: {', '.join(drifting)})." if drifting else "."
    if duplicate:
        reason += " Warning: the new readings are identical to the training year (duplicate dataset, C21)."
    return DriftReport(per_feature=per, retrain=bool(core_drift), reason=reason, identical_rows=identical,
                       duplicate_dataset=duplicate, drifting=drifting)


def verdict(report: DriftReport) -> Literal["retrain", "no_retrain"]:
    return "retrain" if report.retrain else "no_retrain"


def _markdown(rep: DriftReport, cfg: DriftConfig, files: tuple[str, str]) -> str:
    table = "\n".join(
        f"| {f} | {'yes' if r.core else ''} | {r.ks_stat:.3f} | {r.p_value:.3g} | {r.mean_ref:.3f} | {r.mean_new:.3f} | "
        f"{r.shift_sd:.2f} | {'**yes**' if r.drift else 'no'} |" for f, r in rep.per_feature.iterrows())
    return f"""# Drift report · year N vs year N+1

Generated {datetime.now():%Y-%m-%d %H:%M} by `python -m speedlimit.drift` (D13).

- Reference: `{files[0]}`
- New: `{files[1]}`
- Rule: a feature drifts when KS p < {cfg.alpha} **and** the mean moved more than {cfg.mean_shift_sd} standard
  deviations. Retrain if any core feature ({', '.join(CORE)}) drifts.

## Verdict: **{verdict(rep)}**

{rep.reason}

Identical rows: {rep.identical_rows if rep.identical_rows is not None else 'n/a'}.

| Feature | Core | KS D | p | Mean N | Mean N+1 | Shift (sd) | Drift |
|---|---|---|---|---|---|---|---|
{table}

## What this means
{"The N+1 file is a copy of year N (see figure F10), so this check cannot detect anything. "
 "The module is ready for real N+1 data: rerun the command with the new file." if rep.duplicate_dataset else
 "See the table for the features that moved."}
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Year N vs N+1 drift / retraining check")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--new", default=None, help="readings file of the new year (default: config readings_n1_file)")
    ap.add_argument("--reports-dir", default=None)
    ap.add_argument("--evidence", default="docs/evidence/drift_report.md")
    args = ap.parse_args(argv)
    cfg = load_config(Path(args.config))
    from speedlimit.cli_train import prepare_hourly   # local import keeps drift importable without training deps

    new_path = Path(args.new) if args.new else cfg.paths.readings_n1_file
    ref_h, _ = prepare_hourly(cfg)
    new_h, _ = prepare_hourly(cfg, readings_path=new_path)
    ref_x = build_features(ref_h[ref_h.complete], cfg.features)
    new_x = build_features(new_h[new_h.complete], cfg.features)
    rep = drift_report(ref_x, new_x, FEATURES, cfg.drift,
                       ref_raw=load_readings(cfg.paths.readings_file)[READING_COLS],
                       new_raw=load_readings(new_path)[READING_COLS])

    reports = Path(args.reports_dir) if args.reports_dir else cfg.paths.reports_dir
    reports.mkdir(parents=True, exist_ok=True)
    out = {"verdict": verdict(rep), "reason": rep.reason, "identical_rows": rep.identical_rows,
           "duplicate_dataset": rep.duplicate_dataset, "drifting": rep.drifting,
           "alpha": cfg.drift.alpha, "mean_shift_sd": cfg.drift.mean_shift_sd,
           "per_feature": rep.per_feature.reset_index().to_dict(orient="records")}
    (reports / "drift_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    ev = Path(args.evidence)
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text(_markdown(rep, cfg.drift, (cfg.paths.readings_file.name, new_path.name)), encoding="utf-8")
    print(f"drift verdict: {verdict(rep)} - {rep.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
