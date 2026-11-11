"""LLM advisor (REQ2, D14, D15, D26) with a fake Anthropic client. No network."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from speedlimit import llm_advisor as la
from speedlimit.config import load_config
from speedlimit.domain import AQSummary

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")


def _summary(eaqi_max=95.0):
    return AQSummary(lat=48.21, lon=16.37, decision_time=datetime(2026, 1, 6, 20), horizon_h=3,
                     eaqi_max=eaqi_max, eaqi_mean=eaqi_max - 10, pm25_max=40.0, pm25_mean=35.0, pm10_max=60.0,
                     pm10_mean=50.0, no2_max=80.0, no2_mean=70.0, o3_max=30.0, o3_mean=25.0,
                     eaqi_hourly=[int(eaqi_max) - 20, int(eaqi_max), int(eaqi_max) - 10])


class _FakeClient:
    def __init__(self, text=None, stop_reason="end_turn", exc=None):
        self.text, self.stop_reason, self.exc = text, stop_reason, exc
        self.requests, self.options = [], []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def with_options(self, **kw):
        self.options.append(kw)
        return self

    def _create(self, **kw):
        self.requests.append(kw)
        if self.exc:
            raise self.exc
        return SimpleNamespace(stop_reason=self.stop_reason, model=kw["model"],
                               content=[SimpleNamespace(type="text", text=self.text)])


@pytest.fixture(autouse=True)
def _reset():
    la.reset_state()


def _ok(limit=60, reason="EAQI 95 is very poor; NO2 80."):
    return _FakeClient(json.dumps({"speed_limit": limit, "reason": reason}))


def test_valid_llm_json_used():
    r = la.advise(_summary(), CFG, client=_ok())
    assert (r.limit, r.source) == (60, "llm")
    assert "EAQI" in r.reason and r.aq.eaqi_max == 95


def test_request_shape():
    c = _ok()
    la.advise(_summary(), CFG, client=c)
    req = c.requests[0]
    assert req["model"] == CFG.llm.model
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["output_config"]["format"]["schema"]["properties"]["speed_limit"]["enum"] == [40, 50, 60, 70, 80]
    assert req["output_config"]["effort"] == "low"
    assert "temperature" not in req and "thinking" not in req
    assert req["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in req["betas"]
    assert c.options[0] == {"timeout": 10, "max_retries": 0}            # D21, review I-3
    user = req["messages"][0]["content"]
    assert "European AQI: 95 / 85" in user and "lat 48.210" in user


def test_prose_falls_back():
    r = la.advise(_summary(), CFG, client=_FakeClient("I would suggest 60 km/h."))
    assert (r.source, r.limit) == ("table", 60)          # table: EAQI 95 -> 60


def test_limit_outside_set_falls_back():
    r = la.advise(_summary(), CFG, client=_ok(limit=65))
    assert r.source == "table"


def test_extra_key_falls_back():
    c = _FakeClient(json.dumps({"speed_limit": 60, "reason": "x", "note": "y"}))
    assert la.advise(_summary(), CFG, client=c).source == "table"


def test_timeout_falls_back():
    r = la.advise(_summary(), CFG, client=_FakeClient(exc=TimeoutError("slow")))
    assert r.source == "table" and "timeout" in r.reason.lower()


def test_refusal_falls_back():
    r = la.advise(_summary(), CFG, client=_FakeClient("{}", stop_reason="refusal"))
    assert r.source == "table"


def test_implausible_llm_rejected():
    """D26: AQI 120 -> table says 50; LLM saying 80 is more than 10 km/h looser."""
    r = la.advise(_summary(eaqi_max=120.0), CFG, client=_ok(limit=80, reason="fine"))
    assert (r.source, r.limit) == ("table", 50)


def test_stricter_llm_answer_accepted():
    r = la.advise(_summary(eaqi_max=70.0), CFG, client=_ok(limit=50, reason="NO2 high"))
    assert (r.source, r.limit) == ("llm", 50)


def test_good_air_needs_no_llm():
    c = _ok()
    r = la.advise(_summary(eaqi_max=45.0), CFG, client=c)
    assert (r.limit, r.source) == (80, "none") and c.requests == []


def test_unknown_air_quality():
    r = la.advise(None, CFG, client=_ok())
    assert (r.limit, r.source, r.aq) == (80, "none", None)
    assert "unknown" in r.reason.lower()


def test_manual_aqi_uses_table():
    r = la.manual_limit(85, CFG)
    assert (r.limit, r.source) == (60, "manual")


def test_cache_avoids_second_call():
    c = _ok()
    la.advise(_summary(), CFG, client=c)
    la.advise(_summary(), CFG, client=c)
    assert len(c.requests) == 1


def test_reason_is_truncated_plain_text():
    r = la.advise(_summary(), CFG, client=_ok(reason="x" * 290))
    assert r.source == "llm" and len(r.reason) <= 300
    long = la.advise(_summary(eaqi_max=96.0), CFG, client=_ok(reason="y" * 400))
    assert long.source == "table"                          # V3: reason > 300 chars is invalid


def test_calls_are_logged_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret")
    log = tmp_path / "llm_calls.jsonl"
    la.advise(_summary(), CFG, client=_ok(), log_path=log)
    line = json.loads(log.read_text().splitlines()[0])
    assert line["source"] == "llm" and line["model"] == CFG.llm.model
    assert "sk-ant" not in log.read_text()


def test_failed_call_is_not_retried_on_every_rerun():
    """Review I-3: after a timeout the table result is cached briefly, so reruns do not block again."""
    c = _FakeClient(exc=TimeoutError("slow"))
    a = la.advise(_summary(), CFG, client=c)
    b = la.advise(_summary(), CFG, client=c)
    assert a.source == b.source == "table"
    assert len(c.requests) == 1


def test_no_sdk_retries_so_timeout_is_the_deadline():
    c = _ok()
    la.advise(_summary(), CFG, client=c)
    assert c.options[0]["max_retries"] == 0                 # one 10 s attempt (D21), not 2 x 10 s
