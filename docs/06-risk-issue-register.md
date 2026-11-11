# 06 · Risk & Issue Register

| | |
|---|---|
| Document | Risk & Issue Register, SpeedLimit MVP (SE4AI, ExID SpeedLimit21) |
| Version | 0.1 |
| Date | 2026-11-10 |
| Status | Draft |
| Owner | QA & Risk |
| Inputs | Case study slides (REQ1–3, SPEC1–4, slide 17), main exercise slide 32, `05-decision-log.md` (D1–D32), `figures/facts.json`, figures F01–F12 |
| Rule | No questions go to the lecturer. Open points are closed by an assumption in the decision log (Dx) and tracked here. |

## 0. How to read this register

- **Issue (ISS-xx)** = already true today. It has evidence and a handling decision. It cannot be "mitigated away", only handled.
- **Risk (RSK-xx)** = may happen. Scored **Probability (P) × Impact (I)**, both 1–5, score 1–25.
- Score bands: **15–25 high** (Top-5 candidates, reviewed every team meeting), **8–14 medium** (reviewed weekly), **1–7 low** (reviewed at milestones).
- All numbers below come from `facts.json` or the figures. No other numbers are used.

**Roles used as owners**

| Role | Short | Responsible for |
|---|---|---|
| Project Lead / Product Owner | PL | Scope, timeline, final presentation |
| Requirements Engineer | RE | REQ/SPEC interpretation, assumptions, glossary |
| Data Engineer | DE | Loading, cleaning, joining, feature table |
| ML Engineer | ML | Model, evaluation, decision sweep |
| Integration / GUI Developer | DEV | Streamlit GUI, API and LLM client, combiner |
| QA & Risk | QA | Tests, this register, acceptance demo |

Probability scale: 1 rare (<10 %), 2 unlikely (10–30 %), 3 possible (30–50 %), 4 likely (50–80 %), 5 almost certain (>80 %).
Impact scale: 1 cosmetic, 2 minor rework, 3 a deliverable is weakened, 4 a requirement or the demo is at risk, 5 the project message or safety case fails.

## 1. Issues (already true)

