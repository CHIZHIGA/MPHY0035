"""Sensor-independent inference on a canonical five-minute timeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


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


WINDOWS_BY_K = {
    2: [30, 5],
    3: [30, 10, 5],
    4: [30, 15, 10, 5],
}


def normalise_location(value: object) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    if not text:
        return "Unknown"
    lowered = text.lower()
    aliases = {
        "out": "Out",
        "outside": "Out",
        "away": "Out",
        "living room": "Living",
        "bed room": "Bedroom",
    }
    if lowered in aliases:
        return aliases[lowered]
    for room in ("Bedroom", "Living", "Dining", "Kitchen", "Bathroom", "Toilet", "Office"):
        if room.lower() in lowered:
            return room
    if lowered in {"?", "unknown", "nan", "none", "unmapped"}:
        return "Unknown"
    return text[:1].upper() + text[1:]


def _ordered_kmeans(values: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    model = KMeans(n_clusters=k, n_init=20, random_state=42)
    labels = model.fit_predict(values.reshape(-1, 1))
    centers = model.cluster_centers_.ravel()
    order = np.argsort(centers)
    remap = np.empty(k, dtype=int)
    remap[order] = np.arange(k)
    return remap[labels], centers[order]


def choose_ordered_clustering(
    values: pd.Series,
    candidates: Iterable[int],
    min_count: int,
    min_fraction: float,
    silhouette_min: float,
    near_best: float,
    silhouette_borderline_min: float | None = None,
    borderline_min_center_ratio: float | None = None,
) -> tuple[pd.Series, np.ndarray | None, pd.DataFrame]:
    """Choose a small, ordered 1-D KMeans model without using labels."""
    clean = values.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    diagnostics = []
    fits: dict[int, tuple[np.ndarray, np.ndarray, float]] = {}
    for k in candidates:
        if len(clean) <= k:
            continue
        if clean.nunique() < k:
            diagnostics.append(
                {
                    "k": k,
                    "silhouette": np.nan,
                    "minimum_cluster_count": 0,
                    "required_cluster_count": max(min_count, int(np.ceil(len(clean) * min_fraction))),
                    "accepted": False,
                    "centers_transformed": "",
                }
            )
            continue
        labels, centers = _ordered_kmeans(clean.to_numpy(), k)
        counts = np.bincount(labels, minlength=k)
        required = max(min_count, int(np.ceil(len(clean) * min_fraction)))
        valid_size = bool((counts >= required).all())
        score = float(silhouette_score(clean.to_numpy().reshape(-1, 1), labels))
        minimum_center_ratio = (
            float(np.exp(np.diff(centers)).min()) if len(centers) > 1 else np.inf
        )
        strong = score >= silhouette_min
        borderline = bool(
            silhouette_borderline_min is not None
            and borderline_min_center_ratio is not None
            and silhouette_borderline_min <= score < silhouette_min
            and minimum_center_ratio >= borderline_min_center_ratio
        )
        accepted = valid_size and (strong or borderline)
        separation_tier = (
            "strong"
            if valid_size and strong
            else "borderline"
            if valid_size and borderline
            else "rejected"
        )
        diagnostics.append(
            {
                "k": k,
                "silhouette": score,
                "minimum_cluster_count": int(counts.min()),
                "required_cluster_count": required,
                "accepted": accepted,
                "separation_tier": separation_tier,
                "minimum_center_ratio": minimum_center_ratio,
                "centers_transformed": "|".join(f"{item:.8g}" for item in centers),
            }
        )
        if accepted:
            fits[k] = (labels, centers, score)
    diagnostic_frame = pd.DataFrame(diagnostics)
    output = pd.Series(pd.NA, index=values.index, dtype="Int64")
    if not fits:
        return output, None, diagnostic_frame
    best_score = max(item[2] for item in fits.values())
    selected_k = min(k for k, item in fits.items() if item[2] >= best_score - near_best)
    labels, centers, _ = fits[selected_k]
    output.loc[clean.index] = labels + 1
    if not diagnostic_frame.empty:
        diagnostic_frame["selected"] = diagnostic_frame["k"].eq(selected_k)
    return output, centers, diagnostic_frame


def classify_movement(
    feature: pd.Series,
    source: str,
    params: PipelineParameters,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    transformed = np.log(feature.clip(lower=1e-6)) if source == "acc" else np.log1p(feature.clip(lower=0))
    states, centers, diagnostics = choose_ordered_clustering(
        transformed,
        candidates=(2, 3, 4),
        min_count=params.min_movement_cluster_windows,
        min_fraction=params.min_cluster_fraction,
        silhouette_min=params.movement_silhouette_min,
        near_best=params.near_best_silhouette,
    )
    result = pd.DataFrame(index=feature.index)
    result["movement_source"] = source
    result["movement_value"] = feature
    result["movement_state"] = states
    result["movement_k"] = len(centers) if centers is not None else pd.NA
    result["movement_resolved"] = centers is not None
    if centers is None:
        result["low_motion"] = False
        result["low_motion_threshold"] = np.nan
        audit = {"movement_source": source, "movement_k": None, "low_motion_threshold": None}
        return result, diagnostics, audit
    boundary_transformed = float((centers[0] + centers[1]) / 2)
    threshold = float(np.exp(boundary_transformed)) if source == "acc" else float(np.expm1(boundary_transformed))
    result["low_motion"] = result["movement_state"].eq(1)
    result["low_motion_threshold"] = threshold
    audit = {
        "movement_source": source,
        "movement_k": len(centers),
        "low_motion_threshold": threshold,
        "movement_centers": "|".join(f"{item:.8g}" for item in centers),
    }
    return result, diagnostics, audit


def build_raw_rssi_features(
    rssi_mean: pd.DataFrame,
    rssi_count: pd.DataFrame,
    beacon_to_room: dict[str, str],
) -> pd.DataFrame:
    result = pd.DataFrame(index=rssi_mean.index)
    result["rssi_sample_count"] = rssi_count.sum(axis=1).reindex(result.index).fillna(0).astype(int)
    result["rssi_available_beacons"] = rssi_mean.notna().sum(axis=1)
    result["rssi_observed"] = result["rssi_available_beacons"].gt(0)
    result["raw_strongest_beacon"] = rssi_mean.apply(
        lambda row: row.idxmax() if row.notna().any() else pd.NA,
        axis=1,
    )
    result["raw_strongest_rssi"] = rssi_mean.max(axis=1).where(result["rssi_observed"])
    second = np.full(len(result), np.nan)
    for index, row in enumerate(rssi_mean.to_numpy(dtype=float)):
        finite = np.sort(row[np.isfinite(row)])
        if len(finite) >= 2:
            second[index] = finite[-2]
    result["raw_second_rssi"] = second
    result["raw_strongest_second_gap_db"] = result["raw_strongest_rssi"] - result["raw_second_rssi"]
    result["raw_room"] = result["raw_strongest_beacon"].map(beacon_to_room).fillna("Unknown")
    result.loc[~result["rssi_observed"], "raw_room"] = pd.NA
    return result


def _boolean_runs(mask: pd.Series, window_minutes: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    runs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = previous = None
    step = pd.Timedelta(minutes=window_minutes)
    for timestamp, active in mask.items():
        if bool(active):
            if start is None or previous is None or timestamp - previous != step:
                if start is not None and previous is not None:
                    runs.append((start, previous + step))
                start = timestamp
            previous = timestamp
        elif start is not None and previous is not None:
            runs.append((start, previous + step))
            start = previous = None
    if start is not None and previous is not None:
        runs.append((start, previous + step))
    return runs


def build_sleep_candidates(movement: pd.DataFrame, params: PipelineParameters) -> pd.DataFrame:
    low_times = movement.index[movement["low_motion"].fillna(False)]
    if len(low_times) == 0:
        return pd.DataFrame(columns=["candidate_id", "start", "end", "duration_minutes", "low_motion_share"])
    max_separation = pd.Timedelta(minutes=params.max_motion_interruption_minutes + params.window_minutes)
    bounds = []
    start = previous = low_times[0]
    for timestamp in low_times[1:]:
        if timestamp - previous > max_separation:
            bounds.append((start, previous + pd.Timedelta(minutes=params.window_minutes)))
            start = timestamp
        previous = timestamp
    bounds.append((start, previous + pd.Timedelta(minutes=params.window_minutes)))
    rows = []
    for start, end in bounds:
        segment = movement.loc[(movement.index >= start) & (movement.index < end)]
        duration = (end - start).total_seconds() / 60
        share = float(segment["low_motion"].mean()) if len(segment) else 0.0
        if duration >= params.min_sleep_candidate_minutes and share >= params.min_sleep_low_motion_share:
            rows.append(
                {
                    "candidate_id": len(rows) + 1,
                    "start": start,
                    "end": end,
                    "duration_minutes": duration,
                    "low_motion_share": share,
                }
            )
    return pd.DataFrame(rows)


def select_main_sleep(
    candidates: pd.DataFrame, params: PipelineParameters
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    updated = candidates.copy()
    if updated.empty:
        updated["duration_cluster"] = pd.Series(dtype="Int64")
        updated["main_sleep"] = pd.Series(dtype=bool)
        return updated, pd.DataFrame(), {"sleep_resolved": False, "main_sleep_episode_count": 0}
    log_duration = pd.Series(np.log(updated["duration_minutes"].to_numpy()), index=updated.index)
    states, centers, diagnostics = choose_ordered_clustering(
        log_duration,
        candidates=(2, 3),
        min_count=2,
        min_fraction=0,
        silhouette_min=params.sleep_silhouette_min,
        near_best=params.near_best_silhouette,
        silhouette_borderline_min=params.sleep_silhouette_borderline_min,
        borderline_min_center_ratio=params.sleep_borderline_center_ratio,
    )
    updated["duration_cluster"] = states
    if centers is None:
        updated["main_sleep"] = False
        return updated, diagnostics, {"sleep_resolved": False, "main_sleep_episode_count": 0}
    updated["main_sleep"] = updated["duration_cluster"].eq(len(centers))
    audit = {
        "sleep_resolved": True,
        "sleep_duration_k": len(centers),
        "sleep_duration_centers_minutes": "|".join(f"{np.exp(item):.4g}" for item in centers),
        "main_sleep_episode_count": int(updated["main_sleep"].sum()),
        "sleep_separation_tier": diagnostics.loc[diagnostics["selected"], "separation_tier"].iloc[0],
    }
    return updated, diagnostics, audit


def add_episode_room_evidence(
    episodes: pd.DataFrame,
    timeline: pd.DataFrame,
    params: PipelineParameters,
) -> pd.DataFrame:
    updated = episodes.copy()
    for column in ("dominant_beacon", "dominant_room"):
        updated[column] = pd.NA
    updated["dominant_count"] = 0
    updated["observed_windows"] = 0
    updated["dominant_share"] = np.nan
    for index, episode in updated.iterrows():
        segment = timeline.loc[(timeline.index >= episode["start"]) & (timeline.index < episode["end"])]
        counts = segment["base_beacon"].dropna().value_counts()
        if counts.empty:
            continue
        winner = str(counts.index[0])
        observed = int(counts.sum())
        updated.loc[index, "dominant_beacon"] = winner
        updated.loc[index, "dominant_room"] = segment.loc[segment["base_beacon"].eq(winner), "base_room"].iloc[0]
        updated.loc[index, "dominant_count"] = int(counts.iloc[0])
        updated.loc[index, "observed_windows"] = observed
        updated.loc[index, "dominant_share"] = float(counts.iloc[0] / observed)
    updated["room_supported"] = updated["dominant_share"].ge(params.room_dominance_share)
    return updated


def infer_bedroom(
    episodes: pd.DataFrame,
    known_bedroom_beacons: set[str],
    local_timezone: str,
) -> dict[str, object]:
    if known_bedroom_beacons:
        return {
            "bedroom_source": "metadata",
            "bedroom_beacons": "|".join(sorted(known_bedroom_beacons)),
            "bedroom_inferred": False,
        }
    supported = episodes.loc[episodes.get("main_sleep", False) & episodes.get("room_supported", False)].copy()
    if supported.empty:
        return {"bedroom_source": "unresolved", "bedroom_beacons": "", "bedroom_inferred": False}
    supported["night"] = supported["start"].dt.tz_convert(local_timezone).dt.date
    rows = []
    for beacon, group in supported.groupby("dominant_beacon"):
        nights = group["night"].nunique()
        total = group["observed_windows"].sum()
        dominant = group["dominant_count"].sum()
        rows.append((str(beacon), int(nights), float(dominant / total) if total else 0.0, int(total)))
    eligible = [item for item in rows if item[1] >= 2 and item[2] >= 0.60]
    if not eligible:
        return {"bedroom_source": "unresolved", "bedroom_beacons": "", "bedroom_inferred": False}
    winner = sorted(eligible, key=lambda item: (item[1], item[3], item[2]), reverse=True)[0]
    return {
        "bedroom_source": "inferred_cross_night",
        "bedroom_beacons": winner[0],
        "bedroom_inferred": True,
        "bedroom_support_nights": winner[1],
        "bedroom_support_share": winner[2],
    }


def classify_away_runs(
    timeline: pd.DataFrame,
    params: PipelineParameters,
) -> tuple[pd.Series, pd.DataFrame, dict[str, object]]:
    eligible = (~timeline["rssi_observed"]) & timeline["wearable_online"].fillna(False) & ~timeline["main_sleep"]
    runs = _boolean_runs(eligible, params.window_minutes)
    output = pd.Series(False, index=timeline.index, dtype=bool)
    rows = [
        {"run_id": i + 1, "start": start, "end": end, "duration_minutes": (end - start).total_seconds() / 60}
        for i, (start, end) in enumerate(runs)
    ]
    table = pd.DataFrame(rows)
    if len(table) < params.away_min_runs:
        return output, table, {"away_resolved": False, "away_run_count": len(table)}
    transformed = pd.Series(np.log(table["duration_minutes"].to_numpy()), index=table.index)
    states, centers, diagnostics = choose_ordered_clustering(
        transformed,
        candidates=(2,),
        min_count=params.away_min_per_cluster,
        min_fraction=0,
        silhouette_min=params.away_silhouette_min,
        near_best=0,
        silhouette_borderline_min=params.away_silhouette_borderline_min,
        borderline_min_center_ratio=params.away_center_ratio,
    )
    table["duration_cluster"] = states
    resolved = centers is not None and np.exp(centers[1]) >= params.away_center_ratio * np.exp(centers[0])
    table["probable_away"] = resolved & table["duration_cluster"].eq(2)
    if resolved:
        for run in table.loc[table["probable_away"]].itertuples(index=False):
            output.loc[(output.index >= run.start) & (output.index < run.end)] = True
    if not diagnostics.empty:
        table.attrs["clustering_diagnostics"] = diagnostics
    audit = {
        "away_resolved": bool(resolved),
        "away_run_count": len(table),
        "probable_away_run_count": int(table["probable_away"].sum()),
        "away_centers_minutes": "|".join(f"{np.exp(item):.4g}" for item in centers) if centers is not None else "",
        "away_separation_tier": (
            diagnostics.loc[diagnostics["selected"], "separation_tier"].iloc[0]
            if centers is not None and "selected" in diagnostics
            else "unresolved"
        ),
    }
    return output, table, audit


def _dominant_context(values: pd.Series, target: str) -> tuple[int, float]:
    observed = values.dropna()
    if observed.empty:
        return 0, np.nan
    return len(observed), float(observed.eq(target).mean())


def apply_sleep_correction(
    timeline: pd.DataFrame,
    episodes: pd.DataFrame,
    params: PipelineParameters,
) -> pd.DataFrame:
    updated = timeline.copy()
    for episode in episodes.loc[episodes["main_sleep"]].itertuples(index=False):
        mask = (updated.index >= episode.start) & (updated.index < episode.end)
        updated.loc[mask, "sleep_episode_id"] = int(episode.candidate_id)
        updated.loc[mask, "main_sleep"] = True
        correction_eligible = bool(getattr(episode, "room_correction_eligible", episode.room_supported))
        if not correction_eligible or pd.isna(episode.dominant_beacon):
            continue
        observed_mask = mask & updated["base_beacon"].notna()
        updated.loc[observed_mask, "corrected_beacon"] = episode.dominant_beacon
        updated.loc[observed_mask, "corrected_room"] = episode.dominant_room
        changed = observed_mask & updated["base_beacon"].ne(episode.dominant_beacon)
        updated.loc[changed, "correction_reason"] = "sleep_episode_dominant_room"
        updated.loc[observed_mask, "location_evidence"] = "sleep_episode_locked"

        missing = mask & updated["base_beacon"].isna()
        for start, end in _boolean_runs(missing, params.window_minutes):
            context = pd.Timedelta(minutes=params.gap_context_minutes)
            before = updated.loc[(updated.index >= max(start - context, episode.start)) & (updated.index < start), "base_beacon"]
            after = updated.loc[(updated.index >= end) & (updated.index < min(end + context, episode.end)), "base_beacon"]
            before_n, before_share = _dominant_context(before, str(episode.dominant_beacon))
            after_n, after_share = _dominant_context(after, str(episode.dominant_beacon))
            supported = (
                before_n >= 1
                and after_n >= 1
                and before_share >= params.context_room_share
                and after_share >= params.context_room_share
            )
            gap_mask = (updated.index >= start) & (updated.index < end)
            if supported:
                updated.loc[gap_mask, "corrected_beacon"] = episode.dominant_beacon
                updated.loc[gap_mask, "corrected_room"] = episode.dominant_room
                updated.loc[gap_mask, "correction_reason"] = "sleep_gap_two_sided_room_support"
                updated.loc[gap_mask, "location_evidence"] = "sleep_gap_context_filled"
                updated.loc[gap_mask, "sleep_gap_filled"] = True
    return updated


def apply_awake_adaptive_rssi(
    timeline: pd.DataFrame,
    rssi_mean: pd.DataFrame,
) -> pd.DataFrame:
    updated = timeline.copy()
    if not updated["movement_resolved"].any():
        return updated
    k = int(updated.loc[updated["movement_resolved"], "movement_k"].iloc[0])
    windows = WINDOWS_BY_K[k]
    step = pd.Timedelta(minutes=5)
    for position, timestamp in enumerate(updated.index):
        row = updated.iloc[position]
        if bool(row["main_sleep"]) or row["occupancy_state"] != "indoor_observed" or not bool(row["rssi_observed"]):
            continue
        if pd.isna(row["movement_state"]):
            continue
        state = int(row["movement_state"])
        window_minutes = windows[state - 1]
        start = timestamp - pd.Timedelta(minutes=window_minutes - 5)
        segment = updated.loc[(updated.index >= start) & (updated.index <= timestamp)]
        if segment.empty:
            continue
        # Boundaries: discontinuity, missing RSSI, state branch, floor group, or a higher movement state.
        reset_positions = []
        times = segment.index.to_series()
        reset_positions.extend(np.flatnonzero(times.diff().gt(step).to_numpy()))
        reset_positions.extend(np.flatnonzero((~segment["rssi_observed"]).to_numpy()))
        reset_positions.extend(np.flatnonzero(segment["main_sleep"].to_numpy()))
        reset_positions.extend(np.flatnonzero(segment["occupancy_state"].ne("indoor_observed").to_numpy()))
        reset_positions.extend(np.flatnonzero(segment["movement_state"].fillna(k + 1).gt(state).to_numpy()))
        if "pressure_floor_group" in segment and pd.notna(row.get("pressure_floor_group")):
            reset_positions.extend(np.flatnonzero(segment["pressure_floor_group"].notna().to_numpy() & segment["pressure_floor_group"].ne(row.get("pressure_floor_group")).to_numpy()))
        if reset_positions:
            segment = segment.iloc[max(reset_positions) + 1 :]
        if segment.empty or timestamp not in segment.index:
            continue
        means = rssi_mean.reindex(segment.index).mean(axis=0, skipna=True).dropna()
        if means.empty:
            continue
        winner = str(means.sort_values(ascending=False, kind="stable").index[0])
        updated.at[timestamp, "corrected_beacon"] = winner
        updated.at[timestamp, "corrected_room"] = updated.at[timestamp, "beacon_to_room"].get(winner, "Unknown")
        updated.at[timestamp, "adaptive_window_minutes"] = window_minutes
        updated.at[timestamp, "location_evidence"] = "awake_adaptive"
        if winner != row["base_beacon"]:
            updated.at[timestamp, "correction_reason"] = "awake_movement_adaptive_rssi"
    return updated


def count_transitions(values: pd.Series) -> int:
    observed = values.dropna()
    if len(observed) < 2:
        return 0
    contiguous = observed.index.to_series().diff().eq(pd.Timedelta(minutes=5))
    return int((observed.ne(observed.shift()) & contiguous).sum())


def run_inference(
    rssi_mean: pd.DataFrame,
    rssi_count: pd.DataFrame,
    movement_feature: pd.Series | None,
    movement_source: str | None,
    wearable_online: pd.Series,
    beacon_to_room: dict[str, str],
    local_timezone: str,
    params: PipelineParameters | None = None,
    base_rssi_mean: pd.DataFrame | None = None,
    context_features: pd.DataFrame | None = None,
) -> dict[str, object]:
    params = params or PipelineParameters()
    beacon_to_room = {str(key): normalise_location(value) for key, value in beacon_to_room.items()}
    raw = build_raw_rssi_features(rssi_mean, rssi_count, beacon_to_room)
    base_rssi_mean = rssi_mean if base_rssi_mean is None else base_rssi_mean.reindex_like(rssi_mean)
    base_features = build_raw_rssi_features(base_rssi_mean, rssi_count, beacon_to_room)
    timeline = raw.copy()
    timeline["base_beacon"] = base_features["raw_strongest_beacon"]
    timeline["base_room"] = base_features["raw_room"]
    timeline["pressure_constrained"] = timeline["base_beacon"].fillna("").ne(timeline["raw_strongest_beacon"].fillna(""))
    timeline["beacon_to_room"] = [beacon_to_room] * len(timeline)
    timeline["wearable_online"] = wearable_online.reindex(timeline.index).fillna(False).astype(bool)

    if movement_feature is None or movement_source is None or movement_feature.dropna().empty:
        movement = pd.DataFrame(index=timeline.index)
        movement["movement_source"] = "unresolved"
        movement["movement_value"] = np.nan
        movement["movement_state"] = pd.Series(pd.NA, index=timeline.index, dtype="Int64")
        movement["movement_k"] = pd.NA
        movement["movement_resolved"] = False
        movement["low_motion"] = False
        movement["low_motion_threshold"] = np.nan
        movement_diagnostics = pd.DataFrame()
        movement_audit = {"movement_source": "unresolved", "movement_k": None}
    else:
        movement, movement_diagnostics, movement_audit = classify_movement(
            movement_feature.reindex(timeline.index), movement_source, params
        )
    timeline = timeline.join(movement)
    if context_features is not None and not context_features.empty:
        timeline = timeline.join(context_features.reindex(timeline.index))
    candidates = build_sleep_candidates(movement, params)
    episodes, sleep_diagnostics, sleep_audit = select_main_sleep(candidates, params)
    timeline["sleep_candidate"] = False
    timeline["main_sleep"] = False
    timeline["sleep_episode_id"] = pd.Series(pd.NA, index=timeline.index, dtype="Int64")
    for episode in episodes.itertuples(index=False):
        mask = (timeline.index >= episode.start) & (timeline.index < episode.end)
        timeline.loc[mask, "sleep_candidate"] = True
    timeline["corrected_beacon"] = timeline["base_beacon"]
    timeline["corrected_room"] = timeline["base_room"]
    timeline["correction_reason"] = "none"
    timeline["location_evidence"] = np.where(timeline["rssi_observed"], "observed_raw", "missing")
    timeline["sleep_gap_filled"] = False
    timeline["adaptive_window_minutes"] = np.nan

    episodes = add_episode_room_evidence(episodes, timeline, params)
    known_bedrooms = {beacon for beacon, room in beacon_to_room.items() if room == "Bedroom"}
    bedroom_audit = infer_bedroom(episodes, known_bedrooms, local_timezone)
    if bedroom_audit.get("bedroom_inferred"):
        inferred = str(bedroom_audit["bedroom_beacons"])
        beacon_to_room[inferred] = "Bedroom"
        episodes.loc[episodes["dominant_beacon"].eq(inferred), "dominant_room"] = "Bedroom"
        timeline.loc[timeline["base_beacon"].eq(inferred), "base_room"] = "Bedroom"
    episodes["room_correction_eligible"] = episodes["room_supported"].fillna(False)
    if movement_source == "step":
        # Zero steps indicate absence of locomotion, not necessarily sleep or
        # a stable non-Bedroom room.  Step-derived episodes may stabilise/fill
        # spatial output only when their dominant room is Bedroom.
        episodes["room_correction_eligible"] &= episodes["dominant_room"].eq("Bedroom")
    timeline = apply_sleep_correction(timeline, episodes, params)
    probable_away, away_runs, away_audit = classify_away_runs(timeline, params)

    timeline["occupancy_state"] = "unknown"
    timeline.loc[timeline["rssi_observed"], "occupancy_state"] = "indoor_observed"
    timeline.loc[probable_away, "occupancy_state"] = "probable_away"
    timeline.loc[timeline["sleep_gap_filled"], "occupancy_state"] = "indoor_inferred_sleep"
    timeline["behaviour_state"] = "awake"
    unresolved_candidate = timeline["sleep_candidate"] & ~timeline["main_sleep"] & ~bool(sleep_audit["sleep_resolved"])
    timeline.loc[unresolved_candidate, "behaviour_state"] = "sleep_unresolved"
    timeline.loc[timeline["main_sleep"], "behaviour_state"] = "main_sleep"
    timeline.loc[timeline["occupancy_state"].eq("probable_away"), "behaviour_state"] = "away"
    if not timeline["movement_resolved"].any():
        timeline.loc[timeline["behaviour_state"].eq("awake"), "behaviour_state"] = "movement_unresolved"

    timeline = apply_awake_adaptive_rssi(timeline, base_rssi_mean)
    # Awake missing remains missing, regardless of historical RSSI.
    awake_missing = timeline["behaviour_state"].isin(["awake", "movement_unresolved"]) & ~timeline["rssi_observed"]
    timeline.loc[awake_missing, ["corrected_beacon", "corrected_room"]] = pd.NA
    timeline["was_corrected"] = timeline["corrected_beacon"].fillna("").ne(timeline["raw_strongest_beacon"].fillna(""))
    timeline["location_confidence"] = timeline["location_evidence"].map(
        {
            "observed_raw": "observed",
            "awake_adaptive": "supported_inference",
            "sleep_episode_locked": "supported_inference",
            "sleep_gap_context_filled": "supported_inference",
            "missing": "missing",
        }
    ).fillna("uncertain")
    timeline = timeline.drop(columns=["beacon_to_room"])

    audit = {
        **movement_audit,
        **sleep_audit,
        **bedroom_audit,
        **away_audit,
        "window_count": len(timeline),
        "raw_observed_fraction": float(timeline["rssi_observed"].mean()) if len(timeline) else np.nan,
        "corrected_observed_fraction": float(timeline["corrected_beacon"].notna().mean()) if len(timeline) else np.nan,
        "corrected_window_count": int(timeline["was_corrected"].sum()),
        "sleep_gap_filled_windows": int(timeline["sleep_gap_filled"].sum()),
        "raw_transition_count": count_transitions(timeline["raw_room"]),
        "corrected_transition_count": count_transitions(timeline["corrected_room"]),
    }
    return {
        "timeline": timeline,
        "episodes": episodes,
        "away_runs": away_runs,
        "movement_diagnostics": movement_diagnostics,
        "sleep_diagnostics": sleep_diagnostics,
        "audit": audit,
    }
