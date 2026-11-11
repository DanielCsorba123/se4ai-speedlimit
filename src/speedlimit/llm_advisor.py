"""LLM air-quality advisor (REQ2, architecture §7, D14, D15, D26).

Claude chooses one of five limits from a numeric forecast. Every answer is
validated (V1-V5); anything invalid, late, refused or implausible falls back
to the deterministic AQI table, so the safety-relevant output never depends
on the LLM alone.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

from speedlimit.air_quality import is_poor, table_limit
from speedlimit.config import Config
from speedlimit.domain import AQSummary, Req2Result

LIMITS = [40, 50, 60, 70, 80]
MAX_REASON = 300
FALLBACK_BETA = "server-side-fallback-2026-07-01"
SCHEMA = {
    "type": "object",
    "properties": {
        "speed_limit": {"type": "integer", "enum": LIMITS},
        "reason": {"type": "string"},
    },
    "required": ["speed_limit", "reason"],
    "additionalProperties": False,
}
SYSTEM_PROMPT = """You are the air-quality advisor of a highway speed-limit control system in Europe.
Your only task: decide whether the speed limit on the highway section should be
reduced because of poor predicted air quality, and by how much.

Rules you must follow:
1. Allowed speed limits are exactly 40, 50, 60, 70 or 80 km/h. 80 means "no reduction".
2. Base your decision only on the numeric forecast values given in the user message.
   The European Air Quality Index (EAQI) bands are: 0-20 good, 20-40 fair,
   40-60 moderate, 60-80 poor, 80-100 very poor, above 100 extremely poor.
3. Lower speeds reduce traffic emissions (NO2, PM10 from abrasion). Recommend a
   reduction only when the forecast shows poor or worse air quality within the
   forecast window, or when one pollutant is clearly at a poor level even if the
   overall index is borderline.
4. Be proportionate: the worse and the longer the predicted pollution, the lower the
   limit. Do not go below 50 km/h unless the index is above 100.
5. Other reasons (darkness, ice, accidents) are handled by other parts of the system.
   Ignore them.
