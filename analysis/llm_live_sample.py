"""One live REQ2 run per poor-air scenario; writes docs/evidence/llm_sample.json.

    .venv/Scripts/python analysis/llm_live_sample.py
Needs the provider key (GROQ_API_KEY) in the environment or in .env / .env.txt next to config.yaml.
Uses synthetic forecast summaries, because live air is usually not poor and REQ2 would then not call the LLM.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from speedlimit import air_quality as aq
from speedlimit import llm_advisor as la
from speedlimit.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CASES = {"AT-5 (EAQI 92, very poor)": 92.0, "EAQI 70 (poor)": 70.0, "EAQI 115 (extremely poor)": 115.0}


def main() -> None:
    cfg = load_config(ROOT / "config.yaml")
    out = {"captured_at": datetime.now().isoformat(timespec="seconds"), "provider": cfg.llm.provider,
           "model": cfg.llm.model, "note": "Synthetic forecast summaries (live Vienna air was not poor). "
                                           "Only numbers are sent; no key is stored.", "calls": []}
    for name, e in CASES.items():
        s = aq.simulated_summary(e, cfg.air_quality, now=datetime(2026, 1, 25, 13))
        t0 = time.perf_counter()
        r = la.advise(s, cfg, log_path=ROOT / "logs" / "llm_calls.jsonl")
        dt = time.perf_counter() - t0
        out["calls"].append({"scenario": name, "eaqi_max": e, "limit": r.limit, "source": r.source,
                             "table_limit": aq.table_limit(e, cfg.air_quality), "latency_s": round(dt, 2),
                             "reason": r.reason})
        line = f"{name}: {r.limit} km/h source={r.source} table={aq.table_limit(e, cfg.air_quality)} {dt:.2f}s | {r.reason}"
        print(line.encode("ascii", "replace").decode())
    (ROOT / "docs" / "evidence" / "llm_sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                                               encoding="utf-8")


if __name__ == "__main__":
    main()
