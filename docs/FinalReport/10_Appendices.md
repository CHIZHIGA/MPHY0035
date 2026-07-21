# 10. Appendices

Appendices contain supporting material for the methodology and results. They are not used to replace the main methodological description, but to make the implementation more auditable and reproducible.

## Appendix A: Unified Pipeline Code Structure

The final unified pipeline is implemented under `src/EighthPhase`. Dataset paths, adapters, timezone settings, mappings, pressure overrides, reference-label sources, and co-presence pairs are declared in `src/EighthPhase/config/datasets.json`. Algorithm defaults are defined in `PipelineParameters` and exported to `Results/EighthPhase/pipeline_parameters.json` during each run.

| File | Main role | Main outputs or side effects |
|---|---|---|
| `run_pipeline.py` | Entry point; runs collections, sessions, plotting, reference evaluation, and co-presence analysis | Per-session output folders, cross-dataset summary, capability audit, failure audit |
| `io.py` | Loads RSSI, ACC, step, pressure, metadata, and mapping inputs into the common five-minute grid | Standardised input tables for inference |
| `core.py` | Implements movement clustering, raw RSSI features, sleep/away inference, sleep correction, awake adaptive RSSI, and transition counts | `timeline_5min.csv`, sleep summaries, movement and sleep audits |
| `pressure.py` | Implements optional pressure-floor grouping and conservative same-floor RSSI constraint | Pressure audit fields and pressure-constrained RSSI input |
| `evaluation.py` | Implements post-hoc reference agreement and two-person co-presence analysis | Reference metrics, confusion matrices, co-presence timelines and summaries |
| `plotting.py` | Produces diagnostic figures for timelines, clustering, and confusion matrices | Raw-versus-corrected timelines, clustering figures, reference confusion figures |
| `test_pipeline.py` | Unit tests and regression checks for core pipeline behaviour | Test pass/fail status |

The main command used to run all eligible sessions is:

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=src \
  /home/czg/miniforge3/envs/0249_env/bin/python \
  src/EighthPhase/run_pipeline.py --dataset all
```

The corresponding test command is:

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=src \
  /home/czg/miniforge3/envs/0249_env/bin/python \
  -m unittest EighthPhase.test_pipeline -v
```

## Appendix B: Key Algorithmic Code Extracts

The following extracts are shortened from the implementation. They show the key algorithmic decisions without reproducing the full source code.

### B.1 Core Parameters

```python
@dataclass(frozen=True)
class PipelineParameters:
    window_minutes: int = 5
    min_cluster_fraction: float = 0.05
    min_movement_cluster_windows: int = 20
    movement_silhouette_min: float = 0.25
    near_best_silhouette: float = 0.02
    max_motion_interruption_minutes: int = 15
    min_sleep_candidate_minutes: int = 60
    min_sleep_low_motion_share: float = 0.60
    sleep_silhouette_min: float = 0.50
    sleep_silhouette_borderline_min: float = 0.45
    sleep_borderline_center_ratio: float = 1.50
    room_dominance_share: float = 0.60
    gap_context_minutes: int = 30
    context_room_share: float = 2 / 3
    away_silhouette_min: float = 0.50
    away_silhouette_borderline_min: float = 0.45
    away_min_runs: int = 6
    away_min_per_cluster: int = 2
    away_center_ratio: float = 2.0
```

### B.2 Ordered One-Dimensional Clustering

Movement, sleep-duration, and away-duration models use the same ordered clustering pattern. Candidate KMeans models are fitted, rejected if clusters are too small or poorly separated, and relabelled from lowest to highest centre.

```python
def choose_ordered_clustering(values, candidates, min_count, min_fraction,
                              silhouette_min, near_best,
                              silhouette_borderline_min=None,
                              borderline_min_center_ratio=None):
    clean = values.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    fits = {}
    diagnostics = []
    for k in candidates:
        labels, centers = _ordered_kmeans(clean.to_numpy(), k)
        counts = np.bincount(labels, minlength=k)
        required = max(min_count, int(np.ceil(len(clean) * min_fraction)))
        score = silhouette_score(clean.to_numpy().reshape(-1, 1), labels)
        valid_size = (counts >= required).all()
        strong = score >= silhouette_min
        borderline = (
            silhouette_borderline_min is not None
            and silhouette_borderline_min <= score < silhouette_min
            and minimum_center_ratio >= borderline_min_center_ratio
        )
        if valid_size and (strong or borderline):
            fits[k] = (labels, centers, score)
    if not fits:
        return unresolved_states, None, diagnostics
    best_score = max(item[2] for item in fits.values())
    selected_k = min(k for k, item in fits.items()
                     if item[2] >= best_score - near_best)
    return ordered_states, ordered_centers, diagnostics
```

### B.3 Movement Classification

ACC uses the logarithm of the clipped movement feature, while step count uses `log1p`. Only the lowest ordered state is treated as low motion.

