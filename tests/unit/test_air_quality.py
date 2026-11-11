"""Air-quality forecast: parsing, summary, table (D15, D30), outage handling (D26). No network."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import requests

from speedlimit import air_quality as aq
from speedlimit.config import load_config

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")
NOW = datetime(2026, 1, 6, 20, 15)


def _payload(aqi=(30, 70, 95, 40), start=datetime(2026, 1, 6, 19)):
    n = len(aqi)
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(n)]
    return {"hourly": {"time": times, "european_aqi": list(aqi), "pm2_5": [10.0] * n, "pm10": [20.0] * n,
                       "nitrogen_dioxide": [30.0] * (n - 1) + ["n/a"], "ozone": [None] * n}}


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def _clear_cache():
    aq.clear_cache()


def test_table_boundaries():
    got = {a: aq.table_limit(a, CFG.air_quality) for a in (60, 61, 80, 81, 100, 101)}
    assert got == {60: 80, 61: 70, 80: 70, 81: 60, 100: 60, 101: 50}


def test_table_rounds_non_integer_aqi():
    assert aq.table_limit(60.4, CFG.air_quality) == 80     # D30: rounds to 60
    assert aq.table_limit(60.6, CFG.air_quality) == 70     # rounds to 61


def test_fetch_parses_numbers_only():
    s = _Session(_Resp(_payload()))
    fc = aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW)
    assert fc.european_aqi == [30, 70, 95, 40]
    assert fc.no2[-1] != fc.no2[-1]                        # "n/a" -> NaN
    assert s.calls[0]["timeout"] == 5                      # D21
    assert "european_aqi" in s.calls[0]["params"]["hourly"]


def test_http_503_returns_none():
    s = _Session(_Resp({}, status=503))
    assert aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW) is None


def test_timeout_returns_none():
    s = _Session(requests.Timeout("slow"))
    assert aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW) is None


def test_outage_uses_cache_up_to_3h():
    s = _Session(_Resp(_payload()), requests.ConnectionError("down"), requests.ConnectionError("down"))
    aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW)
    later = aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW + timedelta(hours=2))
    assert later is not None and later.from_cache
    too_late = aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW + timedelta(hours=4))
    assert too_late is None


def test_fresh_cache_avoids_second_request():
    s = _Session(_Resp(_payload()))
    aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW)
    aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW + timedelta(minutes=5))
    assert len(s.calls) == 1


def test_summarise_uses_horizon_from_current_hour():
    fc = aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=_Session(_Resp(_payload())), now=NOW)
    sm = aq.summarise(fc, 3, now=NOW)
    assert sm.eaqi_hourly == [70, 95, 40]                  # 20h, 21h, 22h (19h is past)
    assert sm.eaqi_max == 95 and sm.eaqi_mean == pytest.approx(205 / 3)
    assert sm.horizon_h == 3 and sm.lat == 48.21


def test_is_poor_threshold():
    assert not aq.is_poor(60, CFG.air_quality)
    assert aq.is_poor(61, CFG.air_quality)


def test_failed_fetch_is_not_retried_immediately():
    """Review I-3: a hanging Open-Meteo must not cost a full timeout on every rerun."""
    s = _Session(requests.Timeout("slow"), _Resp(_payload()))
    assert aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW) is None
    assert aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW + timedelta(seconds=30)) is None
    assert len(s.calls) == 1
    later = aq.fetch_forecast(48.21, 16.37, CFG.air_quality, session=s, now=NOW + timedelta(minutes=2))
    assert later is not None and len(s.calls) == 2


def test_simulated_summary_for_demo():
    """D38: a demo forecast with a chosen EAQI, sent through the real LLM path."""
    s = aq.simulated_summary(92.0, CFG.air_quality, now=NOW)
    assert s.eaqi_max == 92.0 and s.eaqi_hourly[1] == 92 and len(s.eaqi_hourly) == CFG.air_quality.horizon_hours
    assert s.lat == CFG.air_quality.latitude
    assert s.pm10_max > 0 and s.no2_max > 0
