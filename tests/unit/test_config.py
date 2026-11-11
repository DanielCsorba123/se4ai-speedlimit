from pathlib import Path

import pytest

from speedlimit.config import Config, load_config

ROOT = Path(__file__).resolve().parents[2]


def test_config_defaults():
    cfg = load_config(ROOT / "config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.decide.candidate_limits == [40, 50, 60, 70, 80]
    assert cfg.decide.default_limit == 80
    assert cfg.decide.target_rate == 1.0
    assert cfg.decide.unreachable_epsilon == 0.05  # D25
    assert cfg.rules.dark_lux_threshold == 0.5  # SPEC1, D5
    assert cfg.rules.ice_water_um_threshold == 1000  # SPEC2
    assert cfg.rules.ice_temp_c_threshold == 0.0
    assert cfg.llm.timeout_s == 10  # D21
    assert cfg.air_quality.timeout_s == 5  # D21
    assert cfg.air_quality.latitude == 48.21  # D23
    assert cfg.drift.alpha == 0.05  # D21


def test_raw_files_resolve_to_existing_csvs():
    cfg = load_config(ROOT / "config.yaml")
    for p in (cfg.paths.readings_file, cfg.paths.readings_n1_file, cfg.paths.accidents_file,
              cfg.paths.sensors_file, cfg.paths.sensor_types_file):
        assert p.is_file(), p


def test_unknown_key_rejected(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text((ROOT / "config.yaml").read_text() + "\nrules_typo: {}\n")
    with pytest.raises(ValueError, match="rules_typo"):
        load_config(bad)


def test_api_key_never_in_config():
    import yaml

    text = (ROOT / "config.yaml").read_text()
    assert "sk-ant" not in text

    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield str(k).lower()
                yield from keys(v)

    import re

    secret = re.compile(r"(^|_)(api_?key|key|secret|token|password)$")
    assert not [k for k in keys(yaml.safe_load(text)) if secret.search(k)]


@pytest.mark.parametrize("name", [".env", ".env.txt"])
def test_dotenv_file_next_to_config_is_loaded(tmp_path, monkeypatch, name):
    import os
    monkeypatch.delenv("SPEEDLIMIT_TEST_KEY", raising=False)
    (tmp_path / "config.yaml").write_text((ROOT / "config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / name).write_text('SPEEDLIMIT_TEST_KEY="from-file"\n', encoding="utf-8")
    try:
        load_config(tmp_path / "config.yaml")
    except ValueError:
        pass                                  # copied config points at CSVs that are not in tmp; env is loaded first
    assert os.environ.get("SPEEDLIMIT_TEST_KEY") == "from-file"
    monkeypatch.delenv("SPEEDLIMIT_TEST_KEY", raising=False)


def test_dotenv_does_not_override_existing_env(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("SPEEDLIMIT_TEST_KEY", "from-shell")
    (tmp_path / "config.yaml").write_text((ROOT / "config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / ".env").write_text("SPEEDLIMIT_TEST_KEY=from-file\n", encoding="utf-8")
    load_config(tmp_path / "config.yaml")
    assert os.environ["SPEEDLIMIT_TEST_KEY"] == "from-shell"
