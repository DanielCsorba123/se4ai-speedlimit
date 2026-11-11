"""Streamlit operational stage (Task 8) via streamlit.testing.AppTest, fully offline."""
import json
import math
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from speedlimit import cli_train

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "src" / "speedlimit" / "app.py")
pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def models_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("models")
    cli_train.main(["--config", str(ROOT / "config.yaml"), "--models-dir", str(d),
                    "--reports-dir", str(tmp_path_factory.mktemp("reports"))])
    return d


@pytest.fixture
def env(monkeypatch, tmp_path, models_dir):
    monkeypatch.setenv("SPEEDLIMIT_OFFLINE", "1")
    monkeypatch.setenv("SPEEDLIMIT_MODELS_DIR", str(models_dir))
    monkeypatch.setenv("SPEEDLIMIT_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.chdir(ROOT)
    return tmp_path


def _run(**state):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    for key, value in state.items():
        at.session_state[key] = value
    if state:
        at.run()
    return at


def _texts(at):
    return " ".join([m.value for m in at.markdown] + [m.value for m in at.caption] +
                    [str(m.value) for m in at.metric] + [e.value for e in at.warning] + [e.value for e in at.info] +
                    [e.value for e in at.error])


def test_app_renders_without_exception(env):
    at = _run()
    assert not at.exception
    assert at.selectbox(key="sample").value is not None
    assert "km/h" in _texts(at)


def test_renders_default(env):
    """A daylight, dry, good-air hour gives 80 km/h (REQ3)."""
    at = _run()
    daylight = next(o for o in at.selectbox(key="sample").options if o.startswith("Jan 25 12:00"))
    at.selectbox(key="sample").set_value(daylight).run()
    at.slider(key="water").set_value(0.0).run()
    assert not at.exception
    assert at.metric[0].value == "80 km/h"
    assert "REQ3" in _texts(at)


def test_dark_input_reduces(env):
    at = _run()
    at.slider(key="log_lux").set_value(round(math.log10(0.2), 2)).run()
    assert not at.exception
    value = int(at.metric[0].value.split()[0])
    assert value <= 70                                       # D33: REQ1 always reduces
    assert "REQ1" in _texts(at)
    assert len(at.dataframe) >= 1                            # per-limit rate table


def test_unreachable_flag_visible(env, monkeypatch, tmp_path, models_dir):
    only_baseline = tmp_path / "baseline_only"
    only_baseline.mkdir()
    shutil.copy(models_dir / "baseline_table.json", only_baseline / "baseline_table.json")
    monkeypatch.setenv("SPEEDLIMIT_MODELS_DIR", str(only_baseline))
    at = _run()
    at.slider(key="log_lux").set_value(-1.0).run()
    text = _texts(at)
    assert not at.exception
    assert "NOT reachable" in text
    assert "baseline table" in text.lower()


def test_manual_aqi_shows_req2_source(env):
    at = _run()
    at.slider(key="log_lux").set_value(4.0).run()
    at.slider(key="water").set_value(0.0).run()
    at.number_input(key="manual_aqi").set_value(110.0).run()
    assert at.metric[0].value == "50 km/h"
    assert "manual" in _texts(at).lower()


def test_no_forecast_warns(env):
    at = _run()
    assert "air quality unknown" in _texts(at).lower()


def test_replay_next_hour_advances(env):
    at = _run()
    at.radio(key="mode").set_value("Replay").run()
    first = at.session_state["replay_idx"]
    at.button(key="next_hour").click().run()
    assert at.session_state["replay_idx"] == first + 1
    assert not at.exception


def test_decisions_are_logged_once_per_input(env):
    at = _run()
    at.run()                                                 # rerun without changes
    at.slider(key="log_lux").set_value(-1.0).run()
    rows = (env / "logs" / "decisions.jsonl").read_text().splitlines()
    assert len(rows) == 2
    assert not any("plate" in k.lower() for k in json.loads(rows[-1]))


def _scenario(name):
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["scenario"] = name
    at.run()
    return at


def test_scenario_at1_normal_day(env):
    at = _scenario("AT-1")
    assert not at.exception
    assert at.metric[0].value == "80 km/h" and "REQ3" in _texts(at)
    assert at.selectbox(key="sample").value.startswith("Jan 25 13:00")


def test_scenario_at4_threshold_pair(env):
    assert _scenario("AT-4a").metric[0].value == "80 km/h"          # water exactly 1000: no ice
    b = _scenario("AT-4b")
    assert int(b.metric[0].value.split()[0]) <= 70 and "black-ice" in _texts(b)


def test_scenario_at8_most_restrictive_wins(env):
    at = _scenario("AT-8")
    assert int(at.metric[0].value.split()[0]) <= 50
    assert "REQ2" in _texts(at)


def test_unknown_scenario_is_ignored(env):
    at = _scenario("nope")
    assert not at.exception and at.metric[0].value.endswith("km/h")