6. Answer only with the JSON object defined by the schema. The "reason" must be one
   or two plain sentences (max 300 characters) that name the values you relied on."""

_cache: dict[str, tuple[datetime, Req2Result]] = {}
_calls: dict[str, int] = {}


class InvalidAdvice(ValueError):
    pass


def reset_state() -> None:
    _cache.clear()
    _calls.clear()


def build_prompt(s: AQSummary) -> tuple[str, str]:
    user = (
        f"Air-quality forecast for the highway location (lat {s.lat:.3f}, lon {s.lon:.3f}).\n"
        f"Decision time: {s.decision_time.isoformat(timespec='minutes')} (local time).\n"
        f"Forecast window: next {s.horizon_h} hours.\n\n"
        "Values for the window (max / mean):\n"
        f"- European AQI: {s.eaqi_max:.0f} / {s.eaqi_mean:.0f}\n"
        f"- PM2.5 (ug/m3): {s.pm25_max:.1f} / {s.pm25_mean:.1f}\n"
        f"- PM10 (ug/m3): {s.pm10_max:.1f} / {s.pm10_mean:.1f}\n"
        f"- NO2 (ug/m3): {s.no2_max:.1f} / {s.no2_mean:.1f}\n"
        f"- O3 (ug/m3): {s.o3_max:.1f} / {s.o3_mean:.1f}\n\n"
        f"Hourly European AQI for the window: {', '.join(str(int(x)) for x in s.eaqi_hourly)}\n\n"
        "Return the speed limit for the coming hour."
    )
    return SYSTEM_PROMPT, user


def validate(raw: str, summary: AQSummary, cfg: Config) -> tuple[int, str]:
    """V2-V4. Returns (limit, reason) or raises InvalidAdvice."""
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as e:
        raise InvalidAdvice("answer is not JSON") from e
    if not isinstance(data, dict) or set(data) != {"speed_limit", "reason"}:
        raise InvalidAdvice("answer does not match the schema")
    limit, reason = data["speed_limit"], data["reason"]
    if not isinstance(limit, int) or isinstance(limit, bool) or limit not in LIMITS:
        raise InvalidAdvice(f"speed_limit {limit!r} not allowed")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > MAX_REASON:
        raise InvalidAdvice("reason missing or longer than 300 characters")
    table = table_limit(summary.eaqi_max, cfg.air_quality)
    if limit > table + cfg.llm.plausibility_margin_kmh:                          # V4 / D26
        raise InvalidAdvice(f"implausible: LLM {limit} vs table {table}")
    return limit, reason.strip()


def _table_result(summary: AQSummary, cfg: Config, why: str) -> Req2Result:
    limit = table_limit(summary.eaqi_max, cfg.air_quality)
    return Req2Result(limit=limit, reason=f"Table: EAQI max {summary.eaqi_max:.0f} -> {limit} km/h ({why}).",
                      source="table", aq=summary)


def manual_limit(eu_aqi: float, cfg: Config) -> Req2Result:
    """AQI typed by the operator (D26 step 2, D31)."""
    limit = table_limit(eu_aqi, cfg.air_quality) if is_poor(eu_aqi, cfg.air_quality) else 80
    return Req2Result(limit=limit, reason=f"Manual EAQI {eu_aqi:.0f} -> {limit} km/h.", source="manual", aq=None)


def _log(path: Path | None, entry: dict) -> None:
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _call(client, system: str, user: str, cfg: Config):
    kwargs = dict(
        model=cfg.llm.model, max_tokens=cfg.llm.max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}, "effort": cfg.llm.effort},
    )
    if cfg.llm.server_fallback:
        kwargs |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}
    return client.with_options(timeout=cfg.llm.timeout_s, max_retries=cfg.llm.max_retries).beta.messages.create(
        **kwargs)


def advise(summary: AQSummary | None, cfg: Config, client=None, log_path: Path | None = None,
           now: datetime | None = None) -> Req2Result:
    now = now or datetime.now()
    if summary is None or math.isnan(summary.eaqi_max):
        return Req2Result(limit=80, reason="Air quality unknown: no forecast available (no REQ2 reduction).",
                          source="none", aq=None)
    if not is_poor(summary.eaqi_max, cfg.air_quality):
        return Req2Result(limit=80, reason=f"Air quality not poor (EAQI max {summary.eaqi_max:.0f}).",
                          source="none", aq=summary)
    if not cfg.llm.enabled:
        return _table_result(summary, cfg, "LLM disabled")

    system, user = build_prompt(summary)
    key = hashlib.sha256(f"{cfg.llm.model}|{cfg.llm.prompt_version}|{user}".encode()).hexdigest()
    hit = _cache.get(key)
    if hit:
        ttl = cfg.llm.cache_ttl_min if hit[1].source == "llm" else cfg.llm.fallback_cache_min
        if now - hit[0] <= timedelta(minutes=ttl):
            return hit[1]
    day = now.strftime("%Y-%m-%d")
    if _calls.get(day, 0) >= cfg.llm.max_calls_per_day:
        return _table_result(summary, cfg, "daily LLM budget reached")
    _calls[day] = _calls.get(day, 0) + 1

    entry = {"ts": now.isoformat(), "model": cfg.llm.model, "prompt_version": cfg.llm.prompt_version}
    t0 = time.perf_counter()
    try:
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        resp = _call(client, system, user, cfg)
        entry |= {"stop_reason": resp.stop_reason, "served_by": getattr(resp, "model", None)}
        if resp.stop_reason != "end_turn":                                           # V1
            raise InvalidAdvice(f"stop_reason {resp.stop_reason}")
        raw = next((b.text for b in resp.content if b.type == "text"), "")
        entry["raw"] = raw
        limit, reason = validate(raw, summary, cfg)                                  # V2-V4
        result = Req2Result(limit=limit, reason=reason, source="llm", aq=summary)
    except InvalidAdvice as e:
        result = _table_result(summary, cfg, f"invalid LLM answer: {e}")
    except TimeoutError:
        result = _table_result(summary, cfg, "LLM timeout")
    except Exception as e:  # SDK errors (timeout, connection, status) -> fallback, never crash (D15)
        why = "LLM timeout" if "timeout" in type(e).__name__.lower() else f"LLM error {type(e).__name__}"
        result = _table_result(summary, cfg, why)
    entry |= {"latency_ms": round((time.perf_counter() - t0) * 1000), "source": result.source,
              "limit": result.limit}
    _log(log_path, entry)
    _cache[key] = (now, result)          # fallbacks too, briefly: a hung LLM must not block every rerun
    return result