```python
def classify_movement(feature, source, params):
    if source == "acc":
        transformed = np.log(feature.clip(lower=1e-6))
    else:
        transformed = np.log1p(feature.clip(lower=0))

    states, centers, diagnostics = choose_ordered_clustering(
        transformed,
        candidates=(2, 3, 4),
        min_count=params.min_movement_cluster_windows,
        min_fraction=params.min_cluster_fraction,
        silhouette_min=params.movement_silhouette_min,
        near_best=params.near_best_silhouette,
    )

    boundary = (centers[0] + centers[1]) / 2
    threshold = np.exp(boundary) if source == "acc" else np.expm1(boundary)
    low_motion = states.eq(1)
```

### B.4 Main-Sleep Identification

Low-motion windows are joined across short interruptions, filtered by duration and low-motion share, and then clustered by log duration. The longest accepted duration cluster becomes main sleep.

```python
def build_sleep_candidates(movement, params):
    low_times = movement.index[movement["low_motion"].fillna(False)]
    max_separation = pd.Timedelta(
        minutes=params.max_motion_interruption_minutes + params.window_minutes
    )
    runs = join_low_motion_windows(low_times, max_separation)
    for start, end in runs:
        segment = movement.loc[(movement.index >= start) & (movement.index < end)]
        duration = (end - start).total_seconds() / 60
        share = segment["low_motion"].mean()
        if duration >= params.min_sleep_candidate_minutes and share >= 0.60:
            keep_as_sleep_candidate(start, end, duration, share)

def select_main_sleep(candidates, params):
    log_duration = np.log(candidates["duration_minutes"])
    states, centers, diagnostics = choose_ordered_clustering(
        log_duration,
        candidates=(2, 3),
        min_count=2,
        min_fraction=0,
        silhouette_min=params.sleep_silhouette_min,
        silhouette_borderline_min=params.sleep_silhouette_borderline_min,
        borderline_min_center_ratio=params.sleep_borderline_center_ratio,
    )
    candidates["main_sleep"] = states.eq(len(centers))
```

### B.5 Sleep-Room Correction and Gap Filling

Observed sleep windows are locked to the episode-dominant room only when the dominance rule passes. Missing sleep gaps are filled only with two-sided 30-minute room support.

```python
def apply_sleep_correction(timeline, episodes, params):
    for episode in episodes.loc[episodes["main_sleep"]].itertuples():
        mask = (timeline.index >= episode.start) & (timeline.index < episode.end)
        if not episode.room_correction_eligible:
            continue

        observed = mask & timeline["base_beacon"].notna()
        timeline.loc[observed, "corrected_beacon"] = episode.dominant_beacon
        timeline.loc[observed, "corrected_room"] = episode.dominant_room

        missing = mask & timeline["base_beacon"].isna()
        for start, end in contiguous_missing_runs(missing):
            before = preceding_30_minutes(start, episode)
            after = following_30_minutes(end, episode)
            supported = (
                before.contains_observation
                and after.contains_observation
                and before.share(episode.dominant_beacon) >= 2 / 3
                and after.share(episode.dominant_beacon) >= 2 / 3
            )
            if supported:
                fill_gap_with_episode_room(start, end)
```

### B.6 Awake Adaptive RSSI

Awake adaptive RSSI uses trailing windows and does not cross evidence boundaries.

```python
WINDOWS_BY_K = {
    2: [30, 5],
    3: [30, 10, 5],
    4: [30, 15, 10, 5],
}

def apply_awake_adaptive_rssi(timeline, rssi_mean):
    k = selected_movement_k(timeline)
    windows = WINDOWS_BY_K[k]
    for timestamp, row in timeline.iterrows():
        if row.main_sleep or row.occupancy_state != "indoor_observed":
            continue
        if not row.rssi_observed:
            continue
        window_minutes = windows[int(row.movement_state) - 1]
        segment = trailing_segment(timestamp, window_minutes)
        segment = trim_at_boundaries(
            segment,
            missing_rssi=True,
            sleep=True,
            away=True,
            higher_movement=True,
            trusted_pressure_floor_change=True,
        )
        winner = rssi_mean.loc[segment.index].mean(axis=0).idxmax()
        update_corrected_room(timestamp, winner)
```

### B.7 Pressure Constraint

Pressure is a conservative floor constraint. It can remain inactive through the K=1 null model.

```python
PRESSURE_MIN_FLOOR_SEPARATION_HPA = 0.30
PRESSURE_MIN_GROUP_SILHOUETTE = 0.75
PRESSURE_MIN_BEACONS_PER_GROUP = 2
PRESSURE_MIN_OVERLAP_WINDOWS = 100

def constrain_rssi_with_pressure(rssi_mean, environmental_pressure,
                                 wearable_pressure, movement_state=None,
                                 floor_override=None):
    groups, audit = auto_or_configured_pressure_groups(environmental_pressure)
    if len(set(groups.values())) < 2:
        return rssi_mean.copy(), inactive_pressure_info, audit

    group_pressure = median_pressure_by_group(environmental_pressure, groups)
    offset = calibrate_wearable_to_environmental_pressure(
        wearable_pressure, group_pressure, raw_rssi_winner
    )
    inferred_floor, confidence = nearest_pressure_group(
        wearable_pressure - offset, group_pressure
    )
    trusted = confidence.ge(0.75) & movement_supported_floor_changes
    constrained = remove_beacons_from_other_floors(rssi_mean, inferred_floor, trusted)
    return constrained, pressure_info, audit
```

