# 09 · Lessons Learned

| | |
|---|---|
| Project | SpeedLimit MVP (SE4AI, ExID SpeedLimit21) |
| Document | Retrospective by project phase |
| Owner | Project Lead |
| Status | Draft, 2026-11-10. Lessons marked **to confirm after implementation** are hypotheses until the build and training run are done. |
| Feeds | Slide 13 of `08-presentation-storyline.md`; carried over to the 3rd semester |
| Sources | `05-decision-log.md` (D1–D20), `figures/facts.json`, figures F01–F12, case study slides, main exercise brief (slide 32) |

## How to read this

Each lesson has three parts:

- **What happened** — the fact, with evidence (figure or decision ID).
- **Why it matters** — the consequence for this or a similar project.
- **Next time** — the concrete change in how we work.

Status tags:

- `[observed now]` — based on analysis already done and verified against the data.
- `[to confirm after implementation]` — expected, but needs evidence from the build, training or demo. Placeholders are marked `[TODO]`.

---

## 1. Requirements

### L1.1 A requirement can be precise and still not achievable `[observed now]`

- **What happened:** REQ1 sets a clear, measurable target: at most one near-accident per hour in dark or black-ice conditions. The data shows 1.3 near-accidents per hour overall and at least 1.04/h in every condition × limit cell. Correlation between limit and near-accidents is 0.008 (F04).
- **Why it matters:** Precision is not feasibility. A target written without looking at the baseline can be unreachable before any line of code exists. If we had found this at the demo, it would have looked like a model failure.
- **Next time:** For every quantitative requirement, compute the historical baseline first and show it next to the target during requirements review. Add "feasibility checked against data: yes/no" as a field on each REQ.

### L1.2 Vague words hide design decisions `[observed now]`

- **What happened:** REQ2 says "reduced in an appropriate way". To build it we had to define allowed limits {40…80, step 10}, a JSON output format and a fallback table (D14, D15). "On average" in REQ1 needed a defined period. "At a regular basis" in the brief needed a meaning (D17).
- **Why it matters:** Each vague word became a decision we made on behalf of the stakeholder. If not written down, these choices would be invisible and impossible to challenge.
- **Next time:** Run the natural-language error checklist (vague terms, missing conditions, passive voice, undefined units) on every requirement before design. Keep a glossary from day one, not at the end.

### L1.3 Source documents contradict each other in small ways `[observed now]`

- **What happened:** The project description says the network is used when it is "dark or the weather is bad"; REQ1 says "dark or danger of black ice". The description says air quality is "current … queried via API"; REQ2 says "predicted". We followed the REQs and used a forecast API (D14).
- **Why it matters:** Small wording differences lead to different systems. Picking one silently is a hidden risk.
- **Next time:** Do a side-by-side read of all source documents and log each contradiction with the chosen interpretation, as we did in the decision log.

### L1.4 A decision log lets the team move without waiting for answers `[observed now]`

- **What happened:** We had a rule not to send questions to the lecturer at this stage. Instead, every open point became a numbered decision (D1–D20) with reason and evidence.
- **Why it matters:** Work never stalled, and every choice can be defended or reversed by ID. It also made the presentation easier: risky choices are already listed.
- **Next time:** Start the decision log at the kick-off. Mark which decisions are "assumption, needs stakeholder confirmation" so they can be batched into one review meeting.

---

## 2. Data

### L2.1 Look at the target against the data before any modelling `[observed now]`

- **What happened:** One grouped bar chart (F04) changed the story of the project from "build a model that meets REQ1" to "build REQ1 transparently and show why it cannot be met".
- **Why it matters:** This was the single most valuable piece of analysis, and it took a fraction of the effort of the model.
- **Next time:** First analysis task on any ML project: plot the target variable against the main control variable, split by condition, with sample sizes on the bars.

### L2.2 Historical operational data is confounded `[observed now]`

- **What happened:** Lower limits coincide with more near-accidents (dark: 1.86/h at 40 km/h vs 1.13/h at 70 km/h). Operators lowered the limit because conditions were worse. A naive model would learn "drive faster to be safer". We added a monotonicity guard (D9).
- **Why it matters:** When the variable we want to control was itself set by humans reacting to conditions, the data cannot tell us its causal effect. This is a design limit, not a tuning problem.
- **Next time:** Ask "who set this variable, and why?" for every input the system will later control. If humans set it, plan for a controlled experiment or add domain constraints early.

### L2.3 Metadata is as error-prone as data `[observed now]`

