# SpeedLimit MVP (SE4AI)

Sets a highway speed limit automatically. The default is 80 km/h. A neural network reduces it when it is dark or there is black-ice danger (REQ1), and an LLM reduces it when poor air quality is forecast (REQ2). Course case study *SpeedLimit*, exercise SpeedLimit21.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Copy your Anthropic key into the environment (never into `config.yaml`):

```bash
export ANTHROPIC_API_KEY=...
```

## Run

| What | Command |
|---|---|
| Tests | `.venv/Scripts/python -m pytest -q` |
| Train (Task 4) | `.venv/Scripts/python -m speedlimit.cli_train --config config.yaml` |
| GUI (Task 8) | `.venv/Scripts/streamlit run src/speedlimit/app.py` |
| Evidence figures | `python analysis/make_figures.py` |
| Dossier site | `python analysis/build_dossier.py` |
| Test fixtures | `python tests/fixtures/make_fixtures.py` |

## Layout

- `src/speedlimit/`: the package. `config.py` holds the typed settings; `domain.py` holds the shared value types (architecture §4.3).
- `tests/`: `unit/`, `integration/`, `fixtures/` (small slices of the course CSVs, plus a copy with the slide-17 faults injected).
- `docs/`: charter, requirements, data report, architecture, decision log (D1–D32), risks, tests, storyline, lessons, and the backlog plan in `docs/superpowers/plans/`.
- Course CSVs and the case-study deck are in the repo root.
