import dataclasses
from datetime import datetime

import pytest

from speedlimit.domain import AQSummary, Decision, Req1Result, Req2Result, RuleResult, Situation


def _situation(**kw):
    base = dict(timestamp=datetime(2026, 1, 6, 20), lux=0.08, water_um=0.0, temp_c=-4.8,
                humidity=85.0, noise_db=90.0, wind_strength=10.0, wind_dir_deg=180.0,
                traffic_cps=12.0, current_limit=60)
    base.update(kw)
    return Situation(**base)


def test_situation_is_frozen():
    s = _situation()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.lux = 1.0


def test_rule_result_req1_active_when_dark_or_ice():
    assert RuleResult(dark=True, black_ice=False).req1_active
    assert RuleResult(dark=False, black_ice=True).req1_active
    assert not RuleResult(dark=False, black_ice=False).req1_active


def test_decision_holds_all_parts():
    r1 = Req1Result(active=True, limit=60, rates_raw={60: 1.2}, rates_guarded={60: 1.2},
                    target_reachable=False, source="model")
    aq = AQSummary(lat=48.21, lon=16.37, decision_time=datetime(2026, 1, 6, 20), horizon_h=3,
                   eaqi_max=45, eaqi_mean=40, pm25_max=10, pm25_mean=8, pm10_max=20, pm10_mean=15,
                   no2_max=30, no2_mean=25, o3_max=50, o3_mean=40, eaqi_hourly=[40, 42, 45])
    r2 = Req2Result(limit=80, reason="good air", source="table", aq=aq)
    d = Decision(limit=60, winning_reasons=["REQ1"], rule=RuleResult(dark=True, black_ice=False),
                 req1=r1, req2=r2, explanation="dark", model_version="test")
    assert d.limit == 60 and d.req1.source == "model" and d.req2.aq.eaqi_max == 45


def test_situation_has_no_licence_plate_field():
    names = {f.name.lower() for f in dataclasses.fields(Situation)}
    assert not any("plate" in n for n in names)  # D20