| ID | Title | Description | Evidence | Impact | Handling / decision | Owner | Status |
|---|---|---|---|---|---|---|---|
| ISS-01 | REQ1 target not supported by data | Mean near-accidents per hour are ≥ 1.04 at every observed limit and condition (overall 1.3/h). Correlation near-accidents vs limit = 0.008. Under "dark", lower limits coincide with *more* incidents (40 km/h: 1.86/h, 70 km/h: 1.13/h). No limit in the data achieves ≤ 1/h under dark or black ice. | F04 | High: the model will often find no limit that meets REQ1. Risk of a "drive faster" model. | Build as specified anyway (D8), sweep + "target not reachable" flag (D7), monotonicity guard (D9), show F04 as key finding in deck. See RSK-01, RSK-02. | ML | Open – handled by design |
| ISS-02 | Data covers January only | 744 hourly rows (31 days × 24 h), single month, winter only. No spring/summer conditions, no other months for validation. | F11, facts `hours`=744 | High for generalisation: model valid only for January-like conditions. | Report scope limit in deck and GUI footer. Day-based split (D12). See RSK-04. | ML | Open – accepted |
| ISS-03 | Year N+1 file is a copy of year N | 12 648 / 12 648 rows identical. Only difference: the header line is missing. | F10, facts `n1_identical_rows` | Medium: retraining analysis (slide 19) cannot show real drift. | Implement drift check anyway, expected verdict "no retraining", report as a finding (D13). Loader must handle missing header (TC-03). | DE | Open – handled |
| ISS-04 | Hour convention mismatch | Readings use Hour 0–23. Accidents use Hour 1–24: no hour 0, 44 events at hour 24. | F05, facts `acc_hour_min_max`, `acc_hour24_count`=44 | High if wrong: shifts every label by one hour, mislabels dusk/dawn hours. | Map accident hour h → reading hour h − 1 (D1). Tested by TC-17/18/19. See RSK-09. | DE | Closed by D1 |
| ISS-05 | Sensor type code `T` ambiguous | `SensorTypes.csv` uses `T` for both temperature (−30..70 °C) and traffic (0..50 cars/s). | F02, F06 | High if wrong: SPEC2 (black ice) uses temperature. | 15/18/19 = temperature (corr ≥ 0.996, swing around 0 °C), 16 = traffic (range 1.85–30, corr 0.21) (D2). See RSK-10. | DE | Closed by D2 |
| ISS-06 | Undocumented and silent sensors | Sensor 19 has readings but no description. Sensors 7, 10, 17 are described but have no readings. No air-pressure input exists. | F03, facts `sensors_undocumented`, `sensors_no_readings` | Low–medium: fewer features, one undocumented sensor used. | 19 treated as temperature; 7/10/17 ignored (D3). | DE | Closed by D3 |
| ISS-07 | 28 unexplained speed reductions | 28 hours below 80 km/h although neither dark nor black ice (mostly daytime 06:00–18:00, e.g. Jan 1 09:00 → 60). 28 "normal" hours at 60 km/h vs 327 at 80. | F07, facts `unexplained_reductions`=28 | Medium: noisy labels for "normal" condition; REQ3 conflict. | Keep in training, flag in data report, never output (REQ3 forces 80) (D10). TC-53, TC-62. | DE | Open – handled |
| ISS-08 | Dirty sensor-type metadata | Unit typo `hm/h` for wind strength, padded unit `degrees   `, trailing space in code `W `. | F02 | Low: join on code fails silently if not stripped. | Strip whitespace on all string fields; treat `hm/h` as km/h (documented assumption, not used in rules). TC-05. | DE | Open – handled in code |
| ISS-09 | CSV format quirks | `;` separator, decimal comma (`0,10`), UTF-8 BOM before `Month`, speed limit encoded as sensor −1. | F01 | Medium: naive `pd.read_csv` yields a column `﻿Month` and string values. | Explicit loader (`sep=';'`, `decimal=','`, `encoding='utf-8-sig'`), sensor −1 split out as label/input. TC-01..TC-04. | DE | Open – handled in code |
| ISS-10 | Course error list does not match V100 | Of 12 slide-17 error claims, 4 are found in V100 (T ambiguous, sensor 19, sensors 7/10/17, unexplained reduction). 8 are not present (NULL month, "January" text, missing sensor id, wind dir > 400°, missing day, duplicated day, empty readings, extreme value). Every sensor has 744 readings, no NaN, month = 1, wind dir ≤ 360 (max 257). | F12, facts `every_sensor_744`, `wd_max`=257 | Low for the model, medium for grading: the lecturer expects these repairs. | Implement all slide-17 repairs anyway and test them on injected faults (D19). TC-07..TC-16. | QA | Open – handled |
| ISS-11 | REQ2 has no training data and depends on two external services | Air quality must come from an API; the decision comes from an LLM. Neither is under our control. | Slide 3, D14 | Medium–high: availability, cost, non-determinism. | Open-Meteo forecast API + Claude with JSON contract (D14); deterministic AQI fallback (D15); source shown in GUI. See RSK-05/06/07/08. | DEV | Open – handled |
| ISS-12 | Accident log structure | 997 rows: 964 near-accidents (886 CloseCar, 63 CloseGuardrail, 15 SkidAngle), 32 accidents (10 of them also with Injured), 1 empty row. CloseCar max 20 cm (log contains only critical events). | F09, facts `acc_composition`, `acc_empty_rows` | Low: target definition must be explicit. | SPEC4 mapping and counting rules per D6; empty row dropped. TC-19, TC-20. | DE | Closed by D6 |
| ISS-13 | Personal data in accident file | `LicencePlate` column identifies vehicles/persons. | Slide 17 ("LicencePlate: Privacy") | Medium: GDPR exposure if persisted or shown. | Drop at load, never persist (D20). TC-45. See RSK-13. | DE | Closed by D20 |
| ISS-14 | Sparse and missing condition × limit cells | Dark: 40 km/h only 7 h, 50 km/h 51 h; black ice: 50 km/h only 4 h, no 40 km/h. **No hour at 80 km/h under dark or black ice exists.** The sweep must still score 80 there. | F04, facts `near_by_cond_speed` | High: predictions for 40 and 80 under dark/ice are extrapolation. | Monotonicity guard (D9); GUI shows per-candidate prediction; deck states that 80 under dark is never observed. See RSK-02, RSK-03. | ML | Open – accepted |
| ISS-15 | Requirement wording is vague | REQ1 "on average" (over which window?), REQ2 "appropriate" and "predicted", "poor air quality" has no threshold. No lecturer clarification allowed. | Slides 9, 11 | Medium: acceptance is debatable. | Operational definitions: REQ1 = model-predicted expected rate per hour ≤ 1.0 (D7, see 07 §3); REQ2 = forecast API (D14), "poor" = EU AQI > 60 (implied by D15 table). See RSK-19. | RE | Open – assumptions documented |
| ISS-16 | Role of traffic unclear | Slide 17 asks whether traffic is input or output (we may want to maximise throughput). | Slide 17 | Low: modelling choice. | Traffic used as input feature only (D11); throughput optimisation out of MVP scope. | RE | Closed by D11 |
| ISS-17 | Light spans 0..120 000 lux | Linear scale is useless for the network; log scale cleanly splits day/night around SPEC1. Very low values (≈ 10⁻³) occur. | F08 | Low: need log transform with a floor. | log10(lux) as input (D11); floor for lux = 0 (TC-48, proposed). | ML | Open – handled in code |

