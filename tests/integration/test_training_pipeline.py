import json
from pathlib import Path

import pytest

from speedlimit import cli_train
from speedlimit.features import FEATURES
from speedlimit.model import load

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.realdata
def test_training_pipeline_end_to_end(tmp_path):
    rc = cli_train.main(["--config", str(ROOT / "config.yaml"),
                         "--models-dir", str(tmp_path / "models"), "--reports-dir", str(tmp_path / "reports")])
    assert rc == 0
    latest = tmp_path / "models" / "latest.joblib"
    art = load(latest)
    assert art.features == FEATURES
    assert art.candidate_limits == [40, 50, 60, 70, 80]
    assert art.train_days == list(range(1, 25)) and art.test_days == list(range(25, 32))
    assert len(art.data_hash) == 64
    assert ("dark", 60) in art.baseline_table
    assert art.cell_counts[("dark", 80)] == 0           # never observed -> extrapolated (D32)
    metrics = json.loads((tmp_path / "reports" / "metrics.json").read_text())
    for k in ("mae", "poisson_dev", "mae_baseline", "skill", "dark_ice_only", "limit_sensitivity_raw",
              "reachable_share_raw"):
        assert k in metrics
    cards = list((tmp_path / "models").glob("model_card_*.md"))
    assert len(cards) == 1
    text = cards[0].read_text(encoding="utf-8")
    assert "F04" in text and "Known limitations" in text
    assert "plate" not in text.lower()


@pytest.mark.realdata
def test_training_reports_guarded_req1_outcome(tmp_path):
    cli_train.main(["--config", str(ROOT / "config.yaml"),
                    "--models-dir", str(tmp_path / "models"), "--reports-dir", str(tmp_path / "reports")])
    metrics = json.loads((tmp_path / "reports" / "metrics.json").read_text())
    assert metrics["limit_sensitivity_guarded"] <= 0                # guard: 40 never riskier than 70 (D9, D33)
    assert 0 <= metrics["reachable_share_guarded"] <= 1
    dist = metrics["req1_decisions"]                                 # chosen REQ1 limit over dark/ice test hours
    assert set(dist) <= {"40", "50", "60", "70"}                     # D33: never 80
    assert sum(dist.values()) == metrics["dark_ice_only"]["n"]
    table = json.loads((tmp_path / "models" / "baseline_table.json").read_text())
    assert table["dark|60"] > 0
    card = next((tmp_path / "models").glob("model_card_*.md")).read_text(encoding="utf-8")
    assert "after the D9 guard" in card
