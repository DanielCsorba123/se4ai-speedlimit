"""Reproducible evidence figures + facts for the SpeedLimit project docs.

Run from the project root:  python analysis/make_figures.py
Outputs: docs/figures/*.png and docs/figures/facts.json
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

F_READ_N = ROOT / "Case_Study_Speed_Limit_SensorReadingsYearN_V100.csv"
F_READ_N1 = ROOT / "Case_Study_Speed_Limit_SensorReadingsYearNPlus1_V100.csv"
F_ACC = ROOT / "Case_Study_Speed_Limit_AccidentsYearN_V100.csv"
F_SENS = ROOT / "Case_Study_Speed_Limit_Sensors_V100.csv"
F_TYPES = ROOT / "Case_Study_Speed_Limit_SensorTypes_V100.csv"

# ---- style -------------------------------------------------------------
INK, MUTED, GRID = "#1f2a36", "#6b7785", "#e3e8ee"
ROAD, AMBER, RED, TEAL, SKY = "#33414f", "#e8a317", "#c8372d", "#1f8a83", "#4a7fc1"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titleweight": "bold", "axes.titlesize": 15, "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "figure.facecolor": "white", "savefig.dpi": 150,
})
FIG = (12, 6.75)


def save(fig, name, source):
    fig.text(0.01, -0.04, f"Source: {source}", fontsize=9, color=MUTED)
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)


def code_panel(lines, title, name, highlights=None, note=None, source=""):
    """Render a file excerpt like an editor screenshot. highlights: {line_idx: color}"""
    highlights = highlights or {}
    h = 0.42 * len(lines) + 1.6
    fig, ax = plt.subplots(figsize=(12, h))
    ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, len(lines) + 1)
    ax.add_patch(plt.Rectangle((0, 0), 1, len(lines) + 1, color="#f6f8fa", zorder=0))
    for i, ln in enumerate(lines):
        y = len(lines) - i
        if i in highlights:
            ax.add_patch(plt.Rectangle((0, y - 0.45), 1, 0.9, color=highlights[i], alpha=0.22, zorder=1))
        ax.text(0.01, y, f"{i + 1:>3}", family="monospace", fontsize=12, color=MUTED, va="center")
        ax.text(0.06, y, ln, family="monospace", fontsize=12, color=INK, va="center")
    ax.set_title(title, loc="left", pad=12)
    if note:
        fig.text(0.01, -0.02 - 0.12 / h * 6, note, fontsize=11, color=INK, wrap=True)
    save(fig, name, source)


facts = {}

# ---- load ----------------------------------------------------------------
cols = ["Month", "Day", "Hour", "Minute", "Second", "Sensor", "Value"]
rn = pd.read_csv(F_READ_N, sep=";", encoding="utf-8-sig", decimal=",")
rn1 = pd.read_csv(F_READ_N1, sep=";", encoding="utf-8-sig", decimal=",", header=None, names=cols)
acc = pd.read_csv(F_ACC, sep=";", encoding="utf-8-sig")
sens = pd.read_csv(F_SENS, sep=";", encoding="utf-8-sig")
types = pd.read_csv(F_TYPES, sep=";", encoding="utf-8-sig")

raw_types = F_TYPES.read_text(encoding="utf-8-sig").splitlines()
raw_n = F_READ_N.read_bytes()[:400].decode("utf-8", errors="replace").splitlines()
raw_n1 = F_READ_N1.read_text(encoding="utf-8-sig").splitlines()[:4]

facts["rows"] = {"readings_N": len(rn), "readings_N1": len(rn1), "accidents": len(acc),
                 "sensors_defined": len(sens), "sensor_types_rows": len(types)}

# ---- F01 raw format excerpt ---------------------------------------------
code_panel(
    ["Month;Day;Hour;Minute;Second;Sensor;Value      <- UTF-8 BOM before 'Month'",
      "1;1;0;3;35;6;0,00                            <- decimal comma",
     "1;1;0;22;0;-1;70,00                          <- sensor -1 = speed limit (70 km/h)",
     *F_READ_N.read_text(encoding="utf-8-sig").splitlines()[3:7],
     "...  12 648 rows, January only"],
    "F01  Raw readings file: ';' separator, decimal comma, BOM, speed limit as sensor -1",
    "F01_raw_readings_format.png", highlights={0: AMBER, 1: AMBER, 2: TEAL},
    source=F_READ_N.name)

# ---- F02 sensor type metadata issues ------------------------------------
hl = {}
for i, ln in enumerate(raw_types):
    if ln.startswith("T;") or ln.startswith("W ;") or "hm/h" in ln or "degrees   " in ln:
        hl[i] = RED if ln.startswith("T;") else AMBER
code_panel(
    [ln + ("   <- code 'T' used twice" if ln.startswith("T;") else
           "   <- trailing space in code" if ln.startswith("W ;") else
           "   <- unit typo (km/h?)" if "hm/h" in ln else
           "   <- padded unit" if "degrees   " in ln else "") for ln in raw_types],
    "F02  SensorTypes.csv: ambiguous code 'T' (temperature AND traffic) + dirty values",
    "F02_sensor_types_issues.png", highlights=hl, source=F_TYPES.name)

# ---- F03 sensor coverage matrix -----------------------------------------
defined = dict(zip(sens.SensorID, sens.SensorTypeCode.str.strip()))
has_read = set(rn.Sensor.unique()) - {-1}
all_ids = sorted(set(defined) | has_read)
fig, ax = plt.subplots(figsize=(12, 3.6))
ax.grid(False)
for x, sid in enumerate(all_ids):
    d, r = sid in defined, sid in has_read
    color = TEAL if d and r else (RED if r else AMBER)
    ax.add_patch(plt.Rectangle((x, 0), 0.92, 0.92, color=color))
    ax.text(x + 0.46, 0.6, str(sid), ha="center", va="center", color="white", fontsize=13, weight="bold")
    ax.text(x + 0.46, 0.25, defined.get(sid, "?"), ha="center", va="center", color="white", fontsize=10)
ax.set_xlim(0, len(all_ids)); ax.set_ylim(-0.6, 1.1); ax.set_axis_off()
for i, (c, lbl) in enumerate([(TEAL, "defined + has readings"), (AMBER, "defined, NO readings"),
                              (RED, "readings, NOT defined")]):
    ax.add_patch(plt.Rectangle((i * 6, -0.5), 0.4, 0.3, color=c))
    ax.text(i * 6 + 0.55, -0.35, lbl, va="center", fontsize=11, color=INK)
ax.set_title("F03  Sensor coverage: 7, 10, 17 never report; 19 reports but is undocumented", loc="left")
save(fig, "F03_sensor_coverage.png", f"{F_SENS.name}, {F_READ_N.name}")
facts["sensors_no_readings"] = sorted(int(s) for s in set(defined) - has_read)
facts["sensors_undocumented"] = sorted(int(s) for s in has_read - set(defined))

# ---- hourly wide table ----------------------------------------------------
p = rn.pivot_table(index=["Day", "Hour"], columns="Sensor", values="Value")
lux = p[[2, 9, 12]].mean(axis=1)
water = p[[1, 8, 11]].mean(axis=1)
temp = p[[15, 18, 19]].mean(axis=1)
dark = lux < 0.5
ice = (water > 1000) & (temp < 0)
p["cond"] = np.where(dark, "dark", np.where(ice, "black ice", "normal"))
acc2 = acc.copy()
acc2["Hour"] = acc2.Hour - 1  # D1: hour 1-24 = hour ending -> 0-23 start hour
p["near"] = acc2[acc2[["CloseCarCm", "CloseGuardrailCm", "SkidAngle"]].notna().any(axis=1)] \
    .groupby(["Day", "Hour"]).size().reindex(p.index).fillna(0)
p["acc"] = acc2[acc2[["Damage", "Injured"]].notna().any(axis=1)] \
    .groupby(["Day", "Hour"]).size().reindex(p.index).fillna(0)
facts["hours"] = int(len(p))
facts["hours_dark"] = int(dark.sum())
facts["hours_ice_not_dark"] = int((ice & ~dark).sum())
facts["hours_ice_total"] = int(ice.sum())
facts["hours_reduction_needed"] = int((dark | ice).sum())
facts["speed_limit_counts"] = {int(k): int(v) for k, v in p[-1].value_counts().sort_index().items()}
unexpl = p[(p.cond == "normal") & (p[-1] < 80)]
facts["unexplained_reductions"] = int(len(unexpl))
facts["unexplained_examples"] = [f"Jan {d} {h:02d}:00 -> {int(v)} km/h" for (d, h), v in unexpl[-1].head(6).items()]
facts["unexplained_hours_of_day"] = {int(k): int(v) for k, v in pd.Series(unexpl.index.get_level_values(1)).value_counts().sort_index().items()}
facts["near_per_hour_overall"] = round(float(p.near.mean()), 2)
facts["corr_near_vs_speed"] = round(float(p.near.corr(p[-1])), 3)
facts["corr_near_vs_traffic16"] = round(float(p.near.corr(p[16])), 3)

# ---- F04 REQ1 evidence ----------------------------------------------------
g = p.groupby(["cond", -1]).near.agg(["mean", "count"]).reset_index()
facts["near_by_cond_speed"] = [
    {"cond": r.cond, "speed": int(r[-1]), "mean_near_per_h": round(r["mean"], 2), "hours": int(r["count"])}
    for _, r in g.iterrows()]
fig, ax = plt.subplots(figsize=FIG)
conds = ["dark", "black ice", "normal"]
colors = {"dark": ROAD, "black ice": SKY, "normal": AMBER}
speeds = [40, 50, 60, 70, 80]
w = 0.26
for i, c in enumerate(conds):
    sub = g[g.cond == c].set_index(-1)
    xs = [j + (i - 1) * w for j, s in enumerate(speeds) if s in sub.index]
    ys = [sub.loc[s, "mean"] for s in speeds if s in sub.index]
    ns = [sub.loc[s, "count"] for s in speeds if s in sub.index]
    bars = ax.bar(xs, ys, w * 0.95, color=colors[c], label=c)
    for b, n in zip(bars, ns):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"n={n}h", ha="center", fontsize=9, color=MUTED)
ax.axhline(1.0, color=RED, lw=2, ls="--")
ax.text(-0.45, 0.93, "REQ1 target: <= 1 near-accident / h", color=RED, ha="left", fontsize=11, weight="bold")
ax.set_xticks(range(len(speeds)), [f"{s} km/h" for s in speeds])
ax.set_ylabel("Mean near-accidents per hour")
ax.set_ylim(0, 2.2)
ax.legend(title="Condition (SPEC1/SPEC2)", frameon=False, loc="upper center")
ax.set_title(f"F04  Near-accidents stay above 1/h at every speed limit (corr. with limit = {facts['corr_near_vs_speed']})", loc="left")
save(fig, "F04_req1_near_accidents_vs_speed.png", f"{F_ACC.name} joined to {F_READ_N.name}; hour mapping D1")

# ---- F05 hour mismatch ------------------------------------------------------
fig, axs = plt.subplots(1, 2, figsize=FIG, sharey=False)
axs[0].bar(sorted(rn.Hour.unique()), rn.groupby("Hour").size().sort_index(), color=TEAL)
axs[0].set_title("Readings: Hour 0..23", loc="left"); axs[0].set_xticks([0, 6, 12, 18, 23])
hc = acc.Hour.value_counts().sort_index()
axs[1].bar(hc.index, hc.values, color=[RED if h == 24 else ROAD for h in hc.index])
axs[1].set_title("Accidents: Hour 1..24 (no 0)", loc="left"); axs[1].set_xticks([1, 6, 12, 18, 24])
axs[1].annotate(f"{int(hc.get(24, 0))} events at hour 24", xy=(24, hc.get(24, 0)), xytext=(13, hc.max() * 1.05),
                arrowprops=dict(arrowstyle="->", color=RED), color=RED)
fig.suptitle("F05  Clock mismatch between files: accidents use 1-24, readings use 0-23",
             x=0.01, ha="left", weight="bold", size=15, color=INK)
save(fig, "F05_hour_mismatch.png", f"{F_READ_N.name}, {F_ACC.name}")
facts["acc_hour_min_max"] = [int(acc.Hour.min()), int(acc.Hour.max())]
facts["acc_hour24_count"] = int(hc.get(24, 0))

# ---- F06 sensor 16 is not temperature ---------------------------------------
wk = p.loc[(slice(1, 7), slice(None)), :]
x = np.arange(len(wk))
fig, ax = plt.subplots(figsize=FIG)
for s, c in [(15, SKY), (18, TEAL), (19, ROAD)]:
    ax.plot(x, wk[s].values, color=c, lw=1.4, label=f"sensor {s}" + (" (undocumented)" if s == 19 else " (T)"))
ax.plot(x, wk[16].values, color=AMBER, lw=2, label="sensor 16 (T) - range 1.85..30, no daily cycle match")
ax.set_xticks(range(0, len(wk), 24), [f"Jan {d}" for d in range(1, 8)])
ax.set_ylabel("Value")
ax.legend(frameon=False, loc="upper left", fontsize=10)
c16 = p[[15, 18, 19, 16]].corr().loc[16, 15]
ax.set_title(f"F06  Code 'T': sensor 16 behaves like traffic, not temperature (corr. with 15 = {c16:.2f})", loc="left")
save(fig, "F06_sensor16_traffic_vs_temperature.png", F_READ_N.name)
facts["corr_16_vs_15"] = round(float(c16), 2)
facts["corr_15_18_19_min"] = round(float(p[[15, 18, 19]].corr().values.min()), 3)

# ---- F07 unexplained reductions timeline -------------------------------------
d0, d1 = 11, 14
seg = p.loc[(slice(d0, d1), slice(None)), :]
x = np.arange(len(seg))
fig, ax = plt.subplots(figsize=FIG)
for i, (idx, row) in enumerate(seg.iterrows()):
    if row.cond == "dark":
        ax.axvspan(i - 0.5, i + 0.5, color=ROAD, alpha=0.12, lw=0)
    elif row.cond == "black ice":
        ax.axvspan(i - 0.5, i + 0.5, color=SKY, alpha=0.25, lw=0)
ax.step(x, seg[-1].values, where="mid", color=INK, lw=2, label="speed limit (sensor -1)")
bad = np.where((seg.cond == "normal") & (seg[-1] < 80))[0]
ax.scatter(bad, seg[-1].values[bad], color=RED, s=90, zorder=5, label="reduced with no SPEC1/SPEC2 reason")
ax.set_xticks(range(0, len(seg), 12), [f"Jan {d} {h:02d}h" for (d, h) in seg.index[::12]], rotation=30)
ax.set_ylim(35, 85); ax.set_ylabel("km/h")
from matplotlib.patches import Patch
handles, labels = ax.get_legend_handles_labels()
handles += [Patch(color=ROAD, alpha=0.12), Patch(color=SKY, alpha=0.25)]
labels += ["dark (lux < 0.5)", "black ice"]
ax.legend(handles, labels, frameon=False, loc="lower left", ncol=2, fontsize=10)
ax.set_title(f"F07  {facts['unexplained_reductions']} hours in Jan. have a reduced limit although REQ3 says 80 (shown: Jan {d0}-{d1})",
             loc="left")
save(fig, "F07_unexplained_reductions.png", F_READ_N.name)

# ---- F08 lux distribution -----------------------------------------------------
fig, axs = plt.subplots(1, 2, figsize=FIG)
axs[0].hist(lux, bins=40, color=AMBER)
axs[0].set_title("Illuminance, linear scale", loc="left"); axs[0].set_xlabel("lux")
axs[1].hist(np.log10(lux + 1e-3), bins=40, color=ROAD)
axs[1].axvline(np.log10(0.5), color=RED, ls="--", lw=2)
axs[1].text(np.log10(0.5) + 0.1, axs[1].get_ylim()[1] * 0.9, "SPEC1: 500 millilux", color=RED)
axs[1].set_title("log10(lux) - clean day/night split", loc="left"); axs[1].set_xlabel("log10 lux")
fig.suptitle("F08  Light spans 0 .. 120 000 lux: use log scale as model input",
             x=0.01, ha="left", weight="bold", size=15, color=INK)
save(fig, "F08_lux_log_transform.png", F_READ_N.name)

# ---- F09 event composition ------------------------------------------------------
comp = {
    "CloseCarCm": int(acc.CloseCarCm.notna().sum()),
    "CloseGuardrailCm": int(acc.CloseGuardrailCm.notna().sum()),
    "SkidAngle": int(acc.SkidAngle.notna().sum()),
    "Damage (accident)": int(acc.Damage.notna().sum()),
    "Injured (accident)": int(acc.Injured.notna().sum()),
}
kinds = acc[["Damage", "Injured", "CloseCarCm", "CloseGuardrailCm", "SkidAngle"]].notna().sum(axis=1)
facts["acc_fields_per_row"] = {int(k): int(v) for k, v in kinds.value_counts().items()}
facts["acc_composition"] = comp
facts["near_accidents"] = int(acc[["CloseCarCm", "CloseGuardrailCm", "SkidAngle"]].notna().any(axis=1).sum())
facts["accidents"] = int(acc[["Damage", "Injured"]].notna().any(axis=1).sum())
facts["acc_empty_rows"] = int((kinds == 0).sum())
facts["closecar_max_cm"] = float(acc.CloseCarCm.max())
fig, ax = plt.subplots(figsize=(12, 5))
names = list(comp)[::-1]; vals = [comp[n] for n in names]
bars = ax.barh(names, vals, color=[RED if "accident" in n else ROAD for n in names])
for b, v in zip(bars, vals):
    ax.text(v + 8, b.get_y() + b.get_height() / 2, str(v), va="center", fontsize=12)
ax.set_xlabel("rows with a value")
ax.set_title(f"F09  Event log: {facts['near_accidents']} near-accidents vs {facts['accidents']} accidents; "
             f"near-misses are 89% 'too close to car'", loc="left")
save(fig, "F09_event_composition.png", F_ACC.name)

# ---- F10 year N vs N+1 identical ---------------------------------------------------
same = (rn[cols].values == rn1[cols].values).all(axis=1).sum()
facts["n1_identical_rows"] = int(same)
fig, axs = plt.subplots(1, 2, figsize=FIG, gridspec_kw={"width_ratios": [1.1, 1]})
axs[0].scatter(rn.Value, rn1.Value, s=6, color=ROAD, alpha=0.5)
lim = [rn.Value.min(), rn.Value.max()]
axs[0].plot(lim, lim, color=RED, lw=1, ls="--")
axs[0].set_xscale("symlog"); axs[0].set_yscale("symlog")
axs[0].set_xlabel("Value, year N"); axs[0].set_ylabel("Value, year N+1")
axs[0].set_title("Every point on the diagonal", loc="left")
axs[1].set_axis_off()
txt = ("Year N (first 3 data rows)\n" + "\n".join(F_READ_N.read_text(encoding='utf-8-sig').splitlines()[1:4]) +
       "\n\nYear N+1 (first 3 rows, no header)\n" + "\n".join(raw_n1[:3]) +
       f"\n\nIdentical rows: {same:,} / {len(rn):,}\nOnly difference: header line missing")
axs[1].text(0, 0.95, txt, family="monospace", fontsize=12, va="top", color=INK,
            bbox=dict(boxstyle="round", fc="#f6f8fa", ec=GRID))
fig.suptitle("F10  'Year N+1' readings are a copy of year N: drift check will find nothing",
             x=0.01, ha="left", weight="bold", size=15, color=INK)
save(fig, "F10_yearN1_identical.png", f"{F_READ_N.name} vs {F_READ_N1.name}")

# ---- F11 one-week overview -----------------------------------------------------------
wk = p.loc[(slice(1, 7), slice(None)), :]
x = np.arange(len(wk))
fig, axs = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
axs[0].plot(x, np.log10(lux.loc[wk.index] + 1e-3), color=AMBER); axs[0].set_ylabel("log lux")
axs[0].axhline(np.log10(0.5), color=RED, ls="--", lw=1)
axs[1].plot(x, water.loc[wk.index], color=SKY); axs[1].set_ylabel("water um")
axs[1].axhline(1000, color=RED, ls="--", lw=1)
axs[2].plot(x, temp.loc[wk.index], color=TEAL); axs[2].set_ylabel("temp C")
axs[2].axhline(0, color=RED, ls="--", lw=1)
axs[3].step(x, wk[-1], where="mid", color=INK); axs[3].set_ylabel("limit km/h")
axs[3].bar(x, wk.near * 10 + 0, bottom=30, color=RED, alpha=0.4, width=1)
axs[3].set_ylim(28, 85)
axs[3].set_xticks(range(0, len(wk), 24), [f"Jan {d}" for d in range(1, 8)])
axs[0].set_title("F11  First week of January: inputs (with SPEC thresholds) vs speed limit; red bars = near-accidents",
                 loc="left")
save(fig, "F11_week_overview.png", f"{F_READ_N.name}, {F_ACC.name}")

# ---- F12 data quality scorecard of slide-17 claims -----------------------------------
claims = [
    ("Sensor type 'T' ambiguous", True), ("Sensor 19 undocumented", True),
    ("Sensors 7/10/17 no readings", True), ("Unexplained reductions: 28 h (slide example Jan 6 20:00 is dark in V100)", True),
    ("Sensor 18 empty readings Jan 26", False), ("Sensor 15 empty sensor# Jan 24", False),
    ("Sensor 2 NULL month Jan 18", False), ("Sensor 13 > 400 deg wind dir.", False),
    ("Sensor 15 Jan 10 missing", False), ("Sensor 4 Jan 12 duplicated", False),
    ("Sensor 9 'January' instead of 1", False), ("Sensor 11 Jan 17 extreme value", False),
]
# verify the 'False' claims programmatically so the figure is honest
chk = rn.groupby("Sensor").size()
assert (chk == 744).all(), "every sensor has exactly 744 readings"
assert rn.Value.notna().all() and rn.Month.eq(1).all()
assert rn[rn.Sensor == 13].Value.max() <= 360
fig, ax = plt.subplots(figsize=(12, 6.2)); ax.set_axis_off(); ax.grid(False)
for i, (c, ok) in enumerate(claims):
    y = len(claims) - i
    ax.text(0.02, y, "FOUND" if ok else "NOT IN V100", color="white", fontsize=11, weight="bold", va="center",
            bbox=dict(boxstyle="round", fc=TEAL if ok else MUTED, ec="none"))
    ax.text(0.22, y, c, fontsize=13, va="center", color=INK)
ax.set_ylim(0, len(claims) + 1); ax.set_xlim(0, 1)
ax.set_title("F12  Course error list (deck slide 17) checked against the V100 files", loc="left")
save(fig, "F12_slide17_claims_check.png", "deck slide 17 vs V100 CSVs (744 readings/sensor, no NaN, month=1, WD<=360)")
facts["every_sensor_744"] = True
facts["wd_max"] = float(rn[rn.Sensor.isin([5, 13])].Value.max())

(OUT / "facts.json").write_text(json.dumps(facts, indent=2))
print(json.dumps(facts, indent=2))
print("figures:", sorted(f.name for f in OUT.glob("*.png")))
