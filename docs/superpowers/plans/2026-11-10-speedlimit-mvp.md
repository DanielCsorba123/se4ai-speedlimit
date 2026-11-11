# SpeedLimit MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SpeedLimit MVP. It has a training pipeline that turns the raw CSVs into a trained neural network, and a Streamlit GUI that sets the speed limit from entered (or replayed) sensor values plus an LLM air-quality advice. It also produces the evidence for the management presentation.

**Architecture:** A Python package `src/speedlimit/` with one module per responsibility (architecture §4): `io_load → cleaning → features → model`, plus `rules`, `decide` (router + combiner), `air_quality` + `llm_advisor`, `drift` and `audit`. `cli_train` writes a joblib `ModelArtefact`. `app.py` (Streamlit) loads it and routes each `Situation` to REQ3 (default), REQ1 (NN sweep) or REQ2 (LLM), combined by `min()`.

**Tech Stack:** Python 3.13, pandas 3, numpy, scikit-learn (MLPRegressor in a TransformedTargetRegressor), joblib, Streamlit, anthropic SDK, requests, scipy (KS test), pytest.

**Spec:** `docs/02-requirements-specification.md` (requirements) · `docs/04-solution-architecture.md` (design; the source of all names below) · `docs/05-decision-log.md` (binding decisions D1–D29) · `docs/07-test-strategy.md` (TC catalogue)

## Global Constraints

- Default limit is exactly **80** km/h. Candidate limits are exactly `[40, 50, 60, 70, 80]` (D7).
- Dark: mean lux `< 0.5`. Black ice: mean water `> 1000` µm **and** mean temp `< 0` °C. Both are strict inequalities (D5).
- REQ1 target: guarded predicted near-accidents per hour `<= 1.0` (D7, D9). When unreachable, take the highest limit within ε = 0.05/h of the best (D25).
- Accident hour mapping: `reading_hour = accident_hour - 1` (D1).
- Sensor groups (D2–D4): water `[1, 8, 11]`, light `[2, 9, 12]`, noise `[3]`, humidity `[4]`, wind direction `[5, 13]`, wind strength `[6, 14]`, temperature `[15, 18, 19]`, traffic `[16]`, speed limit `-1`. Sensors 7, 10 and 17 are ignored.
- `LicencePlate` is dropped at read time and never appears in any output, log or artefact (D20).
- Final limit = `min(REQ1 limit if dark or ice, REQ2 limit if EU AQI > 60, 80)` (D14, D16).
- LLM output must be JSON `{"speed_limit": int in {40,50,60,70,80}, "reason": str}`. Anything else goes to the AQI table (D15): EU AQI ≤ 60 → 80, 61–80 → 70, 81–100 → 60, > 100 → 50.
- Timeouts and targets (D21): LLM 10 s, air-quality API 5 s, ≤ 2 s per decision, ≤ 5 min training, drift α = 0.05.
- Air-quality location default: 48.21 N, 16.37 E, configurable (D23).
- API keys come only from environment variables (`ANTHROPIC_API_KEY`) and are never committed.
- Seeds `0..4` for the 5-member ensemble (architecture §5.2).
- CSV read: `sep=";"`, `decimal=","`, `encoding="utf-8-sig"`. The N+1 readings file has no header.

## Review Focus

1. **Inputs exactly on a threshold** (lux = 0.5, water = 1000, temp = 0): none of them triggers a reduction. → Test in Task 3.
2. **The model predicts > 1.0 for every candidate**: the system still outputs the highest limit within ε of the best rate (D25), sets `target_reachable=False`, and the GUI shows the flag. → Tests in Tasks 5 and 8.
3. **Non-monotonic predictions** (40 km/h predicted more dangerous than 60): after `monotone_guard`, rates must not increase as the limit decreases. → Test in Task 5.
4. **Air-quality API or LLM down, slow or returning prose**: the decision still completes within the timeout, with `Req2Result.source == "table"` (or `"none"` when no AQ data exists). → Test in Task 6.
5. **Dirty data versions** (NULL month, "January" as text, missing sensor ID, wind direction 400°, duplicated day): cleaning repairs or drops each one without crashing. → Test in Task 2.

---

## Backlog overview

