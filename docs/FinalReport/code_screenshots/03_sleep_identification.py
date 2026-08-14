# Verbatim excerpt: src/EighthPhase/core.py, lines 241-303

import numpy as np
import pandas as pd

from EighthPhase.core import PipelineParameters, choose_ordered_clustering


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
