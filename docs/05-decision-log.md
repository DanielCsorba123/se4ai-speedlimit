# 05 · Decision Log (ADR-lite)

| | |
|---|---|
| Project | SpeedLimit MVP (SE4AI, ExID SpeedLimit21) |
| Status | Accepted, 2026-11-10 |
| Rule | No questions go to the lecturer at this stage. Every open point gets a documented assumption here, so we can carry on and defend it in the final presentation. |

Each decision has an ID that the other documents refer to (e.g. "per D1").

| ID | Topic | Decision | Why | Evidence |
|---|---|---|---|---|
| D1 | Hour alignment | Accident `Hour` 1–24 means the hour *ending* at that clock hour, so we map it to reading hour `Hour − 1` (0–23). | The accidents file has no hour 0 and 44 events at hour 24. Readings use 0–23. A shift by 1 keeps all 24 buckets populated and is the only mapping that needs no special case. | F05 |
| D2 | Sensor code `T` | Sensors 15, 18 and 19 are **temperature**. Sensor 16 is **traffic** (cars/s). | 15/18/19 correlate at ≥ 0.996 and swing around 0 °C. Sensor 16 ranges 1.85–30 and correlates only 0.21 with them. | F02, F06 |
| D3 | Undocumented / silent sensors | Treat sensor 19 as temperature (as in D2). Ignore sensors 7, 10 and 17: they have no readings, so there's no air-pressure input. | Nothing to use. | F03 |
| D4 | Redundant sensors | Aggregate sensors of the same type with the **mean** per hour (water 1/8/11, light 2/9/12, wind direction 5/13, wind strength 6/14, temperature 15/18/19). Single sensors: noise = 3 (10 is silent), humidity = 4 (the only H sensor), traffic = 16. Keep the per-sensor spread as a quality signal. | They agree closely, and the mean is robust against one failing sensor. | facts.json |
| D5 | Condition rules | Dark = mean lux < 0.5 (SPEC1's 500 millilux = 0.5 lx; the data is in lux). Black ice = mean water > 1000 µm **and** mean temp < 0 °C (SPEC2). These rules run as plain code, **not** inside the network. | SPECs are deterministic thresholds, so a model must not relearn them. | F08, F11 |
| D6 | Near-accident definition | A near-accident is any row with `CloseCarCm`, `CloseGuardrailCm` or `SkidAngle` set (SPEC4). Rows with `Damage`/`Injured` are accidents, counted separately and reported, but not the REQ1 target. The single empty row is dropped. No distance threshold is applied: every logged event counts. | The log only records events that were already judged critical (CloseCar ≤ 20 cm). | F09 |
| D7 | Learning target | The model learns `near_accidents_per_hour = f(weather features, speed_limit)` as a **count regression**. At runtime it evaluates candidate limits {40, 50, 60, 70, 80} and picks the **highest** limit whose prediction is ≤ 1.0. If none meets the target, it picks the limit with the **lowest** prediction and raises a "target not reachable" flag. | Directly encodes REQ1 and makes the outcome explainable. | F04 |
| D8 | REQ1 not supported by data | We **build it as specified anyway** and are transparent: the model is reported with its real error, the GUI shows the predicted rate and the flag, and the deck shows F04 as a key finding. | Near-accidents are ≥ 1.04/h at every observed limit (corr. 0.008). Within dark and black-ice hours, lower limits coincide with *more* incidents, which looks like confounding: operators lower the limit when conditions are worse. Under normal conditions it's the other way round (60 km/h: 1.04/h, 80 km/h: 1.35/h). | F04 |
| D9 | Monotonicity guard | Predictions must not *increase* as the limit is lowered within the same conditions. Enforce it by post-processing (running minimum over descending limits). | Prevents the confounded data from teaching "drive faster to be safer". | F04 |
| D10 | Unexplained reductions | Keep the 28 "normal-condition but < 80 km/h" hours in training (they are real observations), flag them in the data report, and never output them: REQ3 forces 80 in normal conditions. | Deleting would hide a real data issue. Outputting would violate REQ3. | F07 |
| D11 | Feature set | Inputs: log10(lux + 0.001) (7 hours have lux = 0), water, temperature, humidity, noise, wind strength, wind direction as sin/cos, traffic, hour of day as sin/cos, speed limit. Drop month (always 1), minute/second, and LicencePlate. | Removes leakage and constant columns, handles the circular variables, and is privacy by design. | F08 |
| D12 | Validation | Split by **day** (e.g. days 1–24 train, 25–31 test), not by random rows. The baseline is the mean rate per condition × limit. | Consecutive hours are correlated, so a random split would leak. | — |
| D13 | Year N+1 / retraining | Implement a drift check (per-feature distribution comparison, e.g. KS test plus a mean shift) and run it on year N+1. Expected verdict: **no retraining**, because the file is identical to year N. Report that as a finding. | The exercise asks for the analysis. The tool is reusable once real N+1 data arrives. | F10 |
| D14 | REQ2 air quality | Use the Open-Meteo Air-Quality **forecast** API (free, no key; European AQI, PM2.5, PM10, NO2, O3) for the highway location. Call an LLM (Claude, latest model) with a fixed prompt. It must return JSON `{speed_limit ∈ {40..80 step 10}, reason}`. | REQ2 says "predicted" (slide 3 says "current"). We use the forecast and accept current values as a fallback. "Poor air quality" = EU AQI > 60. Structured output makes the result testable. | — |
| D15 | LLM failure handling | If the API or LLM fails, times out or returns invalid output, fall back to a deterministic AQI table (EU AQI ≤ 60 → 80, 61–80 → 70, 81–100 → 60, > 100 → 50) and show the source in the GUI. | Safety-relevant output can never depend on a single external service. | — |
| D16 | Combining reasons | Final limit = **min**(REQ1 limit if dark/ice, REQ2 limit if poor air, 80). | The most restrictive reason wins, which is the safe choice. | — |
| D17 | Operational stage | A Streamlit GUI with manual sensor inputs (pre-filled from a sample hour) plus an optional "auto refresh every N minutes" mode that replays readings from the CSV. "At a regular basis" = recomputed on every input change and on the timer. | MVP: no real sensors, no deployment (per the brief). | — |
| D18 | Tech stack | Python 3.13, pandas, scipy, scikit-learn (MLPRegressor, i.e. a real neural network that's small enough for 744 rows), Streamlit, anthropic SDK, requests, pytest. | Smallest stack that covers every requirement and matches the course's "neural network". | — |
| D19 | Data version | The V100 files are clean apart from the issues in F02/F03/F05/F07. The pipeline still implements the slide-17 repairs (missing values, text months, out-of-range values, duplicates, missing sensor IDs), each covered by unit tests on injected faults. | Course error list (F12). Makes the pipeline robust for other data versions. | F12 |
| D20 | Privacy | Drop `LicencePlate` at load time and never persist it. | GDPR data minimisation. It isn't needed for the target. | — |
| D21 | Operational targets | LLM timeout 10 s, air-quality API timeout 5 s, replay timer every 60 min of data time (adjustable in the GUI), drift test α = 0.05, ≤ 2 s per decision, ≤ 5 min training on a laptop. | Values the requirements needed but the brief doesn't give. Fixed here so tests can assert them. | — |
| D22 | "Bad weather" | Slide 3's "dark or bad weather" is read as REQ1/SPEC2's "dark or black ice". No other weather condition triggers the NN. | REQ1 and SPEC2 are the more specific source. | — |
| D23 | Highway location | Air-quality queries use a configurable coordinate. The default is Vienna (48.21 N, 16.37 E) as a stand-in for an Austrian highway section. | The brief names no location, but Open-Meteo needs one. | — |
| D24 | Data-version notes | Slide 17's example "Jan 6 20:00 unexplained" is dark in V100, so SPEC1 explains it. The 28 unexplained hours we report are others. The AP range 900–1000 "mmHg" is implausible (≈ hPa), but irrelevant because sensor 17 never reports. | Keeps our claims accurate to the files we actually have. | F07, F12 |
| D25 | REQ1 when target unreachable (amends D7) | When no candidate reaches ≤ 1.0/h, pick the **highest** limit whose guarded rate is within **ε = 0.05/h** of the best rate, not simply the argmin. Configurable as `decide.unreachable_epsilon`. | The architecture review showed that D7 + D9 alone give 40 km/h in nearly every dark/ice hour, because the data has no limit ≤ 1.0. Operators used 60 km/h in 211 of 354 dark hours. ε stops the system from buying a meaningless 0.01/h with 20 km/h. | F04 |
| D26 | Air-quality API failure (extends D15) | Order: (1) forecast cached ≤ 3 h, (2) AQI entered manually in the GUI, (3) no REQ2 reduction plus a visible warning. An LLM answer more than 10 km/h above the table value (e.g. 80 at AQI 120) counts as invalid and goes to the table. | D15 covered LLM failure only, but the table needs an AQI. The plausibility check stops a lenient hallucination. | — |
| D27 | Training population | Train on all 744 hours (the rules aren't inputs, per D5). Report metrics separately for dark/ice hours, since those are the only ones where the model is used. | More data for a weak signal, while the evaluation stays honest about the population that matters. | F04 |
| D28 | Calm wind | When the mean wind strength is 0, set wind-direction sin/cos to 0. | 142 of 197 calm hours still report a direction, which is noise. | data report DQ-16 |
| D29 | Crash display | If the app hits an unexpected error, it displays 60 km/h plus an error banner, and logs the error. | A fail-safe value between the observed operating range and the most cautious limit. MVP-only behaviour. | — |
| D30 | Edge rules | Round a non-integer AQI to the nearest integer before the table lookup. If all sensors of one type are missing for an hour, the hour is excluded from training. At runtime a missing light or water/temperature input counts as the condition being **met** (fail-safe). | Closes boundary and missing-data holes found in the QA review. | — |
| D31 | GUI AQI field | The GUI has a manual AQI field. It's used for demo/test mode and as step (2) of D26. | Demo scenarios need to drive REQ2 without depending on the live forecast. | — |
| D32 | Extrapolation warning | Cells with no training data (80 km/h in dark or black-ice hours, 40 km/h with black ice) are marked "extrapolated" in the GUI's per-limit table and in the model card. | Predictions there are pure extrapolation. Showing that keeps users from over-trusting them. | F04 |

| D33 | REQ1 candidate set | When REQ1 is active, the candidates are {40, 50, 60, 70}. 80 km/h is excluded. Configurable as `decide.req1_max_limit`. | REQ1 says the limit "shall be reduced". Operators used 80 in 0 of 389 dark/ice hours, so that cell is pure extrapolation (D32). With the D9 guard, a confounded flat curve plus D25 would otherwise keep 80 in the dark. Found while implementing Task 5. | F04 |

## Review round 1 (2026-11-10): where the perspective reviews landed

| Raised by | Point | Resolved in |
|---|---|---|
| Requirements | D4 listed silent sensor 10 and had no humidity sensor | D4 (amended) |
| Requirements | SPEC1 in millilux vs lux data | D5 (amended) |
| Requirements / Presenter | "bad weather" vs "black ice", "current" vs "predicted" air | D22, D14 (amended) |
| Requirements | Missing timeouts, timer, α, performance targets | D21 |
| Presenter | Slide 17's Jan 6 20:00 example is dark in V100; AP unit implausible | D24, F07/F12 relabelled |
| Presenter / Architecture | No highway location for the air-quality API | D23 |
| Architecture | D7 + D9 output 40 km/h in almost every dark hour | **D25** (ε = 0.05/h) |
| Architecture / QA | API outage leaves the table without an AQI; LLM plausibility | D26 (= QA proposal P1) |
| Architecture / QA | Train on all hours or only dark/ice? | D27 |
| Data | Wind direction is noise when calm; log of zero lux | D28, D11 (amended) |
| Architecture | Crash behaviour | D29 |
| QA | AQI rounding, all-missing sensor type, GUI AQI field, extrapolated cells | D30–D32 |
| QA | Guard tie-break (P3) | D25 |
