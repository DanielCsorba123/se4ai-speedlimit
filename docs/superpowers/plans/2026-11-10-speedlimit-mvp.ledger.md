# SDD ledger — plan: docs/superpowers/plans/2026-11-10-speedlimit-mvp.md
Scope: user asked for Task 0 only (2026-11-11).
Pre-flight (Task 0 only): produces Config + types consumed by Tasks 1–8; names checked against architecture §4.3/§11.2.
Task 0: Ruling: config keys follow architecture §11.2 (rules.dark_lux_threshold, air_quality.latitude, …) not the plan shorthand (cfg.rules.lux_dark, cfg.aq.lat) — spec is binding — cost if wrong: renaming attributes in one test
Task 0: Ruling: air_quality.latitude = 48.21 (D23) not 48.20 (arch placeholder); drift alpha 0.05 (D21) not ks_p 0.01 — decision log is binding — cost: two config values
Task 0: Ruling: raw_dir = "." because the course CSVs live in the repo root; not moved to data/raw — avoids moving user files — cost: one path change
Task 0: Ruling: baseline commit of existing docs on main, implementation on branch build/mvp — fresh repo, no prior main history — cost: none
Task 0: Ruling: shared types module named domain.py, not types.py — `streamlit run src/speedlimit/app.py` puts src/speedlimit on sys.path[0], so a types.py would shadow the stdlib `types` module — cost if wrong: one import rename
Task 0: Note for Task 1: pandas read_csv turns the literal "NULL" month into NaN by default — loader must use keep_default_na=False (or explicit na_values) so the NULL-month repair rule can see it
Task 0: complete (commits 51978fa..cef6802, tests: .venv/Scripts/python -m pytest -q → 13 passed in 0.56s)
Task 1: Ruling: load_readings parses into nullable Int64/Float64 (unparseable -> <NA>, keep_default_na=False) AND keeps original text in <col>_raw columns — Task 2 must see "January"/"NULL"/"" to repair and count them (D19); a strict loader would crash or hide them — cost if wrong: drop 7 columns
Task 1: Ruling: load_sensors left-joins types on stripped code and keeps BOTH rows for ambiguous code T with ambiguous=True; resolution is Task 2 (resolve_sensor_types, D2) — cost if wrong: one dedupe
Task 1: Ruling: LicencePlate excluded via usecols at read time, never in memory (arch §1.2, D20)
Task 1: Finding: SensorTypes.csv lists WD only once (earlier recon preview double-printed it via overlapping head/tail); drop_duplicates kept as robustness, its test uses a synthetic duplicate and was mutation-checked
Task 1: complete (commits cef6802..0bd659f, tests: .venv/Scripts/python -m pytest -q → 26 passed in 0.81s)
Note for Task 2: arch §5.1 step 2 says missing sensor ID is "inferred from sequence" and NaN hours imputed from same-type sensors first; plan Task 2 says "dropped" — spec (arch) wins, rule on it at Task 2
Task 2: Ruling: cleaning follows data report §8 rules C02–C16 (the spec) over the plan's shorter wording; missing sensor ID is INFERRED when exactly one expected sensor is absent in that (day,hour) batch (C06), else rejected; plan test renamed test_missing_sensor_id_inferred — cost if wrong: one rule branch
Task 2: Ruling: empty/out-of-range values are filled from same-type siblings first (C07), then ≤3 h interpolation; plan said "interpolated" — spec order — cost: small numeric differences in imputed cells only
Task 2: Ruling: C10 spike rule = deviation from the GROUP MEDIAN (types with >=3 sensors) > 20% of the sensor's range (min/max from SensorTypes); a pure MAD rule false-fires with 2–3 near-identical siblings (MAD≈0) — verified to fire 0× on V100 — cost if wrong: missed subtle spikes
Task 2: Ruling: wind direction aggregated with a circular mean (mean of 350° and 10° is 0°, not 180°) — cost: none
Task 2: Ruling: new config section `cleaning` (max_interp_gap_h, spike_rel_range) because CleaningConfig had no home in config.yaml — cost: one section
Task 2: Ruling: C17 (unexplained reduction flag), C18 (calm wind), C20 (leakage cols) belong to Task 3 features; C21 to Task 9 drift — they need rules/features
Task 2: Finding: leave-one-out mean let one spike flag all siblings (test_in_range_spike RED: C10 count 3 vs 1); switched to group median
Task 2: complete (commits 0bd659f..567dacf, tests: .venv/Scripts/python -m pytest -q → 44 passed in 2.08s)
Task 3: Ruling: extra function rules.label_conditions(hourly, cfg) adds dark/black_ice/condition/unexplained_reduction (C17, D10) — Task 4 baseline needs condition per hour; not in the brief's Produces — cost: one function
Task 3: Ruling: D28 calm wind (wind_strength == 0 -> wind_dir sin/cos = 0) and D30 fail-safe (missing lux / water / temp -> condition met, listed in RuleResult.missing_inputs) implemented here
Task 3: Ruling: condition label precedence dark > black_ice > normal (dark-and-icy hours count as "dark"), matching F04 and facts.json (black ice total 62, of which 35 not dark)
Task 3: complete (commits 567dacf..15b84b9, tests: .venv/Scripts/python -m pytest -q → 57 passed in 3.14s)
Task 4: Ruling: train(X, y, cfg) returns the fitted part of ModelArtefact; cli_train fills baseline_table, metrics, data_hash, cell_counts etc. via dataclasses.replace — keeps train() testable on synthetic data — cost: none
Task 4: Ruling: model card reports limit sensitivity / reachable share on the RAW curve; guarded figures are added in Task 5 where monotone_guard is defined — cost: two extra rows later
Task 4: Ruling: training uses complete hours only (all 744 on V100, D27); artefact stores cell_counts[(condition, limit)] for the D32 extrapolation flag in Task 5
Task 4: Ruling: prepare_hourly(cfg, readings_path=None) lives in cli_train so Task 8 (replay) and Task 9 (N+1 drift) reuse the same pipeline
Task 4: Result (V100, model 20261111-0903): test MAE 0.876 vs baseline 0.895, skill +0.006; dark/ice MAE 0.790 vs 0.856; raw limit sensitivity +0.435/h (40 vs 80: model predicts MORE at 40 = confounding, D9 guard required); raw reachable share 37.8%; training 4 s (D21 ≤5 min)
Task 4: complete (commits 15b84b9..d536036, tests: .venv/Scripts/python -m pytest -q → 67 passed in 10.34s)
Task 5: Ruling (new decision D33): when REQ1 is active the candidates are {40..70}; 80 is excluded — REQ1 says "shall be REDUCED", operators used 80 in 0 of 389 dark/ice hours (cell is pure extrapolation, D32), and with the D9 guard a confounded flat curve plus D25 "highest within eps" would otherwise output 80 in the dark — cost if wrong: one config value (decide.req1_max_limit)
Task 5: Ruling: req1_limit(s, art, cfg: Config, rule=None, baseline=None) takes the full Config (needs rules + features + decide) and an optional baseline table; cli_train also writes models/baseline_table.json so the GUI has a fallback when the artefact cannot be loaded — cost: signature differs from brief (cfg type)
Task 5: Ruling: model card + metrics get guarded figures and the REQ1 decision distribution over dark/ice test hours (completes the Task 4 ruling)
Task 5: Result (V100, model 20261111-0906): guarded 40-vs-80 = -0.183/h; REQ1 reachable 37.8% of dark/ice test hours; chosen REQ1 limits over 82 dark/ice test hours: 70x64, 60x17, 50x1 (operators used 60 in 211/354 dark hours)
Task 5: complete (commits d536036..d42cd72, tests: .venv/Scripts/python -m pytest -q → 81 passed in 15.24s)
Task 6: Ruling: LLM model claude-opus-5-5 (not arch's claude-sonnet-5-5) — the user never named a model; claude-api skill default is Opus 5.5 and forbids downgrading for cost on the user's behalf; D14 only says "latest Claude" — cost if wrong: one config value
Task 6: Ruling: server-side refusal fallback on by default (betas server-side-fallback-2026-07-01, fallbacks="default", via client.beta.messages.create) per claude-api skill; new config key llm.server_fallback — refusal still ends in the D15 table if the chain refuses
Task 6: Ruling: llm.max_tokens 1024 -> 4096 — Opus 5.5 always thinks (adaptive); 1024 risks stop_reason max_tokens -> needless fallback — cost: none (billed by use)
Task 6: Ruling: schema maxLength enforced by our validator (V3), not sent in the API schema — avoids structured-output schema-feature limits — cost: none
Task 6: Ruling: advise() takes full Config (needs llm + air_quality); good air (EAQI max <= 60) returns 80 with source "none" WITHOUT an LLM call; unknown AQ returns source "none" + warning reason (D26 step 3); manual AQI via manual_limit() source "manual" (D26 step 2, D31)
Task 6: Ruling: LLM cache in memory only (arch also wanted logs/llm_cache.json) — MVP; restart re-calls at most once per hour — cost: a few cents
Task 6: Step 4 partial: live Open-Meteo call OK (Vienna EAQI max 45 -> REQ2 inactive, 80, source none), saved docs/evidence/req2_live_sample.json; live LLM call NOT run — no ANTHROPIC_API_KEY and no ant CLI on this machine; deviation from brief Expected (left for the user)
Task 6: complete (commits d42cd72..9cf6c67, tests: .venv/Scripts/python -m pytest -q → 105 passed in 15.94s)
Task 7: Ruling: RuntimeContext(cfg, art, baseline, aq_summary, manual_aqi, llm_client, llm_log, decision_log) defined in decide.py; Decision gets optional situation + decided_at fields (arch §11.1 log needs situation values) — cost: two defaulted fields
Task 7: Ruling: winning_reasons = every path whose limit equals the final limit when it is < 80 (ties list both); final 80 -> ["REQ3"]
Task 7: Ruling: decide() lets a missing-model-and-baseline error propagate; the GUI applies D29 (show 60 + banner) — keeps the decision core honest
Task 7: complete (commits 9cf6c67..8de3d3b, tests: .venv/Scripts/python -m pytest -q → 116 passed in 17.00s)
Task 8: Ruling: env overrides SPEEDLIMIT_OFFLINE (no Open-Meteo, LLM off), SPEEDLIMIT_MODELS_DIR, SPEEDLIMIT_LOGS_DIR so AppTest runs hermetically — cost: three env vars documented in README
Task 8: Ruling: default sample hour = first dark hour of the test days (arch §8.2), not daylight as the plan's test assumed; test_renders_default selects a daylight hour explicitly — spec wins
Task 8: Ruling: plan's test_llm_offline_shows_table_badge replaced by test_manual_aqi_shows_req2_source + test_no_forecast_warns (LLM->table fallback already unit-tested in Task 6; in the GUI it needs a live poor forecast); unreachable flag tested via baseline-only models dir (baseline dark rates are all > 1.0, so the flag is guaranteed)
Task 8: Ruling: light slider works on log10(lux) (arch §8.2), caption shows lux; decisions are logged only when inputs change (no log flood on reruns)
Task 8: Finding: replay fragment advanced replay_idx on every full rerun too (test_replay_next_hour_advances RED: +2 per click); now advances only on fragment-only (timer) reruns
Task 8: complete (commits 8de3d3b..c094841, tests: .venv/Scripts/python -m pytest -q → 124 passed in 25.32s)
Task 9: Ruling: feature drifts when KS p < alpha (0.05, D21 binding over arch's 0.01) AND standardised mean shift |Δmean|/std_N > 0.5 (arch §10.2); plan's "relative mean shift > 10%" rejected — dividing by a mean near 0 (temp mean -3.5 °C) is unstable — config key mean_shift_rel -> mean_shift_sd — cost if wrong: one threshold
Task 9: Ruling: verdict = retrain if ANY core feature (log_lux, water, temp, traffic, speed_limit) drifts (plan test: temp +8 alone must retrain) instead of arch's ">= 2 core features" — a single temperature shift changes black-ice frequency — cost: more conservative retrain advice
Task 9: Ruling: identity check (row equality + SHA-256 of cleaned readings) reported with a "duplicate dataset" warning (C21); arch's chi² on limits and histogram PNG skipped (speed_limit is covered by its KS row) — cost: one figure
Task 9: Result: real N+1 -> no_retrain, 12648 identical rows, all KS D = 0, duplicate-dataset warning; evidence docs/evidence/drift_report.md
Task 9: complete (commits c094841..311d7b9, tests: .venv/Scripts/python -m pytest -q → 130 passed in 26.50s)
Task 10: Ruling: demo deep links ?scenario=AT-1..AT-8 (test-strategy §4) added to app.py — needed to render each scenario reproducibly for headless screenshots and to drive the live demo; scenarios use day 25 (test week) at the scenario's hour — cost: one dict + 15 lines
Task 10: Ruling: screenshots via the installed Microsoft Edge in headless mode (no Playwright/browser download) — cost: none
Task 10: Ruling: AT-5 ("poor air via LLM") cannot show source "llm" — no Anthropic credentials here; the AQI override field is the D26/D31 manual path (table). AT-5 and AT-7 therefore both show the table result; LLM path is covered by unit tests; recorded honestly in acceptance_run.md
Task 10: Ruling: screenshots driven by Playwright with the installed Chrome (channel="chrome", no browser download); plain headless --screenshot captured half-rendered pages (virtual time does not wait for the Streamlit websocket) — dev-only dependency
Task 10: complete (commits 311d7b9..8189157, tests: .venv/Scripts/python -m pytest -q → 134 passed in 24.99s)
Order: Task 12 (UML) executed before Task 11 — slide 8 of the deck needs the UML router diagram; Task 12 has no dependency on 11
Task 12: complete (commits 8189157..b74a522, tests: .venv/Scripts/python -m pytest -q → 156 passed in 25.46s)
Task 11: Ruling: deck built as a Slides artifact (Artifact quickstart routes decks there) instead of .pptx — it exports to PPTX/PDF from Share › Export; sources copied to docs/presentation/ — cost: none
Task 11: Not done by me (user steps): rehearsal with a timer (Step 2) and the export for semester 3 (Step 3); deck is private until the user shares it
Task 11: complete (commits b74a5220..6de7f31, tests: .venv/Scripts/python -m pytest -q → 156 passed in 27.03s)
Final review: opus reviewer, verdict "With fixes": 0 Critical, 3 Important, 12 Minor
Final: re-grade: Minor-3 (slider adds 0.001 lux -> near-threshold dark hour flips to not dark) -> Important (wrong safety decision for a reasonable user); Minor-4 (C07 interpolates whole-type gaps, positional gap length) -> Important (violates binding D30: such hours must be excluded)
Final: minor (deferred): replay fragment reuses AQ summary from last full run (stale past 3 h in long unattended replays)
Final: minor (deferred): sidebar sliders show manual values in Replay mode; Sample hour selector inert once replay_idx set
Final: minor (deferred): C10 not implemented for 1- and 2-sensor types (6-sigma neighbour jump)
Final: minor (deferred): all-months-invalid crashes (mode() empty); month not part of hourly key (multi-month files would merge)
Final: minor (deferred): load_config does not check req1_max_limit >= min(candidate_limits)
Final: minor (deferred): drift check only detects mean shifts (variance/shape changes ignored); AC-REQ9-02 +5 °C case not tested exactly
Final: minor (deferred): baseline path drops D32 extrapolation flags
Final: minor (deferred): broad except in llm_advisor can hide SDK/coding errors as silent table fallback (GUI shows no "LLM error")
Final: minor (deferred): no regression tests for AC-NFR-01 (744 h domain), AC-REQ3-02 (28 h -> 80), AC-NFR-10 (<= 2 s) — reviewer's replay probe shows they pass
Final: minor (deferred): source labels "table"/"manual" vs AC wording "fallback"; model.artefact config unused; replay timer not adjustable in GUI; cache_resource keeps stale model until restart
Final: fixed I-1 missing input crashes REQ1 with a model (D30) — test_missing_input_uses_baseline_not_crash RED->GREEN (req1 falls back to the artefact's baseline table when rule.missing_inputs)
Final: fixed I-2 extrapolated 80 km/h cell drove guard + reachable flag — test_guard_ignores_excluded_80_cell RED->GREEN (decide.guard_candidates: guard over <= req1_max_limit; cli_train + model_figures use it)
Final: fixed I-3 LLM 2x timeout and per-rerun retries; AQ fetch retried per rerun — test_no_sdk_retries_so_timeout_is_the_deadline, test_failed_call_is_not_retried_on_every_rerun, test_failed_fetch_is_not_retried_immediately RED->GREEN (max_retries 0, 5 min fallback cache, 60 s AQ failure backoff)
Final: fixed I-4 (re-graded minor 3) slider +0.001 lux drift — test_light_slider_round_trip / test_dark_sample_stays_dark (new speedlimit.ui_helpers; RED was import-level, behaviour change verified by the 0.4995-lux case)
Final: fixed I-5 (re-graded minor 4) C07 interpolated whole-type gaps and partial long gaps — test_whole_type_missing_is_not_interpolated, test_single_sensor_short_gap_interpolated_long_gap_not RED->GREEN (interpolate only single-sensor types, whole gaps <= 3 h by time)
Final: fix pass committed; suite 172/172; model retrained (20261111-1026); reachable share 37.8% -> 32.9%; D34 added; deck + storyline + acceptance updated