### B.8 Reference Agreement and Co-Presence

Reference labels and co-presence are evaluated after individual timelines have already been generated.

```python
def evaluate_reference(timeline, spec):
    reference = align_reference(load_reference(spec), timeline)
    raw = timeline["raw_room"]
    corrected = timeline["corrected_room"]
    corrected = corrected.mask(
        timeline["occupancy_state"].isin(["probable_away", "confirmed_away"]),
        "Out",
    )
    return metrics_for(raw), metrics_for(corrected), confusion_matrices

def analyse_copresence(left, right):
    merged = left.add_prefix("left_").join(right.add_prefix("right_"), how="inner")
    corrected_copresent = (
        left_and_right_have_known_corrected_rooms
        and both_are_indoor
        and corrected_rooms_match
    )
    return timeline, stratified_same_room_metrics
```

## Appendix C: Replication-Critical Parameters

| Pipeline step | Parameter | Value |
|---|---|---:|
| Canonical timeline | Window length | 5 min |
| ACC movement | Minimum ACC samples per window | 10 |
| Movement clustering | Candidate K | 2, 3, 4 |
| Movement clustering | Minimum silhouette | 0.25 |
| Movement clustering | Minimum cluster size | 5% and 20 windows |
| Movement clustering | Near-best tolerance | 0.02 silhouette |
| Awake adaptive RSSI | K=2 windows | 30, 5 min |
| Awake adaptive RSSI | K=3 windows | 30, 10, 5 min |
| Awake adaptive RSSI | K=4 windows | 30, 15, 10, 5 min |
| Step fallback | Maximum equal-count reconstruction gap | 35 min |
| Sleep candidates | Maximum interruption | 15 min |
| Sleep candidates | Minimum duration | 60 min |
| Sleep candidates | Minimum low-motion share | 60% |
| Sleep duration clustering | Candidate K | 2, 3 |
| Sleep duration clustering | Strong silhouette | >= 0.50 |
| Sleep duration clustering | Borderline silhouette | 0.45 to < 0.50 |
| Sleep duration clustering | Borderline centre ratio | >= 1.5 |
| Sleep-room evidence | Dominant room share | >= 60% |
| Sleep-gap filling | Context window | 30 min before and after |
| Sleep-gap filling | Context room support | >= 2/3 on both sides |
| Away inference | Minimum candidate gaps | 6 |
| Away inference | Minimum gaps per class | 2 |
| Away inference | Long/short duration ratio | >= 2.0 |
| Pressure grouping | Minimum overlap | 100 windows |
| Pressure grouping | Minimum beacons per group | 2 |
| Pressure grouping | Minimum floor separation | 0.30 hPa |
| Pressure grouping | Minimum silhouette | 0.75 |
| Pressure constraint | Trusted floor confidence | >= 0.75 |

## Appendix D: Additional Figures

Additional figures should be placed here when they support the main report but are too detailed for Chapter 5. Candidate figure types include per-session raw-versus-corrected timelines, movement and sleep clustering diagnostics, supplementary co-presence timelines, additional confusion matrices, and pressure-audit figures.

## Appendix E: Validation Checks

The pipeline was checked using both automated and manual validation. Key checks include:

- input files and metadata mappings are present before processing;
- output CSV files are non-empty;
- timestamp ranges match expected recording periods;
- all session outputs use the five-minute UTC grid;
- local time is retained for sleep interpretation;
- Home_X001 and Home_A002 co-presence analyses use only overlapping participant timelines;
- no-reference datasets are not described using reference-label accuracy language;
- labelled metrics are calculated only after prediction timelines are generated;
- `Probable away` is reported separately from indoor room correction;
- pressure-floor grouping can select K=1 and remain inactive;
- pressure-constrained RSSI is checked against beacon floor grouping;
- sleep-location and stair-related outputs are described as candidates unless independently verified;
- room-transition rates are interpreted alongside coverage and correction provenance.

## Appendix F: AI-Assisted Coding and Verification

AI-assisted coding tools supported planning, code drafting, debugging, refactoring, figure planning, documentation structure, and report organisation. They were used as development aids rather than as sources of scientific conclusions.

Generated or modified code was checked against the project data structure and validated through row counts, timestamp ranges, non-empty output files, audit CSVs, figure inspection, reference-metric checks, and comparison with expected metadata. Scientific interpretation and final report responsibility remained with the student.

Practical verification examples include:

- confirming `cross_dataset_summary.csv` matched the reported session totals;
- checking that each figure path used in the report exists;
- confirming that reference labels are loaded only after prediction;
- inspecting pressure audit fields when pressure remained inactive;
- comparing raw and corrected timelines before interpreting transition changes.
