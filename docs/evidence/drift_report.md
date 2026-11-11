# Drift report · year N vs year N+1

Generated 2026-11-11 09:26 by `python -m speedlimit.drift` (D13).

- Reference: `Case_Study_Speed_Limit_SensorReadingsYearN_V100.csv`
- New: `Case_Study_Speed_Limit_SensorReadingsYearNPlus1_V100.csv`
- Rule: a feature drifts when KS p < 0.05 **and** the mean moved more than 0.5 standard
  deviations. Retrain if any core feature (log_lux, water, temp, traffic, speed_limit) drifts.

## Verdict: **no_retrain**

No core feature drifted. Warning: the new readings are identical to the training year (duplicate dataset, C21).

Identical rows: 12648.

| Feature | Core | KS D | p | Mean N | Mean N+1 | Shift (sd) | Drift |
|---|---|---|---|---|---|---|---|
| log_lux | yes | 0.000 | 1 | 1.892 | 1.892 | 0.00 | no |
| water | yes | 0.000 | 1 | 262.387 | 262.387 | 0.00 | no |
| temp | yes | 0.000 | 1 | -3.525 | -3.525 | 0.00 | no |
| humidity |  | 0.000 | 1 | 81.595 | 81.595 | 0.00 | no |
| noise |  | 0.000 | 1 | 95.632 | 95.632 | 0.00 | no |
| wind_strength |  | 0.000 | 1 | 17.897 | 17.897 | 0.00 | no |
| wind_dir_sin |  | 0.000 | 1 | 0.281 | 0.281 | 0.00 | no |
| wind_dir_cos |  | 0.000 | 1 | 0.466 | 0.466 | 0.00 | no |
| traffic | yes | 0.000 | 1 | 15.606 | 15.606 | 0.00 | no |
| hour_sin |  | 0.000 | 1 | -0.000 | -0.000 | 0.00 | no |
| hour_cos |  | 0.000 | 1 | -0.000 | -0.000 | 0.00 | no |
| speed_limit | yes | 0.000 | 1 | 69.167 | 69.167 | 0.00 | no |

## What this means
The N+1 file is a copy of year N (see figure F10), so this check cannot detect anything. The module is ready for real N+1 data: rerun the command with the new file.