## 2. Risks (may happen)

| ID | Description | Category | P | I | Score | Mitigation (before) | Contingency (if it happens) | Trigger / early warning |
|---|---|---|---|---|---|---|---|---|
| RSK-01 | Model cannot meet the REQ1 target: for most dark/ice inputs no candidate limit is predicted ≤ 1.0/h, so the system almost always raises "target not reachable". | ML | 5 | 4 | 20 | Accept and design for it (D7/D8): flag, lowest-risk limit, predicted rate shown. Prepare the F04 story early. Evaluate share of dark/ice test hours where target is reachable. | Present as data finding, not as defect: "REQ1 is not achievable with speed limits alone on this data; recommend additional measures and more data." | Flag rate > 50 % of dark/ice test hours in first evaluation run. |
| RSK-02 | Confounding teaches unsafe behaviour: because operators lowered limits in worse conditions, the network learns "lower limit → more near-accidents" and recommends higher limits in darkness. | ML | 4 | 5 | 20 | Monotonicity guard (D9) as post-processing; rules (D5) decide *when* REQ1 applies; property test TC-32; sanity check "predicted rate non-increasing when limit decreases". | Fall back to baseline table (mean rate per condition × limit, D12) with the same guard; report that the network is not trusted for the decision. | Raw (unguarded) predictions increase as the limit drops in > 20 % of test inputs. |
| RSK-03 | Overfitting on 744 rows (~576 train hours with day split 1–24), small MLP still has many parameters. | ML | 4 | 3 | 12 | Small network (e.g. 1 hidden layer, ≤ 16 units), L2 (`alpha`), early stopping, day-based split (D12), compare with baseline; fixed seed. | Shrink network, drop weak features (noise, wind direction), or use Poisson GLM as reference and report it. | Train MAE much lower than test MAE (ratio < 0.7), or model loses to baseline on test. |
| RSK-04 | Single-month seasonality: model only knows January; applied to other months (daylight hours, no ice, more traffic) predictions are meaningless. | data | 5 | 3 | 15 | State validity range in GUI and deck; input range check vs training min/max; drift check (D13) as operational guard. | Retrain when new months arrive; until then show "outside training range" warning and rely on rules + baseline. | GUI input outside training range of any feature; drift check flags a feature. |
| RSK-05 | LLM hallucination / invalid output: non-JSON text, limit outside {40..80}, a limit inconsistent with AQI (e.g. 40 for AQI 20), or a made-up reason. | LLM/external | 3 | 3 | 9 | Fixed prompt, numeric inputs only, JSON schema validation, allowed set check (D14); sanity rule: LLM may not be more than one step away from the AQI table, else fallback (proposed). | Fallback AQI table (D15); log raw LLM output for review. | Validation failure rate > 10 % in test runs; any out-of-set value. |
| RSK-06 | API outage / rate limit / latency of Open-Meteo or the Anthropic API, especially during the live presentation (venue Wi-Fi). | LLM/external | 3 | 3 | 9 | Timeouts (e.g. 10 s), D15 fallback, cache last good AQI response, GUI shows source. Demo has an "offline" toggle and a recorded backup. | Switch GUI to fallback/manual AQI mode; continue demo. | HTTP 429/5xx or timeout in the dry run; venue network unknown. |
| RSK-07 | API key leakage: Anthropic key committed to the repo, printed in logs or shown in the GUI / screenshots in the deck. | technical | 2 | 4 | 8 | Key only via environment variable or `.streamlit/secrets.toml` in `.gitignore`; never logged; TC-42; pre-submission secret scan. Open-Meteo needs no key. | Revoke and rotate the key immediately; purge from git history. | Secret scan hit; key visible in any output. |
| RSK-08 | Prompt injection through API data reaching the LLM. Low because only numeric AQI fields are passed. | LLM/external | 1 | 2 | 2 | Build prompt only from parsed numbers; never pass free text from the API (TC-41); output validated anyway. | Fallback table. | Any string field found in prompt construction during code review. |
| RSK-09 | Wrong hour mapping assumption (D1): if hour 24 actually meant 00:00 of the next day, or hour h means the hour *starting* at h, labels are shifted. | data | 2 | 3 | 6 | Sensitivity analysis: train with shift 0 and shift −1, compare test error and dusk/dawn alignment; document in deck. | Switch mapping (one constant), retrain; tests TC-17/18 updated. | Alternative mapping gives clearly better fit (lower test deviance). |
| RSK-10 | Wrong `T` sensor assumption (D2): 16 is temperature and one of 15/18/19 is traffic. | data | 1 | 4 | 4 | Evidence is strong (corr ≥ 0.996, F06). Unit test on value ranges (temp around 0 °C, traffic ≥ 0). | Re-map, rerun pipeline; SPEC2 counts re-checked. | Black-ice hour count changes heavily when re-mapped; temperature with no negative values. |
| RSK-11 | Scope creep vs timeline to the last unit: drift tool, auto-refresh, LLM polish, extra analysis eat time; training stage, GUI and deck not ready. | project/schedule | 3 | 4 | 12 | MVP scope frozen in D17/D18; prioritise: pipeline → model → GUI → REQ2 → drift → polish. Weekly burn-down. | Cut auto-refresh and LLM explanation polish first; keep fallback-only REQ2 if needed. | A milestone slips by > 1 week; open "nice-to-have" tickets grow. |
| RSK-12 | Presentation fails to convince management: too technical, or the honest "REQ1 not achievable" message reads as project failure. | presentation | 3 | 5 | 15 | Storyline: problem → data findings (F04, F10, F12) → working MVP → what it means → recommendation. Live demo script (07 §4). Dry run with timing. | Backup video of the demo; one-slide executive summary; offer phased recommendation. | Dry-run feedback unclear; demo > allotted time. |
| RSK-13 | Privacy breach via licence plates kept in intermediate files, logs, notebooks or slides. | ethics/legal | 2 | 4 | 8 | Drop at load (D20), TC-45 scans all outputs; no raw accident rows in deck. | Delete affected artefacts, regenerate, note in lessons learned. | Column `LicencePlate` appears in any saved artefact or screenshot. |
| RSK-14 | Safety liability of an automated limit: an operator or reviewer assumes the system is safe to run unattended; a wrong (too high) limit contributes to an accident. | ethics/legal | 2 | 5 | 10 | MVP is decision support only; GUI states "recommendation, operator confirms"; min combiner (D16); fallback always deterministic (D15); no deployment (brief). | Deck clearly states non-production status and needed safety case (human in the loop, field trial). | Anyone describes the MVP as "ready for the highway". |
| RSK-15 | Drift analysis delivers no insight: N+1 is identical to N (ISS-03), so the retraining exercise looks trivial or "not done". | data | 4 | 2 | 8 | Show the check also on a synthetic shifted copy (TC-44) to prove the tool works; report identity as a finding. | Present drift method + synthetic demo instead of real result. | Drift check returns zero difference (expected). |
| RSK-16 | Live demo fails (environment, missing model artefact, Streamlit crash, network). | technical | 3 | 4 | 12 | Pinned `requirements.txt`, committed model artefact, smoke test TC-54 before the talk, offline mode. | Backup screen recording; screenshots in appendix. | Any failure in the final dry run. |
| RSK-17 | Unexplained reductions (ISS-07) bias the model for "normal" conditions. | data | 3 | 2 | 6 | Model only used when dark/ice (slide 3, D5); 28 rows flagged; optional sensitivity run without them. | Exclude the 28 rows and retrain; report both. | Normal-condition predictions differ strongly with/without the rows. |
| RSK-18 | Environment / dependency problems (Python 3.13 wheels for scikit-learn, Streamlit; different OS in team). | technical | 2 | 3 | 6 | Pin versions, test install on a clean venv early, CI or scripted `pytest` run. | Downgrade to Python 3.12 (document deviation from D18). | Install failure on any team machine. |
| RSK-19 | Requirements misinterpretation: our assumptions (D7, D14, D15, AQI > 60 = "poor") differ from what the lecturer expects; no clarification possible. | requirements | 3 | 3 | 9 | Every assumption written in decision log with reason and evidence; deck has an "assumptions" slide. | Show that assumptions are parameters (thresholds, mapping, AQI table) changeable in config. | Feedback in intermediate units contradicts an assumption. |
| RSK-20 | Non-reproducible training (random init, thread nondeterminism) gives different numbers in report and demo. | ML | 2 | 2 | 4 | Fixed `random_state`, saved artefact, TC-46 reproducibility test, numbers in deck generated from the saved artefact. | Re-generate all numbers from one artefact. | Two runs differ in test MAE by > 0.01. |
| RSK-21 | LLM model id deprecated or API/SDK changes before the last unit. | LLM/external | 2 | 2 | 4 | Model id in config, SDK pinned, fallback (D15). | Update config; fallback meanwhile. | Deprecation notice / 404 model error. |
| RSK-22 | Feature edge cases: lux = 0 → log10 = −inf, wind direction 0 vs 360, NaN after cleaning → crash or silent NaN prediction. | technical | 3 | 2 | 6 | Floor for log, sin/cos encoding (D11), NaN assertion before predict; TC-11, TC-48. | Hotfix with input guard. | Any NaN/inf in feature matrix or prediction. |
| RSK-23 | Operator enters implausible GUI values (temp 500, negative water), model extrapolates silently. | technical | 3 | 3 | 9 | Input widgets bounded by SensorTypes min/max; warning when outside training range; TC-58. | Block decision, show error. | Out-of-range input accepted in testing. |
| RSK-24 | Team member unavailable (bus factor) near the deadline. | project/schedule | 2 | 3 | 6 | Pairing on pipeline and model; docs (01–07) kept current; everything in repo. | Re-assign; cut scope per RSK-11. | Missed meetings, unmerged work > 1 week. |
| RSK-25 | Rule boundary / unit error: SPEC1 says 500 **milli**lux = 0.5 lux; using 500 lux or `<=` instead of `<` misclassifies hours. SPEC2 "more than 1000 µm" and "below 0 °C" are strict. | requirements | 2 | 4 | 8 | Rules as plain code with named constants (D5); boundary tests TC-23..TC-27; check condition counts (dark 354 h, ice 62 h) in TC-61. | Fix constant, rerun pipeline and evaluation. | Condition counts differ from 354 / 62 / 389. |
| RSK-26 | Automation bias: management or operators over-trust model numbers (e.g. "0.98 near-accidents/h at 60") although test error is large and data is confounded. | ethics/legal | 3 | 4 | 12 | Show test MAE next to every prediction in the GUI; show baseline value; deck explains confounding. | Explicit disclaimer slide; recommend field trial before any use. | Audience questions treat predictions as guarantees. |

