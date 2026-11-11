"""Training stage CLI: raw CSVs -> cleaned hourly table -> MLP ensemble artefact + model card.

    python -m speedlimit.cli_train --config config.yaml
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from speedlimit.cleaning import CleaningReport, clean_readings, join_accidents, to_hourly
from speedlimit.config import Config, load_config
from speedlimit.features import FEATURES, build_features
from speedlimit.io_load import load_accidents, load_readings, load_sensors
from speedlimit.decide import select_limit
from speedlimit.model import (baseline_predict, baseline_table, evaluate, monotone_guard, predict_rate, save,
                              split_by_day, train)
from speedlimit.rules import label_conditions

CONDITIONS = ["dark", "black_ice", "normal"]


def prepare_hourly(cfg: Config, readings_path: Path | None = None) -> tuple[pd.DataFrame, CleaningReport]:
    """Load, clean, aggregate, join accidents and label conditions."""
    p = cfg.paths
    sensors = load_sensors(p.sensors_file, p.sensor_types_file)
    readings, report = clean_readings(load_readings(readings_path or p.readings_file), sensors, cfg.cleaning)
    hourly = to_hourly(readings, cfg.cleaning.limit_carry_forward_h)
    hourly = join_accidents(hourly, load_accidents(p.accidents_file))
    return label_conditions(hourly, cfg.rules), report


def _data_hash(cfg: Config) -> str:
    h = hashlib.sha256()
    p = cfg.paths
    for f in (p.readings_file, p.accidents_file, p.sensors_file, p.sensor_types_file):
        h.update(Path(f).read_bytes())
    return h.hexdigest()


def _version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
    except Exception:
        sha = "nogit"
    return f"{datetime.now():%Y%m%d-%H%M}-{sha}"


def _sweep(art, hourly: pd.DataFrame, cfg: Config) -> np.ndarray:
    """Raw predicted rate for every hour x candidate limit -> array (hours, limits)."""
    X = build_features(hourly, cfg.features)
    cols = []
    for lim in cfg.decide.candidate_limits:
        Xl = X.copy()
        Xl["speed_limit"] = float(lim)
        cols.append(predict_rate(art, Xl))
    return np.column_stack(cols)


def _card(art, metrics: dict, cfg: Config, report: CleaningReport) -> str:
    m, d = metrics, metrics["dark_ice_only"]
    calib = "\n".join(f"| {c['bin'] + 1} | {c['mean_pred']:.3f} | {c['mean_obs']:.3f} | {c['n']} |"
                      for c in m["calibration"])
    cells = "\n".join(f"| {c} | " + " | ".join(str(art.cell_counts.get((c, l), 0)) for l in cfg.decide.candidate_limits)
                      + " |" for c in CONDITIONS)
    verdict = ("beats" if m["poisson_dev"] < m["poisson_dev_baseline"] else "does **not** beat")
    return f"""# Model card · {art.version}

**Intended use:** predict near-accidents per hour for a candidate speed limit, used **only** when it is dark
or there is black-ice danger (REQ1, D5). Not used in normal conditions (REQ3).

## Training data
- Course data V100, **January only** ({len(art.train_days)} train days {art.train_days[0]}-{art.train_days[-1]},
  {len(art.test_days)} test days {art.test_days[0]}-{art.test_days[-1]}, split by day, D12).
- All complete hours (D27); target = near-accidents per hour (D6); accident hour shifted by -1 (D1).
- Data hash `{art.data_hash[:16]}…`. Cleaning events: {', '.join(f'{r}={n}' for r, n, _ in report.events)}.

## Model
Ensemble of {len(art.estimators)} MLPs {tuple(cfg.model.hidden_layer_sizes)}, alpha {cfg.model.alpha}, log1p target,
smearing k = {art.smearing_k:.3f}. Features ({len(FEATURES)}): {', '.join(FEATURES)}.

## Results on test days (all hours, n = {m['n']})
| Metric | Model | Baseline (condition x limit) |
|---|---|---|
| MAE | {m['mae']:.3f} | {m['mae_baseline']:.3f} |
| Poisson deviance | {m['poisson_dev']:.3f} | {m['poisson_dev_baseline']:.3f} |
| RMSE | {m['rmse']:.3f} | - |

Skill vs baseline: **{m['skill']:+.3f}** (the model {verdict} the baseline). Predicted/observed total: {m['sum_ratio']:.3f}.

### Dark / black-ice test hours only (where the model is used, n = {d['n']})
MAE {d['mae']:.3f} vs baseline {d['mae_baseline']:.3f}; Poisson deviance {d['poisson_dev']:.3f} vs {d['poisson_dev_baseline']:.3f}.

### Calibration (test, quintiles of prediction)
| Bin | Mean predicted | Mean observed | n |
|---|---|---|---|
{calib}

### Does the speed limit matter to the model? (raw curve, before the D9 guard)
- Mean predicted rate at 40 minus at 80 km/h over dark/ice test hours: **{m['limit_sensitivity_raw']:+.3f}** per hour.
- Share of dark/ice test hours where some limit reaches <= {cfg.decide.target_rate}/h: **{m['reachable_share_raw']:.1%}**.

