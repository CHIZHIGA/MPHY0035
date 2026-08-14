# Verbatim excerpt: src/EighthPhase/core.py, lines 464-510

import numpy as np
import pandas as pd

from EighthPhase.core import WINDOWS_BY_K


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