Score = P × I for every row; 26 risks in total (4 high, 13 medium, 9 low).

### 2.1 Risk ownership, response strategy and status

Strategy: **Avoid** (remove the cause), **Mitigate** (lower P or I), **Accept** (live with it, prepare contingency), **Transfer** (not available in a student project, not used).

| Risk | Owner | Strategy | Status | Linked decisions | Next review |
|---|---|---|---|---|---|
| RSK-01 | ML | Accept | Open – expected to occur | D7, D8 | After first evaluation run |
| RSK-02 | ML | Mitigate | Open – guard designed | D5, D9 | After first evaluation run |
| RSK-03 | ML | Mitigate | Open | D12, D18 | After first evaluation run |
| RSK-04 | ML | Accept | Open | D13 | Deck review |
| RSK-05 | DEV | Mitigate | Open | D14, D15 | REQ2 implementation done |
| RSK-06 | DEV | Mitigate | Open | D15 | Final dry run |
| RSK-07 | DEV | Avoid | Open | – | Before every submission |
| RSK-08 | DEV | Avoid | Open – low | D14 | Code review of prompt builder |
| RSK-09 | DE | Mitigate | Open | D1 | After sensitivity run |
| RSK-10 | DE | Accept | Open – low | D2 | Milestone |
| RSK-11 | PL | Mitigate | Open | D17, D18 | Weekly |
| RSK-12 | PL | Mitigate | Open | D8 | Dry run |
| RSK-13 | DE | Avoid | Open | D20 | Before every submission |
| RSK-14 | PL | Mitigate | Open | D15, D16 | Deck review |
| RSK-15 | DE | Accept | Open – will occur | D13 | Drift report done |
| RSK-16 | QA | Mitigate | Open | D17, D18 | Final dry run |
| RSK-17 | DE | Accept | Open | D10 | After first evaluation run |
| RSK-18 | DEV | Mitigate | Open | D18 | Week 1 setup |
| RSK-19 | RE | Mitigate | Open | all D | After each unit with feedback |
| RSK-20 | ML | Avoid | Open | D18 | After first evaluation run |
| RSK-21 | DEV | Accept | Open – low | D14, D15 | Milestone |
| RSK-22 | ML | Avoid | Open | D11 | Feature builder done |
| RSK-23 | DEV | Mitigate | Open | D17 | GUI done |
| RSK-24 | PL | Mitigate | Open | – | Weekly |
| RSK-25 | RE | Avoid | Open | D5 | Rules implemented |
| RSK-26 | PL | Mitigate | Open | D8 | Deck review |