- **What happened:** Code `T` is used for both temperature and traffic (F02). Sensor 19 reports but has no description; sensors 7, 10, 17 are described but never report (F03). Unit typo "hm/h", padded unit, trailing space in code `W` (F02). We resolved code T by signal behaviour: 15/18/19 correlate ≥ 0.996 and swing around 0 °C; 16 ranges 1.85–30 and correlates 0.21 (F06, D2).
- **Why it matters:** Reading metadata at face value would have fed traffic into the model as temperature, which also breaks the black-ice rule (SPEC2).
- **Next time:** Validate metadata against the readings (range, correlation, daily cycle) before trusting it. Treat sensor master data as a test subject, not as ground truth.

### L2.4 Two files from the same system can use different clocks `[observed now]`

- **What happened:** Readings use hours 0–23, accidents use 1–24 with 44 events at hour 24 (F05). We map accident hour h to reading hour h − 1 (D1).
- **Why it matters:** A one-hour shift silently moves incidents into the wrong conditions, e.g. from night into daylight at dawn. Nothing would crash; the results would just be wrong.
- **Next time:** Check value ranges of every join key in both files before joining. Document the mapping and, where possible, test sensitivity (results with and without the shift). Done in the data report: without the shift the near-accident/limit correlation moves from 0.008 to 0.030, so the conclusion holds either way.

### L2.5 The expected error list did not match our data version `[observed now]`

- **What happened:** Of 12 errors on the course list (slide 17), 4 were present in the V100 files and 8 were not: every sensor has 744 readings, no missing values, month always 1, wind direction max 257° (F12, facts.json). We still implemented the repairs and test them on injected faults (D19).
- **Why it matters:** Copying a known error list into code without checking would have produced repair code for problems that do not exist, and missed checks for ones that do.
- **Next time:** Verify every claimed data issue against the actual file version and record "found / not found". Build repairs as generic checks (range, duplicates, missing, type) rather than one-off fixes for named rows.

### L2.6 Some data issues are process issues, not data errors `[observed now]`

- **What happened:** 28 hours have a reduced limit although neither SPEC1 nor SPEC2 applies, which contradicts REQ3 (F07). We kept them in training, flagged them and never output them (D10).
- **Why it matters:** Deleting them would hide that operators sometimes reduce for reasons the system does not know (e.g. roadworks, events). That is useful information for management.
- **Next time:** Report such cases to the business owner as a question ("why were these reduced?") instead of only cleaning them.

### L2.7 "New data" may not be new `[observed now]`

- **What happened:** The year N+1 readings file is identical to year N, all 12,648 rows; only the header line is missing (F10). The retraining verdict is trivially "no" (D13).
- **Why it matters:** A drift check that reports "no drift" can be a false comfort when the input is a copy. The correct finding is a data-delivery problem.
- **Next time:** Before any drift analysis, run a cheap identity check (row hashes, file checksum). Report identical deliveries as an incident.

### L2.8 One month is a scope limit, not just a small sample `[observed now]`

- **What happened:** All data is January (744 h). There is no summer, no long daylight evenings, almost no variation in month.
- **Why it matters:** The model cannot be validated for other seasons. Dark hours in January (354 of 744) are not representative of the year.
- **Next time:** State the season scope in the model card and the GUI. Ask for a full year before any production decision.

---

## 3. Machine learning

### L3.1 Keep exact rules out of the network `[observed now]`

- **What happened:** SPEC1 and SPEC2 are fixed thresholds. We implement them as plain code that routes to the model (D5). The network only answers "how much to reduce".
- **Why it matters:** Letting a network relearn a known rule wastes data, adds error and makes behaviour harder to explain. Log lux shows a clean day/night split at the SPEC1 threshold (F08), so the rule is easy in code.
- **Next time:** Separate "what is defined" from "what must be learned" during architecture design. Only the second goes into the model.

### L3.2 Turn the requirement into the decision rule `[observed now]`

- **What happened:** The model predicts near-accidents per hour for each candidate limit; the runtime picks the highest limit with prediction ≤ 1.0, or the lowest-risk limit with a "target not reachable" flag (D7).
- **Why it matters:** The output is directly explainable in REQ1 terms, and the failure mode is visible instead of silent.
- **Next time:** Design the model output so that the requirement check is a one-line rule on top of it.

### L3.3 Split by time, not by row `[observed now, result to confirm]`

- **What happened:** Consecutive hours are correlated, so we split by day (days 1–24 train, 25–31 test) and compare against a mean-per-cell baseline (D12).
- **Why it matters:** A random split would leak neighbouring hours into the test set and overstate quality.
- **Next time:** Always define the baseline and the split before training. Recorded: MAE 0.876 (model) vs 0.895 (baseline) on days 25–31.

### L3.4 With no signal, a model can only match the baseline `[observed now]`

