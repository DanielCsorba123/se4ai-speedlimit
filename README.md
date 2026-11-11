# SpeedLimit MVP (SE4AI)

Sets a highway speed limit automatically. The default is 80 km/h. A neural network reduces it when it is dark or there is black-ice danger (REQ1), and an LLM reduces it when poor air quality is forecast (REQ2). Course case study *SpeedLimit*, exercise SpeedLimit21.

**Continuing the work?** Start with [docs/HANDOFF.md](docs/HANDOFF.md) (state, setup on a new machine, open review items).

## Presentation and dossier

Open without any account: [deck (PDF)](docs/exports/SpeedLimit_Management_Deck.pdf) · [deck (PPTX)](docs/exports/SpeedLimit_Management_Deck.pptx) · [project dossier (PDF)](docs/exports/SpeedLimit_Project_Dossier.pdf).

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Put your Groq API key (free tier) into a `.env` or `.env.txt` file next to `config.yaml` (both are git-ignored, never into `config.yaml`):

```
GROQ_API_KEY="gsk_..."
```

To use Anthropic instead, set `llm.provider: anthropic` and `ANTHROPIC_API_KEY`.

## Run

| What | Command |
|---|---|
| Tests | `.venv/Scripts/python -m pytest -q` |
| Train (Task 4) | `.venv/Scripts/python -m speedlimit.cli_train --config config.yaml` |
| GUI (Task 8) | `.venv/Scripts/streamlit run src/speedlimit/app.py` |
| Evidence figures | `python analysis/make_figures.py` |
| Live LLM sample | `.venv/Scripts/python analysis/llm_live_sample.py` |
| Dossier site | `python analysis/build_dossier.py` |
| Test fixtures | `python tests/fixtures/make_fixtures.py` |

## GUI environment overrides

| Variable | Effect |
|---|---|
| `SPEEDLIMIT_OFFLINE=1` | No Open-Meteo call, LLM off (tests, offline demos) |
| `SPEEDLIMIT_MODELS_DIR` | Folder with `latest.joblib` / `baseline_table.json` (default `models/`) |
| `SPEEDLIMIT_LOGS_DIR` | Folder for `decisions.jsonl` / `llm_calls.jsonl` (default `logs/`) |

## Layout

- `src/speedlimit/`: the package. `config.py` holds the typed settings; `domain.py` holds the shared value types (architecture §4.3).
- `tests/`: `unit/`, `integration/`, `fixtures/` (small slices of the course CSVs, plus a copy with the slide-17 faults injected).
- `docs/`: charter, requirements, data report, architecture, decision log (D1–D32), risks, tests, storyline, lessons, and the backlog plan in `docs/superpowers/plans/`.
- Course CSVs and the case-study deck are in the repo root.
