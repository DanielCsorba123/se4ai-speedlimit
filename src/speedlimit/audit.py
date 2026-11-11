"""Append-only JSONL decision log (architecture §11.1). No personal data (D20)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from speedlimit.domain import Decision


def to_record(d: Decision) -> dict:
    s = d.situation
    rec = {
        "decided_at": d.decided_at.isoformat(timespec="seconds") if d.decided_at else None,
        "situation_time": s.timestamp.isoformat(timespec="minutes") if s else None,
        "final_limit": d.limit,
        "winning_reasons": d.winning_reasons,
        "dark": d.rule.dark,
        "black_ice": d.rule.black_ice,
        "missing_inputs": list(d.rule.missing_inputs),
        "req1_active": d.req1.active,
        "req1_limit": d.req1.limit,
        "req1_source": d.req1.source,
        "req1_target_reachable": d.req1.target_reachable,
        "req1_rates_raw": {str(k): round(v, 4) for k, v in d.req1.rates_raw.items()},
        "req1_rates_guarded": {str(k): round(v, 4) for k, v in d.req1.rates_guarded.items()},
        "req1_extrapolated": list(d.req1.extrapolated),
        "req2_limit": d.req2.limit,
        "req2_source": d.req2.source,
        "req2_reason": d.req2.reason,
        "req2_eaqi_max": d.req2.aq.eaqi_max if d.req2.aq else None,
        "model_version": d.model_version,
        "explanation": d.explanation,
    }
    if s:
        rec |= {"lux": s.lux, "water_um": s.water_um, "temp_c": s.temp_c, "humidity": s.humidity,
                "noise_db": s.noise_db, "wind_strength": s.wind_strength, "wind_dir_deg": s.wind_dir_deg,
                "traffic_cps": s.traffic_cps, "current_limit": s.current_limit}
    return rec


def log_decision(d: Decision, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(to_record(d), default=str) + "\n")


def read_log(path: Path, n: int = 50) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    return pd.DataFrame([json.loads(line) for line in lines if line.strip()])