- **What happened:** Confirmed. On unseen days the network's Poisson deviance is 1.138 vs 1.145 for the mean-per-cell baseline (skill +0.006); on dark/ice hours MAE 0.790 vs 0.856 (F13).
- **Why it matters:** If confirmed, the honest message is that the neural network is required by the brief but adds little value with this data. If the network clearly beats the baseline, we must check for leakage before believing it.
- **Next time:** Report model and baseline side by side in every result table.

### L3.5 Domain constraints must be enforced, not hoped for `[observed now]`

- **What happened:** The monotonicity guard (D9) changed the raw curve in **100 %** of dark/ice test hours: the raw network predicted +0.435 near-accidents/h more at 40 than at 80 km/h. Implementing it also exposed a second trap: guard + D25 would have kept 80 km/h in the dark, fixed by D33 (REQ1 always reduces).
- **Why it matters:** A high activation rate is direct evidence that the raw model learned the confounded pattern.
- **Next time:** Consider models with built-in monotonic constraints (e.g. monotonic gradient boosting) when the brief allows it.

### L3.6 Small data favours small models and simple features `[to confirm after implementation]`

- **What happened:** 744 rows; we chose a small MLP (D18), log lux (F08), sin/cos for wind direction and hour (D11), mean over redundant sensors (D4). Feature importance was not measured; seed variance is handled by averaging a 5-seed ensemble. Training takes 4 s.
- **Why it matters:** Complex architectures overfit quickly on a few hundred rows.
- **Next time:** Start with the smallest model that meets the brief, and report variance across random seeds.

---

## 4. LLM integration

### L4.1 An LLM in a safety path needs a deterministic fallback from day one `[observed now]`

- **What happened:** REQ2 uses an LLM because there is no training data for air quality. We defined a fixed AQI fallback table and a source label in the GUI before writing the LLM code (D15).
- **Why it matters:** External APIs fail, time out, change, or return odd text. A speed limit must always be set.
- **Next time:** Design the fallback first, then the LLM path. Test the fallback in the demo on purpose.

### L4.2 Constrain the output so it can be tested `[observed now]`

- **What happened:** The LLM must return JSON `{speed_limit ∈ {40..80 step 10}, reason}`; anything else is rejected (D14). Combination with `min` (D16) means the LLM can only make the limit stricter.
- **Why it matters:** Free-text answers cannot be unit-tested or audited. Bounding the output also bounds the harm.
- **Next time:** Treat LLM output like untrusted input: schema validation, allowed values, logging of prompt and response.

### L4.3 "Predicted" changes the data source `[observed now]`

- **What happened:** REQ2 says "predicted", so we use the Open-Meteo forecast API instead of current values (D14). The highway location is not given in the sources, so it is an assumed, configurable coordinate.
- **Why it matters:** Current and forecast values come from different endpoints and can differ a lot.
- **Next time:** Map each requirement verb to a concrete data source in the specification.

### L4.4 Real LLM behaviour `[to confirm after implementation]`

- **What happened:** Still open: the build machine had no Anthropic API key, so no live LLM call ran. Every LLM branch (valid JSON, prose, out-of-set limit, extra key, refusal, timeout, implausible answer, cache, budget) is tested with a fake client, and the live forecast path works.
- **Why it matters:** These numbers decide whether the LLM adds value over the fixed table.
- **Next time:** Run a small fixed evaluation set (e.g. 20 AQI scenarios) on every prompt change.

---

## 5. Process and tooling (incl. AI-assisted "vibe coding")

### L5.1 AI-assisted analysis is fast, verification is the bottleneck `[observed now]`

- **What happened:** We used Claude Code for data exploration, figure generation and documentation. All reported numbers were collected into one machine-written file (`figures/facts.json`) and documents may only cite numbers from there.
- **Why it matters:** An assistant can produce plausible numbers and wording quickly. A single source of verified facts prevents drift between figures, documents and slides.
- **Next time:** Keep the "one facts file, no free-typed numbers" rule. Regenerate figures and facts from scripts, not by hand.

### L5.2 Structured skills beat free-form prompting `[observed now]`

- **What happened:** We built with the superpowers skills (writing plans → executing plans → test-driven development → verification). Tests written first caught real bugs: a spike rule that flagged healthy sibling sensors, a replay timer that skipped hours, and a test that passed without the code it claimed to test (found with a deliberate mutation). The plan's rulings ledger kept 40+ decisions traceable. Cost: more steps per feature, and several plan details had to be overruled by the more precise specs.
- **Why it matters:** "Vibe coding" without a plan produces code that runs but is hard to defend. The brief allows vibe coding; the presentation still has to explain every result.
- **Next time:** Use plan + tests as the contract with the assistant; review the plan, not just the final code.

