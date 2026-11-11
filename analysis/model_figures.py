"""Model result figures + numbers for the presentation (Task 10).

    .venv/Scripts/python analysis/model_figures.py
Needs models/latest.joblib (python -m speedlimit.cli_train). Writes
docs/figures/F13_model_vs_baseline.png, F14_req1_choices_vs_operators.png and
docs/evidence/model_results.json.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from speedlimit.cli_train import prepare_hourly
from speedlimit.config import load_config
from speedlimit.decide import select_limit
from speedlimit.features import build_features
from speedlimit.model import load, monotone_guard, predict_rate, split_by_day

ROOT = Path(__file__).resolve().parents[1]
FIG, EV = ROOT / "docs" / "figures", ROOT / "docs" / "evidence"
INK, MUTED, GRID, ROAD, AMBER, RED, TEAL = "#1f2a36", "#6b7785", "#e3e8ee", "#33414f", "#e8a317", "#c8372d", "#1f8a83"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "savefig.dpi": 150,
                     "axes.titleweight": "bold", "axes.titlesize": 15, "axes.titlecolor": INK})


def main() -> None:
    cfg = load_config(ROOT / "config.yaml")
    art = load(cfg.model.artefact)
    m = art.metrics
    hourly, _ = prepare_hourly(cfg)
    _, test = split_by_day(hourly[hourly.complete], cfg.split)
    di = test[test.condition != "normal"]
    X = build_features(di, cfg.features)
    limits = list(cfg.decide.candidate_limits)
    sweep = []
    for lim in limits:
        Xl = X.copy()
        Xl["speed_limit"] = float(lim)
        sweep.append(predict_rate(art, Xl))
    sweep = np.column_stack(sweep)
    raw = [dict(zip(limits, row)) for row in sweep]
    guarded = [monotone_guard(r) for r in raw]
    activated = float(np.mean([any(abs(g[l] - r[l]) > 1e-9 for l in limits) for r, g in zip(raw, guarded)]))
    chosen = pd.Series([select_limit(g, cfg)[0] for g in guarded]).value_counts().reindex(limits, fill_value=0)
    operators = di.speed_limit.astype(int).value_counts().reindex(limits, fill_value=0)

    # F13 model vs baseline
    fig, ax = plt.subplots(figsize=(12, 5.5))
    groups = [("All test hours", m["mae"], m["mae_baseline"], m["n"]),
              ("Dark / black-ice test hours\n(where the model is used)", m["dark_ice_only"]["mae"],
               m["dark_ice_only"]["mae_baseline"], m["dark_ice_only"]["n"])]
    x = np.arange(len(groups))
    b1 = ax.bar(x - 0.18, [g[1] for g in groups], 0.34, color=TEAL, label="Neural network (5-MLP ensemble)")
    b2 = ax.bar(x + 0.18, [g[2] for g in groups], 0.34, color=MUTED, label="Baseline: mean per condition x limit")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, f"{b.get_height():.3f}", ha="center")
    ax.set_xticks(x, [f"{g[0]}\nn = {g[3]} h" for g in groups])
    ax.set_ylabel("Mean absolute error (near-accidents / h)")
    ax.set_ylim(0, 1.1)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title(f"F13  On unseen days the network is only slightly better than a simple average "
                 f"(skill {m['skill']:+.3f})", loc="left")
    fig.text(0.01, -0.03, f"Source: model {art.version}, test days {art.test_days[0]}-{art.test_days[-1]} (D12)",
             fontsize=9, color=MUTED)
    fig.savefig(FIG / "F13_model_vs_baseline.png", bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)

    # F14 REQ1 choices vs operators
    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(limits))
    ax.bar(x - 0.18, operators.values, 0.34, color=ROAD, label="Operators (historical limit)")
    ax.bar(x + 0.18, chosen.values, 0.34, color=AMBER, label="System REQ1 choice (guard + D25 + D33)")
    for i, (o, c) in enumerate(zip(operators.values, chosen.values)):
        ax.text(i - 0.18, o + 0.8, str(o), ha="center")
        ax.text(i + 0.18, c + 0.8, str(c), ha="center")
    ax.set_xticks(x, [f"{l} km/h" for l in limits])
    ax.set_ylabel(f"Dark / black-ice test hours (n = {len(di)})")
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("F14  The system reduces less than the operators did: mostly 70 instead of 60 km/h", loc="left")
    fig.text(0.01, -0.03, "Source: test days 25-31; the system never keeps 80 km/h in dark/icy hours (D33)",
             fontsize=9, color=MUTED)
    fig.savefig(FIG / "F14_req1_choices_vs_operators.png", bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)

    out = {"model_version": art.version, "mae": m["mae"], "mae_baseline": m["mae_baseline"], "skill": m["skill"],
           "dark_ice": m["dark_ice_only"], "reachable_share": m["reachable_share_guarded"],
           "not_reachable_share": 1 - m["reachable_share_guarded"], "guard_activation_share": activated,
           "req1_choices": {str(k): int(v) for k, v in chosen.items()},
           "operator_limits": {str(k): int(v) for k, v in operators.items()},
           "limit_sensitivity_raw": m["limit_sensitivity_raw"], "limit_sensitivity_guarded": m["limit_sensitivity_guarded"]}
    EV.mkdir(parents=True, exist_ok=True)
    (EV / "model_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
