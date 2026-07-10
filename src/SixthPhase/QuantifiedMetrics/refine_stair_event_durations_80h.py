import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SIXTH_PHASE_SRC = ROOT / "src" / "SixthPhase"
if str(SIXTH_PHASE_SRC) not in sys.path:
    sys.path.insert(0, str(SIXTH_PHASE_SRC))

from plot_pressure_only_80h import (  # noqa: E402
    BEACON_PRESSURE_PATH,
    BEACON_SHORT_SPIKE_MAX_ROWS,
    BEACON_SPIKE_WINDOW,
    BRACELET_PRESSURE_PATH,
    BRACELET_SHORT_SPIKE_MAX_ROWS,
    BRACELET_SPIKE_WINDOW,
    SPIKE_THRESHOLD_HPA,
    build_beacon_baseline,
    correct_baseline_offset_short_segments,
    correct_long_plateaus,
    correct_short_spikes,
    load_pressure_csv,
    pressure_columns,
)


DATA_DIR = ROOT / "Data" / "New data- 80 hour single user" / "559662"
SOURCE_RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"
OUTPUT_DIR = ROOT / "Results" / "SixthPhase" / "QuantifiedMetrics"

ACC_PATH = DATA_DIR / "HE_ACC.csv"
STAIR_EVENTS_PATH = OUTPUT_DIR / "new80h_stair_events_5min.csv"

REFINED_OUTPUT = OUTPUT_DIR / "new80h_stair_event_refined_durations.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "new80h_stair_event_refined_duration_summary.csv"

LOCAL_WINDOW_MINUTES = 5
BEFORE_AFTER_LEVEL_MINUTES = 2
RAMP_START_FRACTION = 0.10
RAMP_END_FRACTION = 0.90
MIN_PRESSURE_RAMP_HPA = 0.12
MAX_PLAUSIBLE_REFINED_DURATION_MIN = 3.0
ACC_SPIKE_THRESHOLD = 1.2
ACC_SPIKE_REPLACEMENT = 1.0
ACC_STD_SUPPORT_THRESHOLD = 0.010
ACC_MAX_ABS_DEVIATION_SUPPORT_THRESHOLD = 0.030


def load_clean_relative_pressure():
    beacon_pressure = load_pressure_csv(BEACON_PRESSURE_PATH)
    bracelet_pressure = load_pressure_csv(BRACELET_PRESSURE_PATH)

    beacon_cols = pressure_columns(beacon_pressure)
    bracelet_cols = pressure_columns(bracelet_pressure)

    beacon_corrected, _, _ = correct_short_spikes(
        beacon_pressure,
        beacon_cols,
        BEACON_SPIKE_WINDOW,
        SPIKE_THRESHOLD_HPA,
        BEACON_SHORT_SPIKE_MAX_ROWS,
    )
    bracelet_spike_corrected, _, _ = correct_short_spikes(
        bracelet_pressure,
        bracelet_cols,
        BRACELET_SPIKE_WINDOW,
        SPIKE_THRESHOLD_HPA,
        BRACELET_SHORT_SPIKE_MAX_ROWS,
    )
    bracelet_plateau_corrected, _, _ = correct_long_plateaus(
        bracelet_pressure, beacon_corrected, beacon_cols
    )
    bracelet_corrected, _, _, _ = correct_baseline_offset_short_segments(
        bracelet_plateau_corrected, beacon_corrected, beacon_cols
    )

    target_times = pd.DatetimeIndex(bracelet_corrected["time"])
    beacon_baseline = build_beacon_baseline(
        beacon_corrected, beacon_cols, target_times
    )
    pressure = bracelet_corrected[["time", "PRESSURE"]].merge(
        beacon_baseline, on="time", how="left"
    )
    pressure["bracelet_relative_pressure_hpa"] = (
        pressure["PRESSURE"] - pressure["beacon_baseline_pressure"]
    )
    pressure["relative_pressure_smooth_hpa"] = (
        pressure["bracelet_relative_pressure_hpa"]
        .rolling(window=3, center=True, min_periods=1)
        .median()
    )
    return pressure