| # | Task | Exercise covered (deck) | Perspective | Depends on |
|---|---|---|---|---|
| 0 | Project scaffold, config, shared types | all | Lead | – |
| 1 | Data loading (robust CSV IO) | Development (slide 18) | Data eng. | 0 |
| 2 | Cleaning rules (incl. slide-17 fault classes) + hourly table | Data prep (16–18) | Data eng. | 1 |
| 3 | Features + condition rules | Feature eng. (16), SPEC1/2 | Data/ML | 2 |
| 4 | Model training, evaluation, model card | Training stage (32), SPEC3 | ML | 3 |
| 5 | REQ1 decision: candidate sweep + monotone guard | REQ1 | ML | 4 |
| 6 | REQ2 air quality + LLM advisor + table fallback | REQ2 | Integration | 0 |
| 7 | Router/combiner + audit log | REQ1–3, D16 | Architecture | 3, 5, 6 |
| 8 | Streamlit GUI (manual + replay) | Operational stage (32) | Frontend | 7 |
| 9 | Drift check on year N+1 | Retraining (19) | ML/QA | 3 |
| 10 | Acceptance run + screenshots for deck | all | QA | 8, 9 |
| 11 | Management presentation | Main exercise (32) | Lead | 10 |
| 12 | UML set (class, component, sequence, activity) | Data prep (16), Arc diag (15) | Architecture | 0 (refine after 8) |

Task 6 can run in parallel with 1–5. Task 12 can start right away from the design docs.

---

### Task 0: Project scaffold, config, shared types

**Files:** Create `pyproject.toml`, `config.yaml`, `.gitignore`, `README.md`, `src/speedlimit/{__init__,config,types}.py`, `tests/conftest.py`, `tests/fixtures/` (2 days of readings, 20 accident rows, both metadata files, plus fault-injected variants for Task 2)

**Interfaces:**
- Produces: `load_config(path: Path = Path("config.yaml")) -> Config`, and in `types.py` the dataclasses `Situation`, `RuleResult`, `Req1Result`, `Req2Result`, `Decision` exactly as in architecture §4.3.

- [ ] **Step 1:** Run `git init` and create the `.gitignore` (`.venv/`, `models/`, `logs/`, `__pycache__/`, `.env`).
- [ ] **Step 2:** Write the failing test `test_config_defaults`: it asserts `cfg.decide.candidate_limits == [40,50,60,70,80]`, `cfg.decide.default_limit == 80`, `cfg.rules.lux_dark == 0.5`, `cfg.llm.timeout_s == 10` and `cfg.aq.lat == 48.21`.
- [ ] **Step 3:** Implement `config.py` (typed sections built from YAML) and `types.py` (frozen dataclasses).
- [ ] **Step 4:** Run `pytest -q`. Expected: 1 passed.
- [ ] **Step 5:** Commit: `chore: scaffold speedlimit package`.

### Task 1: Data loading

**Files:** Create `src/speedlimit/io_load.py`, `tests/unit/test_io_load.py`

**Interfaces:**
- Produces: `load_readings(path: Path) -> pd.DataFrame` (detects a missing header; columns `month, day, hour, minute, second, sensor, value`), `load_accidents(path: Path) -> pd.DataFrame` (no `LicencePlate`), `load_sensors(path: Path, types_path: Path) -> pd.DataFrame` (codes and units whitespace-stripped).

- [ ] **Step 1: Failing tests:**
  - `test_bom_stripped`: the first column is `month`
  - `test_decimal_comma`: the value of sensor -1 on Jan 1 00:22 is `70.0`
  - `test_n1_without_header`: `len == 12648` and the first row's sensor is `6`
  - `test_licence_plate_dropped`
  - `test_type_codes_stripped`: `"W"` is among the codes