### 2.2 Risk response timeline (by project phase)

| Phase | Risks that become live | Key actions |
|---|---|---|
| Data preparation | RSK-09, RSK-10, RSK-13, RSK-17, RSK-22, RSK-25 | Loader + cleaning tests, condition counts check, licence-plate drop |
| Model training & evaluation | RSK-01, RSK-02, RSK-03, RSK-04, RSK-20 | Baseline first, guard, day split, seed, reachability rate |
| Operational stage (GUI, REQ2) | RSK-05, RSK-06, RSK-07, RSK-08, RSK-21, RSK-23 | Mocked tests, fallback, secrets handling, input bounds |
| Retraining analysis | RSK-15 | Drift on N+1 plus synthetic shift |
| Presentation (last unit) | RSK-12, RSK-14, RSK-16, RSK-26 | Storyline, disclaimers, dry run, backup recording |
| Whole project | RSK-11, RSK-18, RSK-19, RSK-24 | Scope freeze, pinned environment, assumptions slide |

## 3. Risk heat map (5 × 5)

Rows = impact, columns = probability. Cell lists risk IDs (prefix RSK- omitted).

| Impact \ Probability | 1 rare | 2 unlikely | 3 possible | 4 likely | 5 almost certain |
|---|---|---|---|---|---|
| **5 severe** | – | 14 | 12 | **02** | – |
| **4 major** | 10 | 07, 13, 25 | 11, 16, 26 | – | **01** |
| **3 moderate** | – | 09, 18, 24 | 05, 06, 19, 23 | 03 | **04** |
| **2 minor** | 08 | 20, 21 | 17, 22 | 15 | – |
| **1 negligible** | – | – | – | – | – |

