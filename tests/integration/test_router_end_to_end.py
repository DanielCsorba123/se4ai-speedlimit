"""Router + combiner + audit log (REQ1-3, D16) end to end, without network."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from speedlimit import cli_train, llm_advisor
from speedlimit.audit import log_decision, read_log
from speedlimit.config import load_config
from speedlimit.decide import RuntimeContext, combine, decide
from speedlimit.domain import AQSummary, Req1Result, Req2Result, RuleResult, Situation
from speedlimit.features import FEATURES
from speedlimit.model import ModelArtefact, load

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")


class _SpyStub:
    def __init__(self, rates):
        self.rates, self.calls = rates, 0

    def predict(self, X):
        self.calls += 1
        return np.array([self.rates[int(v)] for v in X["speed_limit"]], dtype=float)


class _FakeLLM:
    def __init__(self, limit):
        self.limit, self.requests = limit, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def with_options(self, **kw):
        return self

    def _create(self, **kw):
        self.requests.append(kw)
        return SimpleNamespace(stop_reason="end_turn", model=kw["model"], content=[
            SimpleNamespace(type="text", text=json.dumps({"speed_limit": self.limit, "reason": "NO2 high."}))])


RATES = {40: .5, 50: .7, 60: .9, 70: 1.1, 80: 1.4}      # REQ1 -> 60


def _art(stub):
    return ModelArtefact(estimators=[stub], smearing_k=1.0, features=list(FEATURES), version="stub")


def _aq(eaqi):
    return AQSummary(lat=48.21, lon=16.37, decision_time=datetime(2026, 1, 6, 20), horizon_h=3, eaqi_max=eaqi,
                     eaqi_mean=eaqi, pm25_max=10, pm25_mean=10, pm10_max=20, pm10_mean=20, no2_max=30,
                     no2_mean=30, o3_max=40, o3_mean=40, eaqi_hourly=[int(eaqi)] * 3)


def _sit(**kw):
    base = dict(timestamp=datetime(2026, 1, 6, 12), lux=50000.0, water_um=0.0, temp_c=5.0, humidity=80.0,
                noise_db=90.0, wind_strength=10.0, wind_dir_deg=90.0, traffic_cps=10.0, current_limit=80)
    base.update(kw)
    return Situation(**base)


@pytest.fixture(autouse=True)
def _reset():
    llm_advisor.reset_state()


def test_req3_default():
    stub = _SpyStub(RATES)
    llm = _FakeLLM(50)
    d = decide(_sit(), RuntimeContext(cfg=CFG, art=_art(stub), aq_summary=_aq(30), llm_client=llm))
    assert d.limit == 80 and d.winning_reasons == ["REQ3"]
    assert stub.calls == 0 and llm.requests == []


def test_dark_uses_model():
    stub = _SpyStub(RATES)
    d = decide(_sit(lux=0.2), RuntimeContext(cfg=CFG, art=_art(stub), aq_summary=_aq(30)))
    assert stub.calls == 1 and d.limit == 60 and d.winning_reasons == ["REQ1"]
    assert d.req1.source == "model" and d.model_version == "stub"


def test_min_combination():
    d = decide(_sit(lux=0.2), RuntimeContext(cfg=CFG, art=_art(_SpyStub(RATES)), aq_summary=_aq(70),
                                             llm_client=_FakeLLM(50)))
    assert d.limit == 50 and d.winning_reasons == ["REQ2"]
    assert d.req1.limit == 60 and d.req2.source == "llm"


def test_tie_reports_both_reasons():
    rule = RuleResult(dark=True, black_ice=False)
    r1 = Req1Result(active=True, limit=60, rates_raw={}, rates_guarded={}, target_reachable=True, source="model")
    r2 = Req2Result(limit=60, reason="x", source="table", aq=None)
    assert combine(rule, r1, r2).winning_reasons == ["REQ1", "REQ2"]


def test_poor_air_only():
    d = decide(_sit(), RuntimeContext(cfg=CFG, art=None, aq_summary=_aq(85), llm_client=_FakeLLM(60)))
    assert d.limit == 60 and d.winning_reasons == ["REQ2"] and not d.req1.active


def test_all_external_down_dark_hour():
    """No forecast, no LLM: REQ1 still decides; REQ2 reports unknown air (D26)."""
    d = decide(_sit(lux=0.2), RuntimeContext(cfg=CFG, art=_art(_SpyStub(RATES)), aq_summary=None))
    assert d.limit == 60 and d.req2.source == "none" and "unknown" in d.req2.reason.lower()


def test_manual_aqi_overrides_forecast():
    d = decide(_sit(), RuntimeContext(cfg=CFG, art=None, aq_summary=_aq(30), manual_aqi=110))
    assert d.limit == 50 and d.req2.source == "manual"


def test_explanation_names_the_winner():
    d = decide(_sit(lux=0.2), RuntimeContext(cfg=CFG, art=_art(_SpyStub(RATES)), aq_summary=_aq(30)))
    assert "REQ1" in d.explanation and "60" in d.explanation


def test_log_has_no_plate(tmp_path):
    p = tmp_path / "decisions.jsonl"
    for s in (_sit(), _sit(lux=0.2)):
        log_decision(decide(s, RuntimeContext(cfg=CFG, art=_art(_SpyStub(RATES)), aq_summary=_aq(30))), p)
    rows = [json.loads(line) for line in p.read_text().splitlines()]
    assert len(rows) == 2
    keys = {k.lower() for r in rows for k in r}
    assert not any("plate" in k for k in keys)
    assert {"final_limit", "winning_reasons", "dark", "black_ice", "req1_rates_guarded", "req2_source",
            "lux"} <= keys


def test_read_log_returns_latest_rows(tmp_path):
    p = tmp_path / "decisions.jsonl"
    for lux in (50000.0, 0.2, 0.1):
        log_decision(decide(_sit(lux=lux), RuntimeContext(cfg=CFG, art=_art(_SpyStub(RATES)),
                                                          aq_summary=_aq(30))), p)
    df = read_log(p, n=2)
    assert len(df) == 2 and df.final_limit.tolist() == [60, 60]
    assert read_log(tmp_path / "missing.jsonl").empty


@pytest.mark.realdata
def test_real_model_dark_hour(tmp_path):
    """Trained artefact on the real Jan 6 20:00 situation (dark, -4.8 degC): REQ1 must reduce."""
    cli_train.main(["--config", str(ROOT / "config.yaml"), "--models-dir", str(tmp_path / "m"),
                    "--reports-dir", str(tmp_path / "r")])
    art = load(tmp_path / "m" / "latest.joblib")
    s = _sit(timestamp=datetime(2026, 1, 6, 20), lux=0.08, water_um=0.0, temp_c=-4.8, humidity=85.0,
             noise_db=90.0, wind_strength=10.0, wind_dir_deg=180.0, traffic_cps=12.0, current_limit=60)
    d = decide(s, RuntimeContext(cfg=CFG, art=art, aq_summary=None))
    assert d.rule.dark and d.req1.source == "model"
    assert d.limit in (40, 50, 60, 70)
    assert d.req1.extrapolated == (80,)