### L5.3 Injected-fault tests make cleaning code meaningful `[observed now]`

- **What happened:** Because 8 of 12 listed errors are absent in V100 (F12), the cleaning code would otherwise never run. We test each repair on deliberately corrupted copies (D19). 18 cleaning tests run against a fixture with all 8 slide-17 fault types injected; they exposed the spike-rule bug before any real data needed it.
- **Why it matters:** Untested cleaning code fails exactly when a new data version arrives.
- **Next time:** Write a fault-injection fixture for each data-quality rule as part of the data specification.

### L5.4 Writing documents in parallel needs one shared reference `[observed now]`

- **What happened:** Several documents (requirements, architecture, data, decision log, presentation) were written by different roles. The decision log IDs and `facts.json` kept them consistent.
- **Why it matters:** Without shared IDs, each document would restate assumptions slightly differently.
- **Next time:** Create the decision log and facts file before splitting work by role.

### L5.5 Privacy by design is cheap when done early `[observed now]`

- **What happened:** Licence plates are dropped at load time and never stored (D20). They are not needed for the target.
- **Why it matters:** Removing personal data later means cleaning every intermediate file and log.
- **Next time:** Run a data-minimisation check on every column at the data-specification step.

---

## 6. Presentation

### L6.1 Lead with the uncomfortable finding `[observed now]`

- **What happened:** We placed F04 early in the storyline (slide 6) as the central message, followed by what we did about it.
- **Why it matters:** Management trusts a team that reports limits openly. Hiding the finding until Q&A would undermine the whole result.
- **Next time:** Build the storyline around the one figure that changes decisions, and make every other slide support it.

### L6.2 Assertion headlines force clear thinking `[observed now]`

- **What happened:** Every slide title is a statement ("No retraining is needed, because…") rather than a topic ("Retraining").
- **Why it matters:** If we cannot write the headline, we do not yet know the result. This exposed which slides still depend on the build (marked TODO-after-build).
- **Next time:** Draft headlines before content; any headline with a placeholder is a task.

### L6.3 Live demos need a failure plan `[to confirm after implementation]`

- **What happened:** The demo relies on an external LLM and a weather API. We built deep links (`?scenario=AT-1…AT-8`) and captured all eight scenarios as screenshots; the app also runs fully offline. `[to record after the final presentation: whether the backup was needed]`
- **Why it matters:** A failed demo costs more credibility than no demo. Showing the fallback on purpose turns a risk into a feature.
- **Next time:** Rehearse the demo offline once; include one deliberate failure scenario.

### L6.4 End with decisions, not a summary `[observed now]`

- **What happened:** The last content slide asks management for three decisions: revisit the REQ1 target, fund a full year of data, approve a controlled trial.
- **Why it matters:** A management audience needs to know what is expected of them.
- **Next time:** Write the "decision ask" slide first and work backwards.

---

## What management should take away

1. **The prototype works end to end**, from raw sensor files to a recommended limit in a GUI, with AI used only where the requirements need it and a fixed fallback behind the LLM.
2. **The safety target (≤ 1 near-accident per hour) is not supported by the data.** No observed limit, in any condition, gets below it (F04). The system flags this honestly instead of hiding it.
3. **Historical data cannot measure the effect of the speed limit**, because operators set the limit in response to conditions. Only a controlled trial can answer "how much does lowering the limit help?".
4. **One month of winter data is not enough for production.** The "next year" file was a copy of this year, so we have no evidence about change over time.
5. **The data and master-data quality needs ownership.** Ambiguous sensor codes, undocumented sensors, mismatched clocks and unexplained manual reductions are process issues the operator should fix at the source.

## Carry-over to 3rd semester

- **Keep:** this presentation (required by the brief), the decision log (D1–D20), `facts.json` with the scripts that produce it, the figures, the cleaning pipeline with its fault-injection tests, and the drift check.
- **Re-run first:** identity check + drift check on any new data delivery; re-verify every slide-17-type error claim against the new version.
- **Open questions to resolve with stakeholders:** REQ1 target definition; meaning of code T and sensor 19 in master data; reasons for the 28 manual reductions; highway location for the air-quality forecast; whether accident hour 24 really means the hour ending at midnight (D1).
- **Technical next steps:** sensor or data-platform feed instead of manual input; logging of every decision (inputs, model output, LLM response, source); monitoring of near-accident rate per limit and fallback rate; try a model with built-in monotonic constraints.
- **Method next steps:** design of a controlled trial; full-year data collection plan; small fixed evaluation set for the LLM prompt.
- **Fill in:** all `[to confirm after implementation]` lessons once the build, training and demo are done; then update slide 13 of the deck.
