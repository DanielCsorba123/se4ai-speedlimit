"""SpeedLimit operational stage (backlog Task 8, architecture §8, D17).

    streamlit run src/speedlimit/app.py

Env overrides (tests / demos): SPEEDLIMIT_OFFLINE=1 (no forecast, LLM off),
SPEEDLIMIT_MODELS_DIR, SPEEDLIMIT_LOGS_DIR.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from speedlimit import air_quality
from speedlimit.audit import log_decision, read_log
from speedlimit.cli_train import prepare_hourly
from speedlimit.config import load_config
from speedlimit.decide import RuntimeContext, decide
from speedlimit.domain import Decision, Situation
from speedlimit.model import load
from speedlimit.ui_helpers import lux_to_slider, slider_to_lux

ROOT = Path(__file__).resolve().parents[2]
OFFLINE = os.environ.get("SPEEDLIMIT_OFFLINE") == "1"
# key, label, min, max, step, hourly column
SLIDERS = [
    ("log_lux", "Light (log10 lux)", -3.0, 6.0, 0.01, "lux"),
    ("water", "Water on road (µm)", 0.0, 10000.0, 10.0, "water"),
    ("temp", "Temperature (°C)", -30.0, 70.0, 0.1, "temp"),
    ("humidity", "Humidity (%)", 0.0, 100.0, 0.5, "humidity"),
    ("noise", "Noise (dB)", 60.0, 120.0, 0.5, "noise"),
    ("wind_strength", "Wind strength (km/h)", 0.0, 300.0, 1.0, "wind_strength"),
    ("wind_dir", "Wind direction (°)", 0.0, 360.0, 1.0, "wind_dir"),
    ("traffic", "Traffic (cars/s)", 0.0, 50.0, 0.1, "traffic"),
]


# Demo deep links ?scenario=AT-n (test strategy §4). (day, hour) picks the sample hour; the rest overrides inputs.
SCENARIOS = {
    "AT-1": {"at": (25, 13), "log_lux": math.log10(25000), "water": 200.0, "temp": 4.0, "manual_aqi": 25.0},
    "AT-2": {"at": (25, 22), "log_lux": -1.0, "water": 200.0, "temp": 4.0, "manual_aqi": 25.0},
    "AT-3": {"at": (25, 11), "log_lux": math.log10(30000), "water": 1500.0, "temp": -2.0, "manual_aqi": 25.0},
    "AT-4a": {"at": (25, 11), "log_lux": math.log10(30000), "water": 1000.0, "temp": -2.0, "manual_aqi": 25.0},
    "AT-4b": {"at": (25, 11), "log_lux": math.log10(30000), "water": 1001.0, "temp": -2.0, "manual_aqi": 25.0},
    "AT-5": {"at": (25, 13), "log_lux": math.log10(25000), "water": 200.0, "temp": 4.0, "sim_aqi": 92.0},
    "AT-6": {"at": (25, 3), "log_lux": -2.0, "water": 3000.0, "temp": -8.0, "manual_aqi": 25.0},
    "AT-8": {"at": (25, 22), "log_lux": -1.0, "water": 200.0, "temp": 4.0, "manual_aqi": 105.0},
}


def _apply_scenario(name: str, index: dict) -> None:
    sc = SCENARIOS[name]
    st.session_state["sample"] = next(l for l, dh in index.items() if dh == sc["at"])
    _fill_from_sample()
    for k, v in sc.items():
        if k != "at":
            st.session_state[k] = float(v)
    st.session_state["_scenario"] = name


@st.cache_resource
def _config():
    cfg = load_config(ROOT / "config.yaml")
    if OFFLINE:
        cfg = dataclasses.replace(cfg, llm=dataclasses.replace(cfg.llm, enabled=False))
    return cfg


def _models_dir(cfg) -> Path:
    return Path(os.environ.get("SPEEDLIMIT_MODELS_DIR", cfg.paths.models_dir))


def _logs_dir(cfg) -> Path:
    return Path(os.environ.get("SPEEDLIMIT_LOGS_DIR", cfg.paths.logs_dir))


@st.cache_resource
def _artefact(models_dir: str):
    """(artefact or None, baseline table or None, banner text or None)."""
    d = Path(models_dir)
    try:
        return load(d / "latest.joblib"), None, None
    except Exception as e:  # missing or incompatible artefact -> baseline (arch 8.3)
        why = type(e).__name__
    base = d / "baseline_table.json"
    if base.exists():
        raw = json.loads(base.read_text(encoding="utf-8"))
        table = {}
        for k, v in raw.items():
            c, l = k.split("|")
            table[(c, l if l == "*" else int(l))] = v
        return None, table, f"REQ1 using baseline table – neural network unavailable ({why})."
    return None, None, f"No model and no baseline table found in {d} ({why})."


@st.cache_data
def _hourly() -> pd.DataFrame:
    hourly, _ = prepare_hourly(_config())
    return hourly[hourly.complete]


def _label(day: int, hour: int, row) -> str:
    return f"Jan {day:02d} {hour:02d}:00 · {row.condition.replace('_', ' ')} · was {int(row.speed_limit)} km/h"


def _fill_from_sample():
    h = _hourly()
    day, hour = st.session_state["_sample_index"][st.session_state["sample"]]
    row = h.loc[(day, hour)]
    for key, _, lo, hi, _, col in SLIDERS:
        v = lux_to_slider(row[col]) if key == "log_lux" else float(row[col])
        st.session_state[key] = float(min(max(v, lo), hi))


def _situation_from_sliders(ts: datetime, current: int) -> Situation:
    ss = st.session_state
    return Situation(timestamp=ts, lux=slider_to_lux(ss["log_lux"]), water_um=ss["water"], temp_c=ss["temp"],
                     humidity=ss["humidity"], noise_db=ss["noise"], wind_strength=ss["wind_strength"],
                     wind_dir_deg=ss["wind_dir"], traffic_cps=ss["traffic"], current_limit=current)


def _situation_from_row(day: int, hour: int, row) -> Situation:
    return Situation(timestamp=datetime(2026, 1, day, hour), lux=row.lux, water_um=row.water, temp_c=row.temp,
                     humidity=row.humidity, noise_db=row.noise, wind_strength=row.wind_strength,
                     wind_dir_deg=row.wind_dir, traffic_cps=row.traffic, current_limit=int(row.speed_limit))


def _aq_summary(cfg, use_forecast: bool):
    sim = st.session_state.get("sim_aqi")
    if sim is not None:                                   # D38: demo forecast through the real LLM path
        return air_quality.simulated_summary(sim, cfg.air_quality)
    if OFFLINE or not use_forecast:
        return None
    fc = air_quality.fetch_forecast(cfg.air_quality.latitude, cfg.air_quality.longitude, cfg.air_quality)
    return air_quality.summarise(fc, cfg.air_quality.horizon_hours) if fc else None


def _render(d: Decision, cfg) -> None:
    colour = "green" if d.limit >= 80 else ("orange" if d.limit >= 60 else "red")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Speed limit", f"{d.limit} km/h")
        st.markdown(f":{colour}[**Set by {' + '.join(d.winning_reasons)}**]")
    with c2:
        r1, r2 = d.req1, d.req2
        req1_txt = f"{r1.limit} ({r1.source})" if r1.active else "inactive"
        st.markdown(f"**REQ1:** {req1_txt} · **REQ2:** {r2.limit} ({r2.source}) · **REQ3:** 80")
        if r1.active:
            best = min(r1.rates_guarded[l] for l in r1.rates_guarded if l <= cfg.decide.req1_max_limit)
            if r1.target_reachable:
                st.markdown(f"Target ≤ {cfg.decide.target_rate}/h: **reached** "
                            f"({r1.rates_guarded[r1.limit]:.2f}/h at {r1.limit} km/h)")
            else:
                st.markdown(f"Target ≤ {cfg.decide.target_rate}/h: :red[**NOT reachable**] (best {best:.2f}/h)")
    st.subheader("Explanation")
    st.markdown(d.explanation)
    rule = d.rule
    s = d.situation
    st.markdown(f"- Dark: {'yes' if rule.dark else 'no'} (lux {s.lux:.3g}; dark needs < "
                f"{cfg.rules.dark_lux_threshold}, SPEC1)\n"
                f"- Black ice: {'yes' if rule.black_ice else 'no'} (water {s.water_um:.0f} µm, needs > "
                f"{cfg.rules.ice_water_um_threshold:.0f}; temp {s.temp_c:.1f} °C, needs < "
                f"{cfg.rules.ice_temp_c_threshold:.0f}; SPEC2)")
    if rule.missing_inputs:
        st.warning(f"Missing inputs treated as condition met (D30): {', '.join(rule.missing_inputs)}")
    st.text(f"Air quality ({d.req2.source}): {d.req2.reason[:300]}")   # plain text, never markdown (arch 7.7)
    if d.req1.active:
        table = pd.DataFrame({"raw": d.req1.rates_raw, "guarded": d.req1.rates_guarded})
        table.index.name = "limit km/h"
        table["target"] = cfg.decide.target_rate
        table["extrapolated"] = [l in d.req1.extrapolated for l in table.index]
        st.subheader("Predicted near-accidents per hour by limit")
        st.line_chart(table[["raw", "guarded", "target"]])
        st.dataframe(table.round(3))
        if d.req1.extrapolated:
            st.caption(f"Extrapolated (no training data in this condition, D32): "
                       f"{', '.join(str(l) for l in d.req1.extrapolated)} km/h")
    else:
        st.info("REQ1 inactive: not dark and no black-ice danger.")


def _log_once(d: Decision, cfg) -> None:
    s = d.situation
    sig = (s.timestamp, round(s.lux, 6), s.water_um, s.temp_c, s.humidity, s.noise_db, s.wind_strength,
           s.wind_dir_deg, s.traffic_cps, d.req2.source, d.req2.limit)
    if st.session_state.get("_last_sig") != sig:
        log_decision(d, _logs_dir(cfg) / "decisions.jsonl")
        st.session_state["_last_sig"] = sig


def main() -> None:
    st.set_page_config(page_title="SpeedLimit MVP", layout="wide")
    cfg = _config()
    art, baseline, banner = _artefact(str(_models_dir(cfg)))
    hourly = _hourly()
    st.title("SpeedLimit MVP")
    st.caption(f"model {art.version if art else 'none'} · prompt {cfg.llm.prompt_version} · "
               f"LLM {cfg.llm.model if cfg.llm.enabled else 'off'}")
    if banner:
        st.warning(banner)

    index = {_label(d, h, r): (d, h) for (d, h), r in hourly.iterrows()}
    st.session_state["_sample_index"] = index
    labels = list(index)
    scenario = st.query_params.get("scenario")
    if scenario in SCENARIOS and st.session_state.get("_scenario") != scenario:
        _apply_scenario(scenario, index)
    if "sample" not in st.session_state:
        test_start = cfg.split.test_days[0]
        st.session_state["sample"] = next(
            (l for l, (d, h) in index.items() if d >= test_start and hourly.loc[(d, h)].condition == "dark"), labels[0])
        _fill_from_sample()

    with st.sidebar:
        mode = st.radio("Mode", ["Manual", "Replay"], key="mode", horizontal=True)
        st.selectbox("Sample hour", labels, key="sample", on_change=_fill_from_sample)
        for key, label, lo, hi, step, _ in SLIDERS:
            st.slider(label, lo, hi, step=step, key=key, disabled=(mode == "Replay"))
            if key == "log_lux":
                st.caption(f"= {slider_to_lux(st.session_state['log_lux']):.4g} lux (dark below 0.5)")
        st.divider()
        st.markdown("**Air quality**")
        use_forecast = st.checkbox("Use Open-Meteo forecast", value=not OFFLINE, key="use_forecast",
                                   disabled=OFFLINE)
        st.number_input("Simulated forecast EAQI (demo, asks the LLM)", min_value=0.0, max_value=500.0,
                        value=None, step=1.0, key="sim_aqi")
        st.number_input("Manual EAQI (optional, uses the table)", min_value=0.0, max_value=500.0, value=None,
                        step=1.0, key="manual_aqi")

    aq = _aq_summary(cfg, use_forecast)
    manual = st.session_state.get("manual_aqi")
    if aq is None and manual is None:
        st.warning("Air quality unknown: no forecast available, no REQ2 reduction (D26).")
    ctx = RuntimeContext(cfg=cfg, art=art, baseline=baseline, aq_summary=aq, manual_aqi=manual,
                         llm_log=_logs_dir(cfg) / "llm_calls.jsonl")

    if mode == "Replay":
        keys = list(index.values())
        st.session_state.setdefault("replay_idx", keys.index(index[st.session_state["sample"]]))
        if st.button("Next hour", key="next_hour"):
            st.session_state["replay_idx"] = (st.session_state["replay_idx"] + 1) % len(keys)

        @st.fragment(run_every=cfg.gui.replay_interval_min * 60)
        def _replay():
            # advance only on timer ticks (fragment-only reruns), not on every full rerun
            if not st.session_state.pop("_full_run", False):
                st.session_state["replay_idx"] = (st.session_state["replay_idx"] + 1) % len(keys)
            day, hour = keys[st.session_state["replay_idx"]]
            st.markdown(f"**Replay hour:** Jan {day:02d} {hour:02d}:00")
            _show(_situation_from_row(day, hour, hourly.loc[(day, hour)]), ctx, cfg)

        st.session_state["_full_run"] = True
        _replay()
    else:
        day, hour = index[st.session_state["sample"]]
        current = int(hourly.loc[(day, hour)].speed_limit)
        _show(_situation_from_sliders(datetime(2026, 1, day, hour), current), ctx, cfg)

    st.subheader(f"Audit log (last {cfg.gui.audit_rows} decisions)")
    log = read_log(_logs_dir(cfg) / "decisions.jsonl", n=cfg.gui.audit_rows)
    if not log.empty:
        cols = ["situation_time", "dark", "black_ice", "req1_limit", "req2_limit", "req2_source", "final_limit",
                "winning_reasons", "req1_target_reachable", "model_version"]
        st.dataframe(log[[c for c in cols if c in log.columns]].iloc[::-1], hide_index=True)


def _show(s: Situation, ctx: RuntimeContext, cfg) -> None:
    try:
        d = decide(s, ctx)
    except Exception as e:  # D29: fail safe, never a blank screen
        st.error(f"Decision failed ({type(e).__name__}: {e}). Showing the fail-safe limit "
                 f"{cfg.decide.crash_display_limit} km/h (D29).")
        st.metric("Speed limit", f"{cfg.decide.crash_display_limit} km/h")
        return
    _render(d, cfg)
    _log_once(d, cfg)


main()
