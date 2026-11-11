# 10 · UML Diagrams

| | |
|---|---|
| Document | UML set for the SpeedLimit MVP (exercise "class diagram", deck slide 16; "architecture diagram with router", slide 15) |
| Version | 1.0 · 2026-11-11 · reflects branch `build/mvp` |
| Owner | Architecture |
| Check | `tests/unit/test_uml.py` verifies that every type, field and module function named in U02M and U03 exists in the code |
| Images | `figures/U01…U06*.png`, rendered by `analysis/render_uml.py` |

| ID | Diagram | UML type | Answers |
|---|---|---|---|
| U01 | Data model | Class | What do the course files contain and how do they relate? |
| U02 | Router architecture | Component (flowchart notation) | Which parts decide the limit, and how? |
| U02M | Module interfaces | Class (modules as «module») | Which functions does each module offer? |
| U03 | Domain types | Class | Which values flow through a decision? |
| U04 | Decision cycle | Sequence | What happens when an operator changes an input? |
| U05 | Training stage | Activity | How do raw CSVs become a model artefact? |
| U06 | GUI and REQ1 states | State machine | Which modes and REQ1 outcomes exist? |

---

## U01 · Data model (course files, V100)

<!-- U01 -->
```mermaid
classDiagram
    direction LR
    class SensorType {
        +code : string
        +type : string
        +unit : string
        +min : float
        +max : float
    }
    class Sensor {
        +sensorId : int
        +sensorTypeCode : string
    }
    class SensorReading {
        +month : int
        +day : int
        +hour : int 0-23
        +minute : int
        +second : int
        +sensorId : int
        +value : float
    }
    class SpeedLimitReading {
        +sensorId = -1
        +value : km/h 40..80
    }
    class AccidentEvent {
        <<abstract>>
        +month : int
        +day : int
        +hour : int 1-24 hour ending
        +second : int
        +licencePlate : dropped at load D20
    }
    class Accident {
        +damage : EUR
        +injured : int
    }
    class NearAccident {
        +closeCarCm : int
        +closeGuardrailCm : int
        +skidAngle : deg
    }
    class HourlyObservation {
        +day : int
        +hour : int 0-23
        +lux water temp humidity noise
        +wind_strength wind_dir traffic
        +speed_limit : km/h
        +condition : dark / black_ice / normal
        +near_accidents : int target
        +accidents : int reported only
    }
    SensorType "1..2" -- "0..*" Sensor : classifies (code T ambiguous, D2)
    Sensor "1" -- "0..*" SensorReading : produces
    SensorReading <|-- SpeedLimitReading
    AccidentEvent <|-- Accident
    AccidentEvent <|-- NearAccident
    HourlyObservation "1" o-- "1..*" SensorReading : mean per type D4
    HourlyObservation "1" o-- "1" SpeedLimitReading : limit of the hour
    HourlyObservation "1" o-- "0..*" AccidentEvent : hour - 1 (D1)
```

Notes: sensor 19 reports but is not in `Sensors.csv` (mapped to temperature, D3); sensors 7, 10, 17 are documented but silent. `SensorType` code `T` matches two rows, hence the `1..2` multiplicity.

## U02 · Router architecture

<!-- U02 -->
```mermaid
flowchart LR
    subgraph Inputs
        GUI["GUI sliders / replay hour<br/>(app.py)"]
        OM["Open-Meteo forecast<br/>(air_quality)"]
        MAN["Manual EAQI<br/>(D26, D31)"]
    end
    subgraph Core["Decision core (decide.py)"]
        R{"SPEC1 / SPEC2 rules<br/>(rules.evaluate)"}
        NN["REQ1 sweep 40-70<br/>model + monotone guard<br/>(req1_limit, D7 D9 D25 D33)"]
        AQ{"EAQI > 60?<br/>(air_quality.is_poor)"}
        LLM["REQ2 LLM advice<br/>JSON + validation<br/>(llm_advisor.advise)"]
        TAB["AQI table fallback<br/>(table_limit, D15)"]
        MIN[["combine: min of reasons<br/>(D16)"]]
    end
    subgraph Artefacts
        ART[("models/latest.joblib<br/>MLP ensemble")]
        BASE[("baseline_table.json")]
        LOG[("logs/decisions.jsonl<br/>logs/llm_calls.jsonl")]
    end
    GUI --> R
    R -- "dark or black ice" --> NN
    R -- "neither" --> D80["80 km/h (REQ3)"]
    ART --> NN
    BASE -. "no model" .-> NN
    OM --> AQ
    MAN --> TAB
    AQ -- yes --> LLM
    AQ -- "no / unknown" --> N80["80 (REQ2 inactive)"]
    LLM -- "invalid / timeout / refusal" --> TAB
    NN --> MIN
    LLM --> MIN
    TAB --> MIN
    D80 --> MIN
    N80 --> MIN
    MIN --> OUT["Limit + explanation<br/>(GUI)"]
    MIN --> LOG
```