- [ ] **Step 2:** Run `pytest tests/unit/test_io_load.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement. Header detection: if the first cell isn't numeric, treat the first row as a header.
- [ ] **Step 4:** Run the tests. Expected: 5 passed.
- [ ] **Step 5:** Commit: `feat(io): robust CSV loaders`.

### Task 2: Cleaning rules + hourly table

**Files:** Create `src/speedlimit/cleaning.py`, `tests/unit/test_cleaning.py`

**Interfaces:**
- Consumes: the Task 1 frames.
- Produces: `clean_readings(df, sensors, cfg: CleaningConfig) -> tuple[pd.DataFrame, CleaningReport]` (the report holds a list of `(rule_id, rows_affected, note)`), `to_hourly(df) -> pd.DataFrame` (index `(day, hour)`, per-group mean + spread, `speed_limit`), `join_accidents(hourly, acc) -> pd.DataFrame` (adds `near_accidents` and `accidents`, D1/D6).

- [ ] **Step 1: Failing tests (fault-injected fixtures):**
  - `test_text_month_repaired`: `"January"` becomes 1
  - `test_null_month_imputed`
  - `test_missing_sensor_id_dropped`
  - `test_out_of_range_wind_direction`: 400 becomes NaN, then interpolated
  - `test_duplicate_day_removed`: the result is 24 rows/day
  - `test_sensor_type_resolution`: 16 is `traffic` and 19 is `temperature`
  - `test_silent_sensors_reported`: `[7, 10, 17]`
  - `test_hour_mapping`: accident hour 24 on Jan 3 is counted in `(3, 23)`
  - `test_real_counts`: 744 rows, `near_accidents.sum() == 964`, `accidents.sum() == 32`
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement. Ranges come from SensorTypes Min/Max. Gaps of ≤ 3 hours are interpolated; longer gaps stay NaN and are excluded from training.
- [ ] **Step 4:** Run the tests. Expected: 9 passed.
- [ ] **Step 5:** Commit: `feat(cleaning): repair rules, hourly table, accident join`.

### Task 3: Features + condition rules

**Files:** Create `src/speedlimit/features.py`, `src/speedlimit/rules.py`, `tests/unit/test_features.py`, `tests/unit/test_rules.py`

**Interfaces:**
- Produces: `FEATURES: list[str]` (D11, in this order: `log_lux, water, temp, humidity, noise, wind_strength, wind_dir_sin, wind_dir_cos, traffic, hour_sin, hour_cos, speed_limit`), `build_features(hourly) -> pd.DataFrame`, `situation_to_frame(s: Situation, limits: Sequence[int]) -> pd.DataFrame` (one row per candidate limit), `is_dark(lux_mean, cfg) -> bool`, `is_black_ice(water_mean, temp_mean, cfg) -> bool`, `evaluate(s: Situation, cfg) -> RuleResult`.

- [ ] **Step 1: Failing tests:**
  - `test_dark_boundary`: 0.499 gives True, 0.5 gives False
  - `test_ice_boundary`: (1001, -0.1) gives True, (1000, -5) gives False, (1500, 0) gives False
  - `test_feature_columns`: `list(build_features(h).columns) == FEATURES`
  - `test_situation_frame_rows`: 5 rows that differ only in `speed_limit`
  - `test_counts_match_facts`: 354 dark hours and 62 black-ice hours on the real data
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement. `log_lux = log10(lux + 1e-3)`. Hour and wind direction are encoded as sin/cos.
- [ ] **Step 4:** Run the tests. Expected: 5 passed.
- [ ] **Step 5:** Commit: `feat(features): D11 feature set and SPEC1/2 rules`.

### Task 4: Model training, evaluation, model card

**Files:** Create `src/speedlimit/model.py`, `src/speedlimit/cli_train.py`, `tests/unit/test_model.py`, `tests/integration/test_training_pipeline.py`. Outputs: `models/model_<ver>.joblib`, `models/model_card_<ver>.md`, `reports/metrics.json`.

**Interfaces:**
- Consumes: `build_features`, `FEATURES`, the hourly table.
- Produces: `train(X, y, cfg) -> ModelArtefact` (fields as in architecture §5.4), `predict_rate(art, X) -> np.ndarray` (≥ 0, smearing-corrected), `save(art, path)`, `load(path) -> ModelArtefact` (refuses a feature-list mismatch).

- [ ] **Step 1: Failing tests:**
  - `test_split_by_day`: train days are 1–24, test days 25–31, no overlap
  - `test_rates_non_negative`
  - `test_reproducible`: same config gives identical rates
  - `test_roundtrip`: `load(save(a))` gives identical rates
  - `test_load_rejects_feature_mismatch`
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement per architecture §5.2: `TransformedTargetRegressor(log1p/expm1)` around `StandardScaler + MLPRegressor((16, 8), alpha=1e-2, early_stopping=True)`, a 5-seed ensemble, the smearing factor `k`, and a condition × limit baseline table stored in the artefact.
- [ ] **Step 4:** Run `python -m speedlimit.cli_train --config config.yaml`. It writes the metrics (MAE, RMSE, Poisson deviance, skill vs baseline, calibration, limit sensitivity, target-reachable share) into the model card. Record the result honestly (D8).
- [ ] **Step 5:** Commit: `feat(model): MLP ensemble near-accident model + model card`.

### Task 5: REQ1 decision (candidate sweep + monotone guard)

**Files:** Create `src/speedlimit/decide.py` (REQ1 part); add `monotone_guard` to `model.py`; create `tests/unit/test_decide.py` (REQ1 tests)

**Interfaces:**
- Consumes: `predict_rate`, `situation_to_frame`.
- Produces: `monotone_guard(rates: Mapping[int, float]) -> dict[int, float]` and `req1_limit(s: Situation, art: ModelArtefact | None, cfg) -> Req1Result` (`rates_raw`, `rates_guarded`, `target_reachable`, `source ∈ {"model", "baseline_table", "inactive"}`).

- [ ] **Step 1: Failing tests (stub artefact):**
  - `test_picks_highest_meeting_target`: rates `{40:.5, 50:.7, 60:.9, 70:1.1, 80:1.4}` give 60 with `target_reachable=True`
  - `test_none_reachable_epsilon` (D25): guarded `{40:1.20, 50:1.22, 60:1.24, 70:1.30, 80:1.40}` with ε=0.05 gives 60 and `target_reachable=False`
  - `test_monotone_guard`: `{40:1.8, 50:1.4, 60:1.2, 70:1.1, 80:1.3}` gives `g[40] <= g[50] <= g[60] <= g[70] <= g[80]`
  - `test_missing_artefact_uses_baseline_table`: `source == "baseline_table"`
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement. The guard walks the limits from 80 down, keeping the running minimum.
- [ ] **Step 4:** Run the tests. Expected: 4 passed.
- [ ] **Step 5:** Commit: `feat(decide): REQ1 sweep with monotone guard`.

### Task 6: REQ2 air quality + LLM advisor

**Files:** Create `src/speedlimit/air_quality.py`, `src/speedlimit/llm_advisor.py`, `tests/unit/test_air_quality.py`, `tests/unit/test_llm_advisor.py`

**Interfaces:**
- Produces: `fetch_forecast(lat, lon, cfg) -> AQForecast | None`, `summarise(fc, horizon_h) -> AQSummary`, `table_limit(eu_aqi: float) -> int`, `build_prompt(summary) -> tuple[str, str]`, `validate(raw: str, summary) -> LLMAdvice`, `advise(summary, cfg, client=None) -> Req2Result` (`source ∈ {"llm", "table", "manual", "none"}`).

- [ ] **Step 1: Failing tests (no network; mocked HTTP + fake client):**
  - `test_table_boundaries`: 60 → 80, 61 → 70, 80 → 70, 81 → 60, 100 → 60, 101 → 50
  - `test_valid_llm_json_used`: limit 60 with `source == "llm"`
  - `test_prose_falls_back`: `source == "table"`
  - `test_limit_outside_set_falls_back`: 65 gives `source == "table"`
  - `test_timeout_falls_back`
  - `test_http_503_returns_none`: `fetch_forecast(...) is None`
  - `test_implausible_llm_rejected` (D26): AQI 120 with LLM 80 gives `source == "table"`, limit 50
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement with Open-Meteo `air-quality-api.open-meteo.com/v1/air-quality` (hourly `european_aqi, pm2_5, pm10, nitrogen_dioxide, ozone`). The prompt is verbatim from architecture §7.2; the model name comes from config.
- [ ] **Step 4:** Run the tests. Expected: 7 passed. Then make one live call and save it to `docs/evidence/llm_sample.json` for the deck.
- [ ] **Step 5:** Commit: `feat(req2): air-quality forecast + LLM advisor with table fallback`.

### Task 7: Router / combiner + audit log

**Files:** Modify `src/speedlimit/decide.py`; create `src/speedlimit/audit.py`, `tests/integration/test_router_end_to_end.py`

**Interfaces:**
- Consumes: `evaluate`, `req1_limit`, `advise`.
- Produces: `combine(rule, r1, r2) -> Decision`, `decide(s: Situation, ctx: RuntimeContext) -> Decision`, `log_decision(d, path)`, `read_log(path, n=50) -> pd.DataFrame` (JSONL in `logs/decisions.jsonl`).

- [ ] **Step 1: Failing tests:**
  - `test_req3_default`: daylight, dry road, good air gives 80, `winning_reasons == ["REQ3"]`, and the model is not called
  - `test_dark_uses_model`
  - `test_min_combination`: REQ1 60 and REQ2 50 give 50 with REQ2 winning
  - `test_log_has_no_plate`: no logged key contains "plate"
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: 4 passed.
- [ ] **Step 5:** Commit: `feat(decide): router, min-combiner, audit log`.

### Task 8: Streamlit GUI

**Files:** Create `src/speedlimit/app.py`, `tests/integration/test_app.py`

**Interfaces:**
- Consumes: `decide`, `load`, `read_log`, the hourly table (for replay). Layout per architecture §8.1.

- [ ] **Step 1: Failing tests** (`streamlit.testing.v1.AppTest`):
  - `test_renders_default`: the daylight sample shows "80 km/h"
  - `test_dark_input_reduces`: lux 0.2 shows a limit ≤ 80 plus the per-limit rate table
  - `test_unreachable_flag_visible`
  - `test_llm_offline_shows_table_badge`
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement the inputs panel (pre-filled from a sample hour), a manual/replay toggle (timer per D21), the result card, the explanation, the per-limit chart and the audit table.
- [ ] **Step 4:** Run the tests and do a manual browser check.
- [ ] **Step 5:** Commit: `feat(gui): Streamlit operational stage`.

### Task 9: Drift check (year N+1)

**Files:** Create `src/speedlimit/drift.py`, `tests/unit/test_drift.py`. Output: `reports/drift_report.json` plus `docs/evidence/drift_report.md`.

**Interfaces:**
- Produces: `drift_report(ref, new, features, cfg) -> DriftReport` and `verdict(report) -> Literal["retrain", "no_retrain"]`.

- [ ] **Step 1: Failing tests:**
  - `test_identical_no_retrain`: N vs N gives `"no_retrain"`
  - `test_temp_shift_retrain`: temp + 8 °C gives `"retrain"`, with `temp` flagged
- [ ] **Step 2:** Run them and confirm they fail.
- [ ] **Step 3:** Implement a KS test per feature (α = 0.05) plus a relative mean shift > 10 %; a feature drifts when it fails both.
- [ ] **Step 4:** Run on the real N+1 file. Expected: `no_retrain` (the file is identical, F10).
- [ ] **Step 5:** Commit: `feat(drift): year N+1 retraining check`.

### Task 10: Acceptance run + presentation evidence

**Files:** Create `docs/evidence/acceptance_run.md` and `docs/evidence/screenshots/*.png`

- [ ] **Step 1:** Run `pytest -q`. Expected: all green, with the count recorded.
- [ ] **Step 2:** Run the demo scenarios from `docs/07-test-strategy.md` §4 in the GUI and screenshot each one (`S01_…png`).
- [ ] **Step 3:** Fill the metrics and screenshots into the model card and the storyline TODO-after-build slides (8–11, 13, 14).
- [ ] **Step 4:** Commit: `docs: acceptance evidence`.

### Task 11: Management presentation

- [ ] **Step 1:** Build the deck from `docs/08-presentation-storyline.md` with figures F01–F12 plus the GUI screenshots.
- [ ] **Step 2:** Rehearse (≤ 15 min) and go through the Q&A prep.
- [ ] **Step 3:** Export a copy and keep it for semester 3.

### Task 12: UML set

**Files:** Create `docs/10-uml.md` (mermaid) and the exported PNGs

- [ ] **Step 1:** Class diagram: data model (data report §3) plus code model (`types.py`).
- [ ] **Step 2:** Component diagram (router), sequence diagram (architecture §6), activity diagram (training pipeline).
- [ ] **Step 3:** Check every name against the Interfaces blocks above.

---

## Self-review notes

- **Spec coverage:** REQ1 → T3/T5/T7, REQ2 → T6/T7, REQ3 → T3/T7, SPEC1–2 → T3, SPEC3 → T4, SPEC4 → T2, training stage → T1–T4, operational stage → T8, retraining exercise → T9, presentation → T10/T11, UML exercise → T12.
- **Type consistency:** all names are taken from architecture §4.2/§4.3. `Req2Result.source` uses `"table"` (not "fallback") everywhere.
- **Proportion:** bodies are left to the implementer; only thresholds, signatures and test values are fixed here.