def load_clean_acc():
    acc = pd.read_csv(ACC_PATH)
    acc["timestamp"] = pd.to_numeric(acc["timestamp"], errors="coerce")
    acc = acc.dropna(subset=["timestamp"]).copy()
    acc["time"] = pd.to_datetime(acc["timestamp"], unit="ms", utc=True)
    acc = acc.sort_values("time")
    acc["acc_magnitude_raw"] = pd.to_numeric(acc["MAGNITUDE"], errors="coerce")
    acc["acc_spike_gt_1p2"] = acc["acc_magnitude_raw"].gt(ACC_SPIKE_THRESHOLD)
    acc["acc_magnitude_clean"] = acc["acc_magnitude_raw"].mask(
        acc["acc_spike_gt_1p2"], ACC_SPIKE_REPLACEMENT
    )
    acc["acc_abs_deviation_from_1g"] = (acc["acc_magnitude_clean"] - 1.0).abs()
    return acc[
        [
            "time",
            "acc_magnitude_raw",
            "acc_magnitude_clean",
            "acc_abs_deviation_from_1g",
            "acc_spike_gt_1p2",
        ]
    ]


def local_slice(frame, time_col, start_time, end_time):
    return frame.loc[frame[time_col].between(start_time, end_time)].copy()


def estimate_levels(segment, shift_time):
    before_start = shift_time - pd.Timedelta(minutes=LOCAL_WINDOW_MINUTES)
    before_end = shift_time - pd.Timedelta(minutes=BEFORE_AFTER_LEVEL_MINUTES)
    after_start = shift_time + pd.Timedelta(minutes=BEFORE_AFTER_LEVEL_MINUTES)
    after_end = shift_time + pd.Timedelta(minutes=LOCAL_WINDOW_MINUTES)

    before = segment.loc[
        segment["time"].between(before_start, before_end),
        "relative_pressure_smooth_hpa",
    ].dropna()
    after = segment.loc[
        segment["time"].between(after_start, after_end),
        "relative_pressure_smooth_hpa",
    ].dropna()

    if before.empty:
        before = segment["relative_pressure_smooth_hpa"].dropna().head(4)
    if after.empty:
        after = segment["relative_pressure_smooth_hpa"].dropna().tail(4)

    before_level = before.median() if not before.empty else pd.NA
    after_level = after.median() if not after.empty else pd.NA
    return before_level, after_level


def expected_pressure_sign(stair_direction):
    if stair_direction == "ascent":
        return -1
    if stair_direction == "descent":
        return 1
    return 0