## U02M · Module interfaces

<!-- U02M -->
```mermaid
classDiagram
    direction TB
    class io_load {
        <<module>>
        +load_readings(path) DataFrame
        +load_accidents(path) DataFrame
        +load_sensors(path, types_path) DataFrame
    }
    class cleaning {
        <<module>>
        +resolve_sensor_types(sensors) dict
        +clean_readings(df, sensors, cfg) tuple
        +to_hourly(df) DataFrame
        +join_accidents(hourly, acc) DataFrame
    }
    class features {
        <<module>>
        +build_features(hourly, cfg) DataFrame
        +situation_to_frame(s, limits, cfg) DataFrame
    }
    class rules {
        <<module>>
        +is_dark(lux, cfg) bool
        +is_black_ice(water, temp, cfg) bool
        +evaluate(s, cfg) RuleResult
        +label_conditions(hourly, cfg) DataFrame
    }
    class model {
        <<module>>
        +split_by_day(frame, cfg) tuple
        +train(X, y, cfg) ModelArtefact
        +predict_rate(art, X) ndarray
        +monotone_guard(rates) dict
        +baseline_table(hourly) dict
        +baseline_predict(table, conditions, limits) ndarray
        +evaluate(pred, y, base) dict
        +save(art, path) Path
        +load(path) ModelArtefact
    }
    class decide {
        <<module>>
        +select_limit(guarded, cfg) tuple
        +req1_limit(s, art, cfg, rule, baseline) Req1Result
        +combine(rule, r1, r2) Decision
        +decide(s, ctx) Decision
    }
    class air_quality {
        <<module>>
        +fetch_forecast(lat, lon, cfg) AQForecast
        +summarise(fc, horizon_h) AQSummary
        +table_limit(eu_aqi, cfg) int
        +is_poor(eu_aqi, cfg) bool
    }
    class llm_advisor {
        <<module>>
        +build_prompt(summary) tuple
        +validate(raw, summary, cfg) tuple
        +advise(summary, cfg, client) Req2Result
        +manual_limit(eu_aqi, cfg) Req2Result
    }
    class audit {
        <<module>>
        +log_decision(d, path) None
        +read_log(path, n) DataFrame
    }
    class drift {
        <<module>>
        +drift_report(ref, new, features, cfg) DriftReport
        +verdict(report) str
        +main(argv) int
    }
    class cli_train {
        <<module>>
        +prepare_hourly(cfg, readings_path) tuple
        +main(argv) int
    }
    cli_train ..> io_load
    cli_train ..> cleaning
    cli_train ..> features
    cli_train ..> model
    cli_train ..> rules
    decide ..> rules
    decide ..> features
    decide ..> model
    decide ..> llm_advisor
    llm_advisor ..> air_quality
    drift ..> cli_train
```

## U03 · Domain types

<!-- U03 -->
```mermaid
classDiagram
    direction LR
    class Situation {
        +timestamp : datetime
        +lux : float
        +water_um : float
        +temp_c : float
        +humidity : float
        +noise_db : float
        +wind_strength : float
        +wind_dir_deg : float
        +traffic_cps : float
        +current_limit : int
    }
    class RuleResult {
        +dark : bool
        +black_ice : bool
        +missing_inputs : tuple
        +req1_active() bool
    }
    class Req1Result {
        +active : bool
        +limit : int
        +rates_raw : dict~int,float~
        +rates_guarded : dict~int,float~
        +target_reachable : bool
        +source : model / baseline_table / inactive
        +extrapolated : tuple
    }
    class AQSummary {
        +lat : float
        +lon : float
        +decision_time : datetime
        +horizon_h : int
        +eaqi_max : float
        +eaqi_mean : float
        +eaqi_hourly : list~int~
    }
    class Req2Result {
        +limit : int
        +reason : str
        +source : llm / table / manual / none
        +aq : AQSummary
    }
    class Decision {
        +limit : int
        +winning_reasons : list
        +rule : RuleResult
        +req1 : Req1Result
        +req2 : Req2Result
        +explanation : str
        +model_version : str
        +situation : Situation
        +decided_at : datetime
    }
    class ModelArtefact {
        +estimators : list
        +smearing_k : float
        +features : list
        +version : str
        +baseline_table : dict
        +cell_counts : dict
        +metrics : dict
        +data_hash : str
    }
    class RuntimeContext {
        +cfg : Config
        +art : ModelArtefact
        +baseline : dict
        +aq_summary : AQSummary
        +manual_aqi : float
        +llm_client : object
        +llm_log : Path
    }
    class CleaningReport {
        +events : list
        +silent_sensors : list
    }
    class DriftReport {
        +per_feature : DataFrame
        +retrain : bool
        +reason : str
        +identical_rows : int
        +duplicate_dataset : bool
    }
    Decision *-- RuleResult
    Decision *-- Req1Result
    Decision *-- Req2Result
    Decision o-- Situation
    Req2Result o-- AQSummary
    RuntimeContext o-- ModelArtefact
    RuntimeContext o-- AQSummary
```

