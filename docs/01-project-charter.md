# 01 · Project Charter

| | |
|---|---|
| Project | SpeedLimit MVP |
| Course | SE4AI (MSc), exercise ID SpeedLimit21, lecturer M. Hasitschka |
| Version | 0.1 · 2026-11-10 · Draft |
| Owner | Project Lead |

## 1. Why

A highway operator wants the speed limit set automatically. The default is **80 km/h**. The limit goes down when:

- it is **dark** or there is **black-ice** danger. A neural network decides how much, with the goal of at most one near-accident per hour (REQ1).
- **poor air quality** is forecast. An LLM decides how much, based on an air-quality API (REQ2).

When neither applies, the limit stays at 80 (REQ3).

## 2. What we deliver (main exercise, deck slide 32)

| # | Deliverable | Done when |
|---|---|---|
| DL1 | **Training stage**: cleaning + transformation pipeline and a trained neural network | `cli_train` produces a model artefact and a model card with honest metrics against the baseline |
| DL2 | **Operational stage**: GUI to enter parameters (temperature, light, water, …) that sets the limit on a regular basis | Streamlit app runs locally, recomputes on input change and on a timer, and shows its reasoning |
| DL3 | **REQ2 path**: air-quality forecast + LLM with fallback | A live call works and the fallback is proven by tests |
| DL4 | **Management presentation** covering all SpeedLimit exercises + lessons learned | Deck rehearsed at ≤ 15 min, presented in the last unit, kept for semester 3 |
| DL5 | Results of the earlier exercises: requirements, architecture/router diagram, data preparation (class diagram, error analysis, feature engineering), cleaning code, retraining analysis | Documents 02–07 in this folder, then code |

## 3. Scope

**In:** local Python MVP, January data V100, rule engine for SPEC1/2, NN for REQ1, LLM for REQ2, GUI, tests, documentation, presentation.

**Out:** real sensors, deployment to production or high-performance infrastructure, connecting to real road signage, multi-month or seasonal modelling, user management.

## 4. Ground rules

- **No questions go to the lecturer now.** Every ambiguity becomes a documented decision ([05-decision-log](05-decision-log.md)) that we defend in the presentation.
- **Be transparent about the data.** The data barely supports REQ1 ([F04](figures/F04_req1_near_accidents_vs_speed.png)). We build to the requirement anyway and report the gap openly (D8).
- **Every claim has evidence.** Each number in the documents comes from `analysis/make_figures.py` → `figures/facts.json`.
- **AI-assisted development** (vibe coding with Claude Code + superpowers skills) is allowed. We still keep TDD and a review on every task.

## 5. Team perspectives used

| Perspective | Owns | Document |
|---|---|---|
| Project Lead | charter, backlog, decisions, presentation | 01, 05, plan, 08, 09 |
| Requirements Engineer | stakeholders, REQ/SPEC/NFR, acceptance criteria | 02 |
| Data Scientist / Engineer | data quality, class diagram, features, retraining | 03 |
| Solution Architect / ML | router architecture, model, LLM, GUI design | 04 |
| QA & Risk | risk/issue register, test strategy, demo script | 06, 07 |

## 6. Milestones

| M | Content | Exit |
|---|---|---|
| M0 | Recon + documentation baseline (this set) | Docs 01–09 reviewed |
| M1 | Data stack (backlog tasks 0–3) | Hourly table matches facts.json |
| M2 | Model + REQ1 decision (tasks 4–5) | Model card written |
| M3 | REQ2 + router + GUI (tasks 6–8) | End-to-end demo |
| M4 | Drift, acceptance, screenshots (tasks 9–10) | All tests green |
| M5 | Presentation (task 11) + UML (task 12) | Rehearsed |
