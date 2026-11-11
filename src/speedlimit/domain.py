"""Shared value types (architecture §4.3). No licence-plate data anywhere (D20)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Situation:
    timestamp: datetime          # hour being decided
    lux: float                   # mean of sensors 2/9/12 (D4)
    water_um: float              # mean of 1/8/11
    temp_c: float                # mean of 15/18/19 (D2, D3)
    humidity: float              # sensor 4
    noise_db: float              # sensor 3
    wind_strength: float         # mean of 6/14
    wind_dir_deg: float          # mean of 5/13
    traffic_cps: float           # sensor 16 (D2)
    current_limit: int           # informational only, not a model input at runtime


@dataclass(frozen=True)
class RuleResult:
    dark: bool
    black_ice: bool
    missing_inputs: tuple[str, ...] = ()   # inputs treated fail-safe as "condition met" (D30)

    @property
    def req1_active(self) -> bool:
        return self.dark or self.black_ice


@dataclass(frozen=True)
class Req1Result:
    active: bool
    limit: int
    rates_raw: dict[int, float]
    rates_guarded: dict[int, float]      # after the monotone guard (D9)
    target_reachable: bool
    source: Literal["model", "baseline_table", "inactive"]
    extrapolated: tuple[int, ...] = ()   # limits without training data in this condition (D32)


@dataclass(frozen=True)
class AQSummary:
    lat: float
    lon: float
    decision_time: datetime
    horizon_h: int
    eaqi_max: float
    eaqi_mean: float
    pm25_max: float
    pm25_mean: float
    pm10_max: float
    pm10_mean: float
    no2_max: float
    no2_mean: float
    o3_max: float
    o3_mean: float
    eaqi_hourly: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Req2Result:
    limit: int
    reason: str
    source: Literal["llm", "table", "manual", "none"]
    aq: AQSummary | None


@dataclass(frozen=True)
class Decision:
    limit: int
    winning_reasons: list[Literal["REQ1", "REQ2", "REQ3"]]
    rule: RuleResult
    req1: Req1Result
    req2: Req2Result
    explanation: str
    model_version: str | None
    situation: Situation | None = None       # inputs, for the audit log (arch 11.1)
    decided_at: datetime | None = None