## U04 · Decision cycle (operator changes an input)

<!-- U04 -->
```mermaid
sequenceDiagram
    actor Op as Operator
    participant GUI as app.py
    participant Dec as decide.decide
    participant Rules as rules.evaluate
    participant R1 as decide.req1_limit
    participant M as model (MLP ensemble)
    participant Adv as llm_advisor.advise
    participant Claude as Claude API
    participant Log as audit.log_decision
    Op->>GUI: move slider / timer tick
    GUI->>Dec: Situation + RuntimeContext
    Dec->>Rules: SPEC1 / SPEC2
    Rules-->>Dec: RuleResult(dark, black_ice)
    alt dark or black ice
        Dec->>R1: situation, artefact
        R1->>M: predict_rate for 40..80
        M-->>R1: raw rates
        R1->>R1: monotone_guard, select_limit (<= 70, eps)
        R1-->>Dec: Req1Result
    else neither
        R1-->>Dec: inactive (80)
    end
    alt manual EAQI
        Dec->>Adv: manual_limit (table)
    else forecast poor (EAQI > 60)
        Dec->>Adv: AQSummary
        Adv->>Claude: JSON schema request (10 s, fallback on refusal)
        Claude-->>Adv: {speed_limit, reason}
        Adv->>Adv: validate V1-V4, else table
    else good or unknown air
        Adv-->>Dec: 80, source none
    end
    Adv-->>Dec: Req2Result
    Dec->>Dec: combine = min(REQ1, REQ2, 80)
    Dec-->>GUI: Decision + explanation
    GUI->>Log: append if inputs changed
    GUI-->>Op: limit, reason, rate chart
```

## U05 · Training stage

<!-- U05 -->
```mermaid
flowchart TD
    A([python -m speedlimit.cli_train]) --> B[load_readings / load_accidents / load_sensors<br/>BOM, ';', decimal comma, no header, plates dropped]
    B --> C[clean_readings<br/>C04-C16: months, sensor ids, duplicates,<br/>ranges, spikes, sibling-first imputation]
    C --> D[to_hourly<br/>means per type, circular wind, completeness]
    D --> E[join_accidents<br/>hour - 1, near vs accident counts]
    E --> F[label_conditions<br/>dark / black_ice / normal, C17 flag]
    F --> G{complete hour?}
    G -- no --> X[excluded]
    G -- yes --> H[split_by_day<br/>train 1-24, test 25-31]
    H --> I[build_features<br/>12 features, D11]
    I --> J[train: 5-seed MLP ensemble<br/>log1p target + smearing]
    H --> K[baseline_table<br/>mean per condition x limit]
    J --> L[evaluate on test days<br/>MAE, deviance, calibration,<br/>guarded REQ1 outcome]
    K --> L
    L --> M[(model_ver.joblib + latest.joblib<br/>baseline_table.json)]
    L --> N[/model card + metrics.json/]
```

## U06 · GUI and REQ1 states

<!-- U06 -->
```mermaid
stateDiagram-v2
    [*] --> Manual
    Manual --> Replay : mode = Replay
    Replay --> Manual : mode = Manual
    Replay --> Replay : timer tick / Next hour (advance one hour)
    state "Decision for current inputs" as D {
        [*] --> REQ1_inactive : not dark, no ice
        [*] --> REQ1_active : dark or black ice
        REQ1_active --> Target_reached : some limit <= 70 predicted <= 1.0/h
        REQ1_active --> Target_not_reachable : none (highest within eps, flag)
    }
    Manual --> D : input changed
    Replay --> D : hour changed
    D --> Logged : inputs differ from last log entry
    D --> FailSafe : exception (show 60 km/h, D29)
```
