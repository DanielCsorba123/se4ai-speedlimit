# Handoff · state on 2026-11-11 evening

Read this first when continuing on another device (or in a new Claude session).

## Where things stand

- **MVP complete** on `main`: training pipeline, guarded REQ1 network, REQ2 live LLM (Groq free tier, `openai/gpt-oss-120b`), Streamlit GUI, drift check. **185 tests pass.** All 8 demo scenarios pass (`docs/evidence/acceptance_run.md`).
- **Deck:** 16 slides. Sources are in `docs/presentation/project/`; the exports (PDF, PPTX with notes) are in `docs/exports/`. The live editable deck is a private claude.ai artifact: https://claude.ai/artifact/74T5TfoZTDT32zvwf9MnMi
- **Dossier:** `docs/exports/SpeedLimit_Project_Dossier.pdf` (artifact: https://claude.ai/artifact/S7761RaVs4AX63rHyy8mQ6)
- **Decisions:** D1–D38 in `docs/05-decision-log.md`. Every build ruling is in `docs/superpowers/plans/2026-11-10-speedlimit-mvp.ledger.md`.
- **Team review:** `SpeedLimit-Review-2026-11-11.pdf` by Alek (8 findings, see below).

## Set up on a new machine

```bash
git clone https://github.com/DanielCsorba123/se4ai-speedlimit.git
cd se4ai-speedlimit
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]" markdown        # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m speedlimit.cli_train                     # recreates models/ (about 4 s)
.venv/Scripts/python -m pytest -q                                # expect 185 passed
```

- **API key:** create `.env` (or `.env.txt`) next to `config.yaml` with `GROQ_API_KEY="gsk_..."`. It is git-ignored and **not in the repo**: copy it over yourself or create a new key at console.groq.com.
- **GUI:** `.venv/Scripts/streamlit run src/speedlimit/app.py --theme.base light`. Demo links: `http://localhost:8501/?scenario=AT-1` to `AT-8`. Put a value like 92 in "Simulated forecast EAQI" to see the live LLM.
- **Screenshots and exports:** `.venv/Scripts/python -m playwright install chromium` if Chrome is missing (the scripts use the installed Chrome via `channel="chrome"`). Then run `analysis/capture_screenshots.py` (with the GUI running), `python analysis/build_dossier.py` and `analysis/export_artifacts.py`.

## Open items: Alek's review (none fixed yet)

| # | Severity | What | Note |
|---|---|---|---|
| F1 | High | AT-6 evidence | Screenshots were re-captured with model 1026 (shows 2.413/h). Only `acceptance_run.md` line 21 still says "best 2.40/h", which should be 2.41/h |
| F2 | High | Deck is planned for 15 min, but the brief may allow **7 min** | **Confirm the time limit first.** Then cut to about 8 slides, or shorten the notes and drop the live demo. Change "fifteen minutes" in the cover notes |
| F3 | Med-high | Docs vs code: REQ1 / AC-REQ1-03 / D35 say "lowest rate / 40", but the code uses the ε rule (D25). **Real gap:** at EAQI 61–80 an LLM answer of 80 passes V4, so a poor-air hour gets no reduction | Fix V4 (reject anything looser than the table, or drop 80 from the LLM enum) and add a test for AQI 70 + LLM 80. Update REQ1, AC-REQ1-03, D35 and traceability |
| F4 | Medium | `markdown` is not declared in pyproject | Add `markdown>=3` to the dev extras |
| F5 | Medium | `evaluate()` crashes when the test slice has no dark/ice hours | Guard n == 0 in `model.evaluate` and in cli_train's dark/ice block |
| F6 | Low-med | D30 fail-safe misses `pd.NA`; `table_limit(nan)` raises | Use `pd.isna` in `rules._missing`; make `table_limit` / `is_poor` NaN-safe |
| F7 | Low | Stale docs: architecture still names `types.py`, `data/raw`, `app.log`, `llm_cache.json`; D1–D32/D33 ranges and model 0906 still cited; hypothesis tests claimed but missing | One documentation sweep |
| F8 | Low | F09 says 89 % (correct: 91.9 %); deck says "S01–S08" (there is no S07); Streamlit toolbar visible in screenshots | Regenerate F09; start the app with `--client.toolbarMode=minimal` before re-capturing |

## Also pending

- Rehearse the deck with a timer (after settling F2) and record a 60-second backup video.
- Optional deferred minors: see D36 in the decision log (all decided; nothing blocking).