Band legend: score ≥ 15 = high (bold), 8–14 = medium, ≤ 7 = low.

| Band | Risks |
|---|---|
| High (15–25) | RSK-01 (20), RSK-02 (20), RSK-04 (15), RSK-12 (15) |
| Medium (8–14) | RSK-03 (12), RSK-11 (12), RSK-16 (12), RSK-26 (12), RSK-14 (10), RSK-05 (9), RSK-06 (9), RSK-19 (9), RSK-23 (9), RSK-07 (8), RSK-13 (8), RSK-15 (8), RSK-25 (8) |
| Low (1–7) | RSK-09 (6), RSK-17 (6), RSK-18 (6), RSK-22 (6), RSK-24 (6), RSK-10 (4), RSK-20 (4), RSK-21 (4), RSK-08 (2) |

## 4. Top-5 risks for management

Ranked by score; tie at 12 broken in favour of the risk with the most direct business/safety consequence.

| Rank | Risk | Score | One sentence for management |
|---|---|---|---|
| 1 | RSK-01 REQ1 target not reachable | 20 | The historical data shows more than one near-accident per hour at every speed limit, so the system will often report that no speed limit alone can meet the target – this is a finding about the highway, not a software defect. |
| 2 | RSK-02 Confounding / unsafe advice | 20 | Because limits were lowered when conditions were already bad, a naive model would learn "faster is safer"; we block this with a safety guard and rules, but the model must not be trusted without a field trial. |
| 3 | RSK-12 Message does not land | 15 | If the honest result is presented as failure, the valuable findings (data gaps, unreachable target, duplicate N+1 file) are lost, so we lead with findings and a working demo. |
| 4 | RSK-04 One month of data | 15 | The model has only seen January; any use in other seasons requires new data and retraining, which our drift check is built to detect. |
| 5 | RSK-26 Over-trust in numbers | 12 | Predictions come with a large error margin, so every number in the GUI is shown next to its error and a baseline, and the system stays a recommendation for a human operator. |