### What REQ1 decides (after the D9 guard, candidates <= {cfg.decide.req1_max_limit} km/h per D33)
- Mean guarded rate at 40 minus at 80 km/h: **{m['limit_sensitivity_guarded']:+.3f}** per hour.
- Share of dark/ice test hours where the target <= {cfg.decide.target_rate}/h is reachable: **{m['reachable_share_guarded']:.1%}**.
- Chosen REQ1 limit over the {d['n']} dark/ice test hours: {', '.join(f"{l} km/h: {n}" for l, n in m['req1_decisions'].items())}.

## Training cells (hours per condition x limit, D32)
| Condition | {' | '.join(str(l) for l in cfg.decide.candidate_limits)} |
|---|{'---|' * len(cfg.decide.candidate_limits)}
{cells}

Cells with 0 hours are pure extrapolation and are flagged in the GUI.

## Known limitations
- One winter month; no seasonality.
- The data barely supports REQ1 (figure F04): near-accidents stay above 1/h at every observed limit, and lower
  limits coincide with *more* incidents in dark hours (confounding). The model cannot learn a causal speed effect.
- MLPRegressor has no Poisson loss; log1p + smearing is an approximation.
- Small test set ({m['n']} hours); differences to the baseline may be noise.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Train the SpeedLimit near-accident model")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--models-dir", default=None)
    ap.add_argument("--reports-dir", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(Path(args.config))
    models_dir = Path(args.models_dir) if args.models_dir else cfg.paths.models_dir
    reports_dir = Path(args.reports_dir) if args.reports_dir else cfg.paths.reports_dir

    hourly, report = prepare_hourly(cfg)
    hourly = hourly[hourly.complete]
    train_h, test_h = split_by_day(hourly, cfg.split)
    X_tr, X_te = build_features(train_h, cfg.features), build_features(test_h, cfg.features)

    art = train(X_tr, train_h["near_accidents"], cfg.model)
    table = baseline_table(train_h)
    counts = train_h.groupby(["condition", train_h["speed_limit"].astype(int)]).size()
    cell_counts = {(c, l): int(counts.get((c, l), 0)) for c in CONDITIONS for l in cfg.decide.candidate_limits}

    y_te = test_h["near_accidents"].to_numpy()
    base_te = baseline_predict(table, test_h["condition"], test_h["speed_limit"])
    pred_te = predict_rate(art, X_te)
    metrics = evaluate(pred_te, y_te, base_te)
    di = (test_h["condition"] != "normal").to_numpy()
    metrics["dark_ice_only"] = {k: v for k, v in evaluate(pred_te[di], y_te[di], base_te[di]).items()
                                if k != "calibration"}
    sweep = _sweep(art, test_h[di], cfg)
    metrics["limit_sensitivity_raw"] = float((sweep[:, 0] - sweep[:, -1]).mean())
    metrics["reachable_share_raw"] = float((sweep.min(axis=1) <= cfg.decide.target_rate).mean())
    limits = list(cfg.decide.candidate_limits)
    guarded = [monotone_guard(dict(zip(limits, row))) for row in sweep]          # D9
    choices = [select_limit(g, cfg) for g in guarded]                             # D7, D25, D33
    metrics["limit_sensitivity_guarded"] = float(np.mean([g[limits[0]] - g[limits[-1]] for g in guarded]))
    metrics["reachable_share_guarded"] = float(np.mean([ok for _, ok in choices]))
    metrics["req1_decisions"] = {str(l): int(n) for l, n in
                                 sorted(pd.Series([l for l, _ in choices]).value_counts().items())}

    art = dataclasses.replace(
        art, version=_version(), candidate_limits=list(cfg.decide.candidate_limits), baseline_table=table,
        cell_counts=cell_counts, train_days=sorted(set(train_h.index.get_level_values("day"))),
        test_days=sorted(set(test_h.index.get_level_values("day"))), metrics=metrics, data_hash=_data_hash(cfg))

    save(art, models_dir / f"model_{art.version}.joblib")
    save(art, models_dir / "latest.joblib")
    (models_dir / "baseline_table.json").write_text(
        json.dumps({f"{c}|{l}": v for (c, l), v in table.items()}, indent=2), encoding="utf-8")
    (models_dir / f"model_card_{art.version}.md").write_text(_card(art, metrics, cfg, report), encoding="utf-8")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (reports_dir / "cleaning_report.json").write_text(
        json.dumps({"events": report.events, "silent_sensors": report.silent_sensors}, indent=2), encoding="utf-8")
    print(f"model {art.version}: test MAE {metrics['mae']:.3f} (baseline {metrics['mae_baseline']:.3f}), "
          f"skill {metrics['skill']:+.3f}, REQ1 reachable {metrics['reachable_share_guarded']:.0%}, "
          f"decisions {metrics['req1_decisions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
