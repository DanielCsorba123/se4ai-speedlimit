"""Cleaning rules, hourly table and accident join (backlog Task 2).

Rule IDs follow the data analysis report §8 (C01–C21). Every repair is
counted in the CleaningReport. On the clean V100 files only the structural
rules C04 (sensor 19 kept) and C05 (silent sensors) fire; the other rules
are exercised with the fault-injected fixture (D19).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from speedlimit.config import CleaningConfig

# D2–D4: semantic groups (hourly column name -> sensor ids)
SENSOR_GROUPS: dict[str, list[int]] = {
    "water": [1, 8, 11],
    "lux": [2, 9, 12],
    "noise": [3],
    "humidity": [4],
    "wind_dir": [5, 13],
    "wind_strength": [6, 14],
    "temp": [15, 18, 19],
    "traffic": [16],
}
GROUP_TYPE = {  # hourly column -> type name used in SensorTypes.csv
    "water": "water", "lux": "light", "noise": "noise", "humidity": "humidity",
    "wind_dir": "wind direction", "wind_strength": "wind strength",
    "temp": "temperature", "traffic": "traffic",
}
SPEED_LIMIT_SENSOR = -1
SENSOR_TO_GROUP = {sid: g for g, ids in SENSOR_GROUPS.items() for sid in ids}
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}
NEAR_FIELDS = ["close_car_cm", "close_guardrail_cm", "skid_angle"]
ACC_FIELDS = ["damage", "injured"]
OUT_COLS = ["month", "day", "hour", "minute", "second", "sensor", "value", "imputed"]


@dataclass
class CleaningReport:
    events: list[tuple[str, int, str]] = field(default_factory=list)
    silent_sensors: list[int] = field(default_factory=list)

    def add(self, rule_id: str, rows: int, note: str) -> None:
        if rows:
            self.events.append((rule_id, int(rows), note))

    def count(self, rule_id: str) -> int:
        return sum(n for r, n, _ in self.events if r == rule_id)


def resolve_sensor_types(sensors: pd.DataFrame) -> dict[int, str]:
    """Sensor id -> type name, applying D2/D3 over the ambiguous metadata.

    Raises if the metadata contradicts the registry for an unambiguous code.
    """
    out: dict[int, str] = {SPEED_LIMIT_SENSOR: "speed_limit"}
    meta = sensors.groupby("sensor_id")
    for group, ids in SENSOR_GROUPS.items():
        tname = GROUP_TYPE[group]
        for sid in ids:
            if sid in meta.groups:
                types = set(meta.get_group(sid)["type"])
                if tname not in types:
                    raise ValueError(f"sensor {sid}: registry says {tname!r}, metadata says {types}")
            out[sid] = tname  # 19 is undocumented and mapped by D3
    return out


def _type_ranges(sensors: pd.DataFrame) -> dict[str, tuple[float, float]]:
    t = sensors.dropna(subset=["type"]).drop_duplicates("type")
    return {r.type: (float(r["min"]), float(r["max"])) for _, r in t.iterrows()}


def _repair_months(df: pd.DataFrame, rep: CleaningReport) -> pd.DataFrame:
    bad = df.month.isna() | ~df.month.between(1, 12)
    if bad.any():
        named = df.loc[bad, "month_raw"].str.strip().str.lower().map(MONTHS)
        modal = int(df.loc[~bad, "month"].mode().iloc[0])
        df.loc[bad, "month"] = named.fillna(modal).astype("Int64")
        rep.add("C08", bad.sum(), f"{named.notna().sum()} month names mapped, "
                                  f"{named.isna().sum()} NULL/invalid set to modal month {modal}")
    return df


def _infer_sensor_ids(df: pd.DataFrame, registry: dict[int, str], rep: CleaningReport) -> pd.DataFrame:
    missing = df.sensor.isna()
    if not missing.any():
        return df
    known = df[~missing]
    reporting = set(known.sensor.dropna().astype(int)) & set(registry)
    present_by_day = known.groupby("day").sensor.agg(lambda s: set(s.astype(int)))
    present_by_hour = known.groupby(["day", "hour"]).sensor.agg(lambda s: set(s.astype(int)))
    n_missing = df[missing].groupby(["day", "hour"]).size()
    inferred = 0
    for idx in df.index[missing]:
        d, h = df.at[idx, "day"], df.at[idx, "hour"]
        # a sensor absent the whole day is a gap (C11), not a lost id
        expected = reporting & present_by_day.get(d, set())
        candidates = expected - present_by_hour.get((d, h), set())
        if len(candidates) == 1 and n_missing.get((d, h), 0) == 1:
            df.at[idx, "sensor"] = candidates.pop()
            inferred += 1
    rejected = int(df.sensor.isna().sum())
    rep.add("C06", inferred, "missing sensor id inferred from the hour's missing sensor")
    rep.add("C06-reject", rejected, "missing sensor id could not be inferred; row removed")
    return df[df.sensor.notna()].copy()


def _dedupe(df: pd.DataFrame, rep: CleaningReport) -> pd.DataFrame:
    key = ["day", "hour", "sensor"]
    dup = df.duplicated(key, keep=False)
    if not dup.any():
        return df
    before = len(df)
    conflicting = df[dup].groupby(key).value.nunique(dropna=False) > 1
    agg = df.groupby(key, as_index=False, sort=False).agg(
        {**{c: "first" for c in df.columns if c not in key + ["value", "imputed"]},
         "value": "mean", "imputed": "any"})
    if conflicting.any():
        agg = agg.set_index(key)
        agg.loc[conflicting[conflicting].index, "imputed"] = True
        agg = agg.reset_index()
    rep.add("C12", before - len(agg), f"duplicate readings removed ({int(conflicting.sum())} conflicting, averaged)")
    return agg[df.columns]


def clean_readings(df: pd.DataFrame, sensors: pd.DataFrame, cfg: CleaningConfig
                   ) -> tuple[pd.DataFrame, CleaningReport]:
    rep = CleaningReport()
    df = df.copy()
    df["imputed"] = False
    registry = resolve_sensor_types(sensors)
    ranges = _type_ranges(sensors)

    # rows without a usable timestamp cannot be placed anywhere
    no_time = df.day.isna() | df.hour.isna() | ~df.hour.between(0, 23)
    rep.add("C01-reject", no_time.sum(), "row without valid day/hour removed")
    df = df[~no_time].copy()

    df = _repair_months(df, rep)                                   # C08
    df = _infer_sensor_ids(df, registry, rep)                      # C06

    unknown = ~df.sensor.astype(int).isin(list(registry))          # C04
    rep.add("C04-reject", unknown.sum(), "reading for an unknown sensor removed")
    df = df[~unknown].copy()
    documented = set(sensors.sensor_id.dropna().astype(int))
    rep.add("C04", (df.sensor == 19).sum(), "sensor 19 is undocumented; kept as temperature (D3)")
    rep.silent_sensors = sorted(documented - set(df.sensor.astype(int)))   # C05
    rep.add("C05", len(rep.silent_sensors), f"documented sensors without readings: {rep.silent_sensors}")

    df = _dedupe(df, rep)                                          # C12
    df["group"] = df.sensor.astype(int).map(SENSOR_TO_GROUP)

    sl = df.sensor == SPEED_LIMIT_SENSOR                           # C16
    bad_limit = sl & df.value.notna() & ~df.value.isin(cfg.valid_limits)
    rep.add("C16", bad_limit.sum(), "speed limit outside the valid set; removed")
    df = df[~bad_limit].copy()

    # C09: out of the documented range -> NaN; WD 360 -> 0
    lo = df.group.map(lambda g: ranges.get(GROUP_TYPE.get(g), (-np.inf, np.inf))[0] if isinstance(g, str) else -np.inf)
    hi = df.group.map(lambda g: ranges.get(GROUP_TYPE.get(g), (-np.inf, np.inf))[1] if isinstance(g, str) else np.inf)
    oor = df.value.notna() & ((df.value < lo) | (df.value > hi))
    rep.add("C09", oor.sum(), "value outside the sensor range set to NaN")
    df.loc[oor, "value"] = pd.NA
    df.loc[(df.group == "wind_dir") & (df.value == 360), "value"] = 0.0

    # C10: in-range spike vs the other siblings (types with >= 3 sensors)
    spikes = 0
    for g, ids in SENSOR_GROUPS.items():
        if len(ids) < 3:
            continue
        lo_g, hi_g = ranges.get(GROUP_TYPE[g], (0.0, 1.0))
        thr = cfg.spike_rel_range * (hi_g - lo_g)
        sub = df[df.group == g]
        grp = sub.groupby(["day", "hour"]).value
        # group median: robust to one outlier (a leave-one-out mean would let the
        # spike drag its healthy siblings over the threshold too)
        med, n = grp.transform("median"), grp.transform("count")
        spike = sub.value.notna() & (n >= 3) & ((sub.value - med).abs() > thr)
        df.loc[spike[spike].index, "value"] = pd.NA
        spikes += int(spike.sum())
    rep.add("C10", spikes, "spike vs sibling sensors set to NaN")

    # C07: fill NaN from siblings, then short interpolation (not for the speed limit)
    sensor_rows = ~(df.sensor == SPEED_LIMIT_SENSOR)
    sib_mean = df[sensor_rows].groupby(["day", "hour", "group"]).value.transform("mean")
    fill = sensor_rows & df.value.isna() & sib_mean.reindex(df.index).notna()
    df.loc[fill, "value"] = sib_mean.reindex(df.index)[fill]
    df.loc[fill, "imputed"] = True
    filled = int(fill.sum())
    # interpolation only for sensors WITHOUT siblings (data report C07); a type whose sensors are
    # all missing leaves the hour incomplete (D30). Gaps are measured in hours, and only whole gaps
    # of <= max_interp_gap_h are filled (never the first part of a longer gap).
    df = df.sort_values(["sensor", "day", "hour"])
    singles = [ids[0] for g, ids in SENSOR_GROUPS.items() if len(ids) == 1 and g != "wind_dir"]
    for sid in singles:
        rows = df[(df.sensor == sid)]
        if not rows.value.isna().any():
            continue
        t = (rows.day.astype(int) * 24 + rows.hour.astype(int)).to_numpy()
        s = pd.Series(rows.value.astype(float).to_numpy(), index=t)
        full = s.reindex(range(t.min(), t.max() + 1))
        gap_id = full.notna().cumsum()
        gap_len = full.isna().groupby(gap_id).transform("sum")
        interp = full.interpolate(limit_area="inside").where(full.isna() & (gap_len <= cfg.max_interp_gap_h))
        new = interp.reindex(t).to_numpy()
        take = rows.value.isna().to_numpy() & ~np.isnan(new)
        idx = rows.index[take]
        df.loc[idx, "value"] = new[take]
        df.loc[idx, "imputed"] = True
        filled += int(take.sum())
    rep.add("C07", filled, "missing values filled (siblings first; single sensors: gaps of <= "
                           f"{cfg.max_interp_gap_h} h interpolated)")
    rep.add("C07-open", int((sensor_rows & df.value.isna()).sum()), "values left missing; hour incomplete")

    df = df.sort_values(["day", "hour", "sensor"]).reset_index(drop=True)
    return df[[c for c in OUT_COLS if c in df.columns]], rep


def _circular_mean_deg(v: pd.Series) -> float:
    v = v.dropna().astype(float)
    if v.empty:
        return np.nan
    r = np.deg2rad(v.to_numpy())
    ang = np.rad2deg(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360.0
    return 0.0 if np.isclose(ang, 360.0) else float(ang)


def to_hourly(df: pd.DataFrame, limit_carry_forward_h: int = 1) -> pd.DataFrame:
    """Wide hourly table indexed by (day, hour): group means, spreads, speed limit."""
    d = df.copy()
    d["sensor"] = d.sensor.astype(int)
    d["value"] = d.value.astype(float)
    d["group"] = d.sensor.map(SENSOR_TO_GROUP)
    key = ["day", "hour"]
    sens = d[d.group.notna()]

    means = sens[sens.group != "wind_dir"].pivot_table(index=key, columns="group", values="value", aggfunc="mean")
    spreads = sens.groupby(key + ["group"]).value.agg(lambda v: v.max() - v.min()).unstack("group")
    spreads.columns = [f"{c}_spread" for c in spreads.columns]
    wd = sens[sens.group == "wind_dir"].groupby(key).value.agg(_circular_mean_deg).rename("wind_dir")
    limit = d[d.sensor == SPEED_LIMIT_SENSOR].groupby(key).value.mean().rename("speed_limit")
    imputed = d.groupby(key).imputed.any().rename("imputed")

    days = sorted(d.day.dropna().astype(int).unique())
    grid = pd.MultiIndex.from_product([days, range(24)], names=key)
    out = pd.concat([means, wd, spreads, limit, imputed], axis=1).reindex(grid)
    for g in SENSOR_GROUPS:
        if g not in out.columns:
            out[g] = np.nan
    out["speed_limit"] = out["speed_limit"].ffill(limit=limit_carry_forward_h)   # C16
    out["imputed"] = out["imputed"].fillna(False).astype(bool)
    out["complete"] = out[list(SENSOR_GROUPS) + ["speed_limit"]].notna().all(axis=1)
    out.index = out.index.set_levels([lvl.astype(int) for lvl in out.index.levels])
    return out


def join_accidents(hourly: pd.DataFrame, acc: pd.DataFrame) -> pd.DataFrame:
    """Add near_accidents / accidents counts per hour (D1 hour shift, D6 definition)."""
    a = acc.copy()
    near = a[NEAR_FIELDS].notna().any(axis=1)
    accident = a[ACC_FIELDS].notna().any(axis=1)
    a = a[near | accident]                                         # C14: drop empty rows
    a = a.assign(hour=a.hour.astype(int) - 1, day=a.day.astype(int))   # C13 / D1
    if not a.hour.between(0, 23).all():
        raise ValueError("accident hour outside 1..24 after shift")
    out = hourly.copy()
    for col, mask in (("near_accidents", near), ("accidents", accident)):
        counts = a[mask.loc[a.index]].groupby(["day", "hour"]).size()
        out[col] = counts.reindex(out.index).fillna(0).astype(int)
    return out