def estimate_pressure_ramp(event, pressure):
    shift_time = event["shift_time"]
    window_start = shift_time - pd.Timedelta(minutes=LOCAL_WINDOW_MINUTES)
    window_end = shift_time + pd.Timedelta(minutes=LOCAL_WINDOW_MINUTES)
    segment = local_slice(pressure, "time", window_start, window_end)
    if segment.empty:
        return {
            "pressure_ramp_start": pd.NaT,
            "pressure_ramp_end": pd.NaT,
            "pressure_ramp_duration_min": pd.NA,
            "pressure_before_level_hpa": pd.NA,
            "pressure_after_level_hpa": pd.NA,
            "pressure_ramp_delta_hpa": pd.NA,
            "pressure_ramp_abs_delta_hpa": pd.NA,
            "pressure_ramp_sign_matches_direction": False,
            "pressure_ramp_delta_too_small": True,
            "pressure_ramp_detection_method": "no_pressure_samples_in_local_window",
        }

    before_level, after_level = estimate_levels(segment, shift_time)
    if pd.isna(before_level) or pd.isna(after_level):
        delta = pd.NA
    else:
        delta = after_level - before_level

    sign = expected_pressure_sign(event["stair_direction"])
    sign_matches = pd.notna(delta) and sign != 0 and (delta * sign > 0)
    delta_too_small = pd.isna(delta) or abs(delta) < MIN_PRESSURE_RAMP_HPA

    ramp_start = pd.NaT
    ramp_end = pd.NaT
    duration_min = pd.NA
    method = "pressure_10_to_90_percent_ramp"

    if not delta_too_small:
        working = segment.dropna(subset=["relative_pressure_smooth_hpa"]).copy()
        working["ramp_progress"] = (
            working["relative_pressure_smooth_hpa"] - before_level
        ) / delta
        working["ramp_progress_monotonic"] = working["ramp_progress"].cummax()
        start_candidates = working.loc[
            working["ramp_progress_monotonic"].ge(RAMP_START_FRACTION)
        ]
        end_candidates = working.loc[
            working["ramp_progress_monotonic"].ge(RAMP_END_FRACTION)
        ]
        if not start_candidates.empty and not end_candidates.empty:
            ramp_start = start_candidates["time"].iloc[0]
            ramp_end = end_candidates["time"].iloc[0]
            if ramp_end < ramp_start:
                ramp_start = pd.NaT
                ramp_end = pd.NaT
                method = "pressure_ramp_crossing_order_invalid"
            else:
                duration_min = (ramp_end - ramp_start).total_seconds() / 60
        else:
            method = "pressure_ramp_thresholds_not_crossed"
    else:
        method = "pressure_delta_too_small_for_refined_duration"

    return {
        "pressure_ramp_start": ramp_start,
        "pressure_ramp_end": ramp_end,
        "pressure_ramp_duration_min": duration_min,
        "pressure_before_level_hpa": before_level,
        "pressure_after_level_hpa": after_level,
        "pressure_ramp_delta_hpa": delta,
        "pressure_ramp_abs_delta_hpa": abs(delta) if pd.notna(delta) else pd.NA,
        "pressure_ramp_sign_matches_direction": bool(sign_matches),
        "pressure_ramp_delta_too_small": bool(delta_too_small),
        "pressure_ramp_detection_method": method,
    }


def summarize_acc_for_interval(acc, start_time, end_time):
    if pd.isna(start_time) or pd.isna(end_time):
        return {
            "refined_acc_samples": 0,
            "refined_acc_mean_clean": pd.NA,
            "refined_acc_std_clean": pd.NA,
            "refined_acc_max_raw": pd.NA,
            "refined_acc_max_abs_deviation_from_1g": pd.NA,
            "refined_acc_spike_count_gt_1p2": 0,
            "refined_acc_supports_motion": False,
            "refined_acc_support_reason": "no_refined_pressure_ramp_interval",
        }

    segment = local_slice(acc, "time", start_time, end_time)
    samples = len(segment)
    std_clean = segment["acc_magnitude_clean"].std() if samples else pd.NA
    max_abs_dev = (
        segment["acc_abs_deviation_from_1g"].max() if samples else pd.NA
    )
    spike_count = int(segment["acc_spike_gt_1p2"].sum()) if samples else 0
    supports = (
        (pd.notna(std_clean) and std_clean >= ACC_STD_SUPPORT_THRESHOLD)
        or (pd.notna(max_abs_dev) and max_abs_dev >= ACC_MAX_ABS_DEVIATION_SUPPORT_THRESHOLD)
        or spike_count > 0
    )
    if supports:
        reason = "acc_variability_or_deviation_high_inside_pressure_ramp"
    else:
        reason = "no_clear_acc_elevation_inside_pressure_ramp"

    return {
        "refined_acc_samples": samples,
        "refined_acc_mean_clean": segment["acc_magnitude_clean"].mean()
        if samples
        else pd.NA,
        "refined_acc_std_clean": std_clean,
        "refined_acc_max_raw": segment["acc_magnitude_raw"].max()
        if samples
        else pd.NA,
        "refined_acc_max_abs_deviation_from_1g": max_abs_dev,
        "refined_acc_spike_count_gt_1p2": spike_count,
        "refined_acc_supports_motion": bool(supports),
        "refined_acc_support_reason": reason,
    }


