# Acceptance run · 2026-11-11

| | |
|---|---|
| Build | branch `build/mvp`, model `20261111-1026-6de7f31` (retrained after the final review) (trained on V100, days 1–24) |
| Test suite | `.venv/Scripts/python -m pytest -q` → **185 passed** (after the final-review fix pass and the Groq provider) (unit, integration, GUI via AppTest; network tests excluded) |
| GUI | `streamlit run src/speedlimit/app.py --theme.base light`, live Open-Meteo forecast on, LLM `openai/gpt-oss-120b` on Groq's free tier (D37) |
| Screenshots | `analysis/capture_screenshots.py` (Playwright + installed Chrome) → `docs/evidence/screenshots/` |

## Demo scenarios (test strategy §4)

Each scenario opens with the deep link `http://localhost:8501/?scenario=AT-n` (day 25 = test week).

| ID | Inputs | Expected | Observed | Result | Screenshot |
|---|---|---|---|---|---|
| AT-1 | 13:00, 25 000 lux, water 200 µm, 4 °C, EAQI 25 | 80, REQ3 | **80**, REQ3, REQ1 inactive | pass | `S01_AT-1_normal_day_80.png` |
| AT-2 | 22:00, 0.1 lux, otherwise AT-1 | REQ1 active, rate table, highest limit ≤ 1.0 or flag | REQ1 active (dark), **70**, rate table, flag "NOT reachable" (best 1.28/h) | pass | `S02_AT-2_dark_model_decides.png` |
| AT-3 | 11:00, 30 000 lux, −2 °C, water 1500 µm | REQ1 via black ice, limit < 80 or flag | black ice yes, **70**, flag NOT reachable | pass | `S03_AT-3_black_ice_daylight.png` |
| AT-4 | AT-3 with water 1000, then 1001 | 1000 → 80; 1001 → REQ1 | 1000 → **80** (REQ3); 1001 → **70** (REQ1) | pass | `S04a_…`, `S04b_…` |
| AT-5 | AT-1 + simulated forecast EAQI 92 (D38) | REQ2 source "LLM", ≈ 60 | **50**, REQ2, source **llm** (live Groq), reason names EAQI 92 / 86 | pass | `S05_AT-5_poor_air_llm.png` |
| AT-6 | 03:00, 0.01 lux, −8 °C, water 3000 µm | "target not reachable" warning, rate visible | dark + black ice, **70**, NOT reachable (best 2.40/h), rate table | pass | `S06_AT-6_target_not_reachable.png` |
| AT-7 | AT-5 with LLM outage | 60 from table, no crash | observed before the key existed: **60**, table, no crash; outage paths also unit-tested (timeout, error, prose, refusal) | pass | — |
| AT-8 | AT-2 + EAQI 105 | min(REQ1, 50) ≤ 50, both reasons visible | **50**, set by REQ2, REQ1 70 shown alongside | pass | `S08_AT-8_most_restrictive_wins.png` |

Pass rule: every "Then" observed and no crash. **8 of 8 pass.**

## Model results (test days 25–31, `docs/evidence/model_results.json`)

| Metric | Value |
|---|---|
| MAE all test hours (n = 168) | 0.876 vs baseline 0.895 (skill +0.006) |
| MAE dark/ice test hours (n = 82) | 0.790 vs baseline 0.856 (skill +0.081) |
| Target ≤ 1.0/h reachable | 32.9 % of dark/ice test hours (67.1 % "not reachable"); 37.8 % before the review fix |
| Monotone guard changed the curve | 100 % of dark/ice test hours (raw curve always says "faster is safer") |
| Raw vs guarded sensitivity | +0.435 (40 vs 80, raw) → −0.048 (40 vs 70, guarded) near-accidents/h |
| REQ1 choices vs operators (82 h) | system 70 ×64, 60 ×17, 50 ×1 · operators 70 ×19, 60 ×55, 50 ×8 |
| Retraining check year N+1 | no_retrain, 12 648 / 12 648 rows identical (`drift_report.md`) |
| Live air quality (Open-Meteo, Vienna) | EAQI max 45 → REQ2 inactive (`req2_live_sample.json`) |

## Open items
- None. Live LLM sample captured in `docs/evidence/llm_sample.json` (Groq, EAQI 70/92/115 → 60/50/40 km/h, 1.2–2.2 s, each stricter than the table).