## 5. Issue ↔ risk ↔ decision cross-reference

| Issue | Related risks | Decisions | Tests (see 07) |
|---|---|---|---|
| ISS-01 | RSK-01, RSK-02, RSK-26 | D7, D8, D9 | TC-29..TC-32, TC-51 |
| ISS-02 | RSK-04, RSK-03 | D12, D13 | TC-47, TC-43/44 |
| ISS-03 | RSK-15 | D13 | TC-03, TC-43 |
| ISS-04 | RSK-09 | D1 | TC-17..TC-19 |
| ISS-05 / ISS-06 | RSK-10 | D2, D3 | TC-21, TC-60 |
| ISS-07 | RSK-17 | D10 | TC-53, TC-62 |
| ISS-08 / ISS-09 | RSK-22 | D19 | TC-01..TC-05 |
| ISS-10 | RSK-19 | D19 | TC-07..TC-16 |
| ISS-11 | RSK-05..RSK-08, RSK-21 | D14, D15 | TC-35..TC-42 |
| ISS-12 | – | D6 | TC-20 |
| ISS-13 | RSK-13 | D20 | TC-45 |
| ISS-14 | RSK-02, RSK-03 | D9 | TC-32, TC-52 |
| ISS-15 | RSK-19, RSK-25 | D5, D7, D14, D15 | TC-23..TC-27, TC-40 |
| ISS-16 | – | D11 | TC-50 |
| ISS-17 | RSK-22 | D11 | TC-48 |

## 6. Open points proposed for the decision log

> **Status update (review round 1, 2026-11-10):** these points are now resolved in the [decision log](05-decision-log.md): P1 → D26, P3 → D25, poor-air threshold → D14, AQI rounding / missing sensor type → D30, AQI field → D31, training population → D27, extrapolated cells → D32, log of zero lux → D11.


These came up while writing the register and are not yet covered by D1–D32. They are proposals; the decision log owner decides.

| # | Gap | Proposal |
|---|---|---|
| P1 | Air-quality API fails → D15 table needs an AQI value that we do not have. | Use last cached AQI if < 3 h old, else manual AQI field in GUI; if empty, no REQ2 reduction + visible warning. |
| P2 | Non-integer AQI at table boundaries (e.g. 60.4). | Round up (ceil) before table lookup: conservative. |
| P3 | Tie in D7 "lowest prediction" after the D9 guard (several limits share the minimum). | Resolved by D25: highest limit within ε = 0.05/h of the minimum. |
| P4 | All sensors of one type missing in one hour. | Exclude hour from training and flag; at runtime GUI requires the value. |
| P5 | lux = 0 before log10. | Floor at 0.001 lux (lowest observed order of magnitude, F08). |
| P6 | "Poor air quality" threshold for REQ2. | EU AQI > 60, consistent with the D15 table. |
| P7 | LLM result far from AQI table. | Accept LLM value only if within ±10 km/h of the table value, else fallback. |

## 7. Review log

| Date | Version | Change | By |
|---|---|---|---|
| 2026-11-10 | 0.1 | Initial register: 17 issues, 26 risks, heat map, top-5 | QA & Risk |