def build_refined_durations(events, pressure, acc):
    rows = []
    for _, event in events.iterrows():
        pressure_features = estimate_pressure_ramp(event, pressure)
        acc_features = summarize_acc_for_interval(
            acc,
            pressure_features["pressure_ramp_start"],
            pressure_features["pressure_ramp_end"],
        )
        duration = pressure_features["pressure_ramp_duration_min"]
        too_long = pd.notna(duration) and duration > MAX_PLAUSIBLE_REFINED_DURATION_MIN
        rows.append(
            {
                "shift_time": event["shift_time"],
                "event_date": event["event_date"],
                "stair_direction": event["stair_direction"],
                "event_label": event["event_label"],
                "source_of_stair_event": "pressure_floor_shift",
                "coarse_evidence_window_min": event["estimated_duration_min"],
                "coarse_window_note": (
                    "5-min pressure/ACC evidence window; not true stair duration"
                ),
                **pressure_features,
                "refined_duration_too_long_anomaly": bool(too_long),
                **acc_features,
                "floor_shift_acc_supported_5min": event["floor_shift_acc_supported"],
                "support_reason_5min": event["support_reason"],
            }
        )
    return pd.DataFrame(rows)


def build_summary(refined):
    valid = refined.dropna(subset=["pressure_ramp_duration_min"]).copy()
    grouped = valid.groupby("stair_direction")
    rows = []
    for direction, group in grouped:
        rows.append(
            {
                "stair_direction": direction,
                "event_count_with_refined_duration": len(group),
                "median_refined_duration_min": group[
                    "pressure_ramp_duration_min"
                ].median(),
                "mean_refined_duration_min": group[
                    "pressure_ramp_duration_min"
                ].mean(),
                "min_refined_duration_min": group[
                    "pressure_ramp_duration_min"
                ].min(),
                "max_refined_duration_min": group[
                    "pressure_ramp_duration_min"
                ].max(),
                "acc_supported_inside_ramp": int(
                    group["refined_acc_supports_motion"].sum()
                ),
                "duration_too_long_anomalies": int(
                    group["refined_duration_too_long_anomaly"].sum()
                ),
            }
        )
    rows.append(
        {
            "stair_direction": "all",
            "event_count_with_refined_duration": len(valid),
            "median_refined_duration_min": valid[
                "pressure_ramp_duration_min"
            ].median(),
            "mean_refined_duration_min": valid["pressure_ramp_duration_min"].mean(),
            "min_refined_duration_min": valid["pressure_ramp_duration_min"].min(),
            "max_refined_duration_min": valid["pressure_ramp_duration_min"].max(),
            "acc_supported_inside_ramp": int(
                valid["refined_acc_supports_motion"].sum()
            ),
            "duration_too_long_anomalies": int(
                valid["refined_duration_too_long_anomaly"].sum()
            ),
        }
    )
    return pd.DataFrame(rows)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(
        STAIR_EVENTS_PATH,
        parse_dates=[
            "shift_time",
            "estimated_event_start",
            "estimated_event_end",
            "duration_window_start",
            "duration_window_end",
            "support_window_start",
            "support_window_end",
        ],
    )
    pressure = load_clean_relative_pressure()
    acc = load_clean_acc()
    refined = build_refined_durations(events, pressure, acc)
    summary = build_summary(refined)

    refined.to_csv(REFINED_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)

    print("Refined stair duration analysis complete")
    print("Saved outputs:")
    for output in [REFINED_OUTPUT, SUMMARY_OUTPUT]:
        print(output)
    print("\nRefined duration summary:")
    print(summary.to_string(index=False))
    print("\nEvents with missing or anomalous refined duration:")
    flagged = refined.loc[
        refined["pressure_ramp_duration_min"].isna()
        | refined["refined_duration_too_long_anomaly"]
        | ~refined["pressure_ramp_sign_matches_direction"]
        | refined["pressure_ramp_delta_too_small"]
    ]
    if flagged.empty:
        print("No missing or anomalous refined durations detected.")
    else:
        print(
            flagged[
                [
                    "shift_time",
                    "stair_direction",
                    "pressure_ramp_duration_min",
                    "pressure_ramp_delta_hpa",
                    "pressure_ramp_sign_matches_direction",
                    "pressure_ramp_delta_too_small",
                    "pressure_ramp_detection_method",
                    "refined_acc_supports_motion",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
