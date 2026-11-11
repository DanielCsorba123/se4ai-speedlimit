"""LLM advisor on the Groq provider (default since 2026-11-11), fake client, no network."""
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


class _FakeGroq:
    """Mimics groq.Groq: client.with_options(...).chat.completions.create(...)."""

    def __init__(self, content=None, finish_reason="stop", exc=None):
        self.content, self.finish_reason, self.exc = content, finish_reason, exc
        self.requests, self.options = [], []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **kw):
        self.options.append(kw)
        return self

    def _create(self, **kw):
        self.requests.append(kw)
        if self.exc:
            raise self.exc
        msg = SimpleNamespace(content=self.content, role="assistant")
        return SimpleNamespace(model=kw["model"], choices=[SimpleNamespace(finish_reason=self.finish_reason,
                                                                           message=msg)])


@pytest.fixture(autouse=True)
def _reset():
    la.reset_state()


def _ok(limit=60, reason="EAQI 95 is very poor; NO2 80."):
    return _FakeGroq(json.dumps({"speed_limit": limit, "reason": reason}))


def test_default_provider_is_groq():
    assert CFG.llm.provider == "groq"
    assert CFG.llm.model == "openai/gpt-oss-120b"


def test_groq_request_shape():
    c = _ok()
    la.advise(_summary(), CFG, client=c)
    req = c.requests[0]
    assert req["model"] == "openai/gpt-oss-120b"
    rf = req["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"]["properties"]["speed_limit"]["enum"] == [40, 50, 60, 70, 80]
    assert [m["role"] for m in req["messages"]] == ["system", "user"]
    assert "European AQI: 95 / 85" in req["messages"][1]["content"]
    for anthropic_only in ("betas", "fallbacks", "output_config", "system"):
        assert anthropic_only not in req
    assert c.options[0] == {"timeout": 10, "max_retries": 0}                    # D21, D34


def test_groq_valid_json_used():
    r = la.advise(_summary(), CFG, client=_ok())
    assert (r.limit, r.source) == (60, "llm")


def test_groq_truncated_answer_falls_back():
    r = la.advise(_summary(), CFG, client=_FakeGroq('{"speed_limit": 60, "rea', finish_reason="length"))
    assert r.source == "table"


def test_groq_prose_falls_back():
    assert la.advise(_summary(), CFG, client=_FakeGroq("I suggest 60.")).source == "table"


def test_groq_error_falls_back():
    import groq
    err = groq.APITimeoutError(request=None)
    r = la.advise(_summary(), CFG, client=_FakeGroq(exc=err))
    assert r.source == "table" and "timeout" in r.reason.lower()


def test_groq_implausible_answer_rejected():
    r = la.advise(_summary(eaqi_max=120.0), CFG, client=_ok(limit=80, reason="fine"))
    assert (r.source, r.limit) == ("table", 50)


def test_missing_key_falls_back(monkeypatch):
    """No GROQ_API_KEY: constructing the real client fails -> table, never a crash."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = la.advise(_summary(), CFG, client=None)
    assert r.source == "table"
