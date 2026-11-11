"""Typed configuration loaded from config.yaml (architecture §11.2)."""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PathsConfig:
    raw_dir: Path
    readings_file: Path
    readings_n1_file: Path
    accidents_file: Path
    sensors_file: Path
    sensor_types_file: Path
    models_dir: Path
    logs_dir: Path
    reports_dir: Path


@dataclass(frozen=True)
class RulesConfig:
    dark_lux_threshold: float
    ice_water_um_threshold: float
    ice_temp_c_threshold: float


@dataclass(frozen=True)
class CleaningConfig:
    max_interp_gap_h: int
    spike_rel_range: float
    valid_limits: list[int]
    limit_carry_forward_h: int


@dataclass(frozen=True)
class FeaturesConfig:
    lux_epsilon: float


@dataclass(frozen=True)
class SplitConfig:
    train_days: list[int]
    test_days: list[int]


@dataclass(frozen=True)
class ModelConfig:
    hidden_layer_sizes: list[int]
    alpha: float
    learning_rate_init: float
    max_iter: int
    seeds: list[int]
    target_transform: str
    artefact: Path


@dataclass(frozen=True)
class DecideConfig:
    candidate_limits: list[int]
    target_rate: float
    unreachable_epsilon: float
    req1_max_limit: int
    default_limit: int
    crash_display_limit: int


@dataclass(frozen=True)
class AQConfig:
    latitude: float
    longitude: float
    horizon_hours: int
    timeout_s: float
    cache_ttl_min: int
    max_cache_age_h: float
    poor_aqi_threshold: float
    fallback_table: list[list[float]]


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    model: str
    effort: str
    max_tokens: int
    timeout_s: float
    max_retries: int
    cache_ttl_min: int
    max_calls_per_day: int
    prompt_version: str
    plausibility_margin_kmh: int


@dataclass(frozen=True)
class GUIConfig:
    replay_interval_min: float
    audit_rows: int


@dataclass(frozen=True)
class DriftConfig:
    alpha: float
    mean_shift_rel: float


@dataclass(frozen=True)
class Config:
    paths: PathsConfig
    rules: RulesConfig
    cleaning: CleaningConfig
    features: FeaturesConfig
    split: SplitConfig
    model: ModelConfig
    decide: DecideConfig
    air_quality: AQConfig
    llm: LLMConfig
    gui: GUIConfig
    drift: DriftConfig


def _build(cls, data: dict, where: str):
    names = {f.name for f in fields(cls)}
    unknown = set(data) - names
    missing = names - set(data)
    if unknown:
        raise ValueError(f"unknown config key(s) in {where}: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing config key(s) in {where}: {sorted(missing)}")
    return cls(**data)


def load_config(path: Path = Path("config.yaml")) -> Config:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.resolve().parent

    p = dict(raw.get("paths", {}))
    raw_dir = (base / p.get("raw_dir", ".")).resolve()
    for key in ("readings_file", "readings_n1_file", "accidents_file", "sensors_file", "sensor_types_file"):
        if key in p:
            p[key] = raw_dir / p[key]
    for key in ("models_dir", "logs_dir", "reports_dir"):
        if key in p:
            p[key] = base / p[key]
    p["raw_dir"] = raw_dir
    m = dict(raw.get("model", {}))
    if "artefact" in m:
        m["artefact"] = base / m["artefact"]

    sections = {
        "paths": (PathsConfig, p), "rules": (RulesConfig, raw.get("rules", {})),
        "cleaning": (CleaningConfig, raw.get("cleaning", {})),
        "features": (FeaturesConfig, raw.get("features", {})), "split": (SplitConfig, raw.get("split", {})),
        "model": (ModelConfig, m), "decide": (DecideConfig, raw.get("decide", {})),
        "air_quality": (AQConfig, raw.get("air_quality", {})), "llm": (LLMConfig, raw.get("llm", {})),
        "gui": (GUIConfig, raw.get("gui", {})), "drift": (DriftConfig, raw.get("drift", {})),
    }
    unknown = set(raw) - set(sections)
    if unknown:
        raise ValueError(f"unknown config section(s): {sorted(unknown)}")
    return Config(**{name: _build(cls, data, name) for name, (cls, data) in sections.items()})
