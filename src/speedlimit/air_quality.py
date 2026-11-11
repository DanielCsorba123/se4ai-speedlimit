"""Air-quality forecast from Open-Meteo (REQ2, D14) with outage handling (D26).

Only numbers from the API are kept: every value is parsed with float() and
anything else becomes NaN, so no API string can ever reach the LLM prompt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

import requests

from speedlimit.config import AQConfig
from speedlimit.domain import AQSummary

URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
HOURLY = ["european_aqi", "pm2_5", "pm10", "nitrogen_dioxide", "ozone"]
_CACHE: dict[tuple[float, float], tuple[datetime, "AQForecast"]] = {}


@dataclass(frozen=True)
class AQForecast:
    lat: float
    lon: float
    times: list[datetime]
    european_aqi: list[float]
    pm2_5: list[float]
    pm10: list[float]
    no2: list[float]
    o3: list[float]
    fetched_at: datetime
    from_cache: bool = False


def clear_cache() -> None:
    _CACHE.clear()


def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return math.nan
    return f if math.isfinite(f) else math.nan


def _parse(payload: dict, lat: float, lon: float, now: datetime) -> AQForecast:
    h = payload["hourly"]
    times = [datetime.fromisoformat(t) for t in h["time"]]
    col = {k: [_num(v) for v in h.get(k, [None] * len(times))] for k in HOURLY}
    return AQForecast(lat=lat, lon=lon, times=times, european_aqi=col["european_aqi"], pm2_5=col["pm2_5"],
                      pm10=col["pm10"], no2=col["nitrogen_dioxide"], o3=col["ozone"], fetched_at=now)


def fetch_forecast(lat: float, lon: float, cfg: AQConfig, session=None, now: datetime | None = None
                   ) -> AQForecast | None:
    """Forecast for (lat, lon); None if unavailable and no cache <= max_cache_age_h (D26)."""
    now = now or datetime.now()
    key = (round(lat, 3), round(lon, 3))
    cached = _CACHE.get(key)
    if cached and now - cached[0] <= timedelta(minutes=cfg.cache_ttl_min):
        return cached[1]
    http = session or requests
    try:
        resp = http.get(URL, params={"latitude": lat, "longitude": lon, "hourly": ",".join(HOURLY),
                                     "forecast_days": 2, "timezone": "Europe/Vienna"},
                        timeout=cfg.timeout_s)
        resp.raise_for_status()
        fc = _parse(resp.json(), lat, lon, now)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        if cached and now - cached[0] <= timedelta(hours=cfg.max_cache_age_h):
            return replace(cached[1], from_cache=True)
        return None
    _CACHE[key] = (now, fc)
    return fc


def _stats(values: list[float]) -> tuple[float, float]:
    v = [x for x in values if not math.isnan(x)]
    return (max(v), sum(v) / len(v)) if v else (math.nan, math.nan)


def summarise(fc: AQForecast, horizon_h: int, now: datetime | None = None) -> AQSummary:
    """Max / mean over the next horizon_h forecast hours, starting at the current hour."""
    now = now or datetime.now()
    start = now.replace(minute=0, second=0, microsecond=0)
    idx = [i for i, t in enumerate(fc.times) if t >= start][:horizon_h]
    pick = lambda xs: [xs[i] for i in idx]  # noqa: E731
    eq, p25, p10, no2, o3 = (_stats(pick(x)) for x in (fc.european_aqi, fc.pm2_5, fc.pm10, fc.no2, fc.o3))
    return AQSummary(lat=fc.lat, lon=fc.lon, decision_time=start, horizon_h=horizon_h,
                     eaqi_max=eq[0], eaqi_mean=eq[1], pm25_max=p25[0], pm25_mean=p25[1],
                     pm10_max=p10[0], pm10_mean=p10[1], no2_max=no2[0], no2_mean=no2[1],
                     o3_max=o3[0], o3_mean=o3[1],
                     eaqi_hourly=[int(round(x)) for x in pick(fc.european_aqi) if not math.isnan(x)])


def table_limit(eu_aqi: float, cfg: AQConfig) -> int:
    """D15 fallback table; non-integer AQI rounded first (D30)."""
    a = round(float(eu_aqi))
    for upper, limit in cfg.fallback_table:
        if a <= float(upper):
            return int(limit)
    return int(cfg.fallback_table[-1][1])


def is_poor(eu_aqi: float, cfg: AQConfig) -> bool:
    """D14: poor air quality = EU AQI above the threshold (60)."""
    return round(float(eu_aqi)) > cfg.poor_aqi_threshold
