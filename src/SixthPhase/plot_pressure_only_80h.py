import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "New data- 80 hour single user" / "559662"
RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

BEACON_PRESSURE_PATH = DATA_DIR / "BEACONS_PRESSURE.csv"
BRACELET_PRESSURE_PATH = DATA_DIR / "PRESSURE.csv"

RAW_OUTPUT = RESULTS_DIR / "new80h_raw_beacon_bracelet_pressure_timeline.png"
CLEANED_OUTPUT = RESULTS_DIR / "new80h_cleaned_beacon_bracelet_pressure_timeline.png"
PLATEAU_OUTPUT = (
    RESULTS_DIR / "new80h_long_plateau_corrected_beacon_bracelet_pressure_timeline.png"
)
SUMMARY_OUTPUT = RESULTS_DIR / "new80h_pressure_cleaning_summary.csv"
PLATEAU_SUMMARY_OUTPUT = RESULTS_DIR / "new80h_pressure_long_plateau_summary.csv"
RESIDUAL_SEGMENT_SUMMARY_OUTPUT = (
    RESULTS_DIR / "new80h_pressure_residual_segment_summary.csv"
)

PRESSURE_MIN_HPA = 950
PRESSURE_MAX_HPA = 1050
PLOT_PRESSURE_MIN_HPA = 1000
PLOT_PRESSURE_MAX_HPA = 1010
BEACON_ROLLING_WINDOW = 3
BRACELET_ROLLING_WINDOW = 11
BEACON_SPIKE_WINDOW = 7
BRACELET_SPIKE_WINDOW = 121
SPIKE_THRESHOLD_HPA = 1.5
BEACON_SHORT_SPIKE_MAX_ROWS = 2
BRACELET_SHORT_SPIKE_MAX_ROWS = 50
LONG_PLATEAU_OFFSET_THRESHOLD_HPA = 2.5
LONG_PLATEAU_MIN_ROWS = 120
PLATEAU_CONTEXT_ROWS = 60
RESIDUAL_OFFSET_THRESHOLD_HPA = 1.2
RESIDUAL_MAX_ROWS = 60


def load_pressure_csv(path):
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).copy()
    frame["time"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.sort_values("time")


def pressure_columns(frame):
    return [column for column in frame.columns if column not in {"timestamp", "time"}]


def find_true_runs(mask):
    runs = []
    start = None
    for index, is_true in enumerate(mask):
        if is_true and start is None:
            start = index
        elif not is_true and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def interpolate_run(values, start, end, anomaly_mask):
    previous_index = start - 1
    while previous_index >= 0 and (
        anomaly_mask.iloc[previous_index] or pd.isna(values.iloc[previous_index])
    ):
        previous_index -= 1

    next_index = end + 1
    while next_index < len(values) and (
        anomaly_mask.iloc[next_index] or pd.isna(values.iloc[next_index])
    ):
        next_index += 1

    previous_value = values.iloc[previous_index] if previous_index >= 0 else pd.NA
    next_value = values.iloc[next_index] if next_index < len(values) else pd.NA

    if pd.notna(previous_value) and pd.notna(next_value):
        run_length = end - start + 1
        for offset, row_index in enumerate(range(start, end + 1), start=1):
            weight = offset / (run_length + 1)
            values.iloc[row_index] = previous_value + (next_value - previous_value) * weight
    elif pd.notna(previous_value):
        values.iloc[start : end + 1] = previous_value
    elif pd.notna(next_value):
        values.iloc[start : end + 1] = next_value


def correct_short_spikes(frame, columns, window, threshold_hpa, max_run_rows):
    corrected = frame.copy()
    short_spike_masks = {}
    long_spike_masks = {}
    for column in columns:
        values = pd.to_numeric(corrected[column], errors="coerce").copy()

        short_mask = pd.Series(False, index=values.index)
        long_mask = pd.Series(False, index=values.index)

        range_anomaly = values.notna() & ~values.between(PRESSURE_MIN_HPA, PRESSURE_MAX_HPA)
        for start, end in find_true_runs(range_anomaly.to_list()):
            if end - start + 1 <= max_run_rows:
                interpolate_run(values, start, end, range_anomaly)
                short_mask.iloc[start : end + 1] = True
            else:
                long_mask.iloc[start : end + 1] = True

        local_median = values.rolling(window=window, center=True, min_periods=1).median()
        jump_anomaly = (
            values.notna()
            & values.between(PRESSURE_MIN_HPA, PRESSURE_MAX_HPA)
            & (values - local_median).abs().gt(threshold_hpa)
            & ~short_mask
            & ~long_mask
        )
        for start, end in find_true_runs(jump_anomaly.to_list()):
            if end - start + 1 <= max_run_rows:
                interpolate_run(values, start, end, jump_anomaly)
                short_mask.iloc[start : end + 1] = True
            else:
                long_mask.iloc[start : end + 1] = True

        corrected[column] = values
        short_spike_masks[column] = short_mask
        long_spike_masks[column] = long_mask
    return corrected, short_spike_masks, long_spike_masks


def build_beacon_baseline(beacon_pressure, beacon_columns, target_times):
    baseline = beacon_pressure[["time", *beacon_columns]].copy()
    baseline["beacon_baseline_pressure"] = baseline[beacon_columns].median(axis=1)
    baseline = (
        baseline[["time", "beacon_baseline_pressure"]]
        .set_index("time")
        .resample("30s")
        .interpolate("time", limit_direction="both")
        .reindex(target_times)
        .interpolate("time", limit_direction="both")
        .reset_index()
        .rename(columns={"index": "time"})
    )
    return baseline


def normal_context_offset(offset, mask, start, end, threshold_hpa):
    before_start = max(0, start - PLATEAU_CONTEXT_ROWS)
    before = offset.iloc[before_start:start]
    before = before.loc[~mask.iloc[before_start:start]]
    before = before.loc[before.abs().le(threshold_hpa)]

    after_end = min(len(offset), end + 1 + PLATEAU_CONTEXT_ROWS)
    after = offset.iloc[end + 1 : after_end]
    after = after.loc[~mask.iloc[end + 1 : after_end]]
    after = after.loc[after.abs().le(threshold_hpa)]

    before_offset = before.median() if not before.empty else pd.NA
    after_offset = after.median() if not after.empty else pd.NA
    return before_offset, after_offset


def correct_long_plateaus(bracelet_pressure, beacon_pressure, beacon_columns):
    corrected = bracelet_pressure.copy()
    target_times = bracelet_pressure["time"]
    baseline = build_beacon_baseline(
        beacon_pressure, beacon_columns, pd.DatetimeIndex(target_times)
    )
    joined = corrected[["time", "PRESSURE"]].merge(baseline, on="time", how="left")
    offset = joined["PRESSURE"] - joined["beacon_baseline_pressure"]
    plateau_mask = offset.abs().gt(LONG_PLATEAU_OFFSET_THRESHOLD_HPA)

    summary_rows = []
    corrected_mask = pd.Series(False, index=corrected.index)
    for start, end in find_true_runs(plateau_mask.fillna(False).to_list()):
        run_length = end - start + 1
        if run_length < LONG_PLATEAU_MIN_ROWS:
            continue

        before_offset, after_offset = normal_context_offset(
            offset, plateau_mask, start, end, LONG_PLATEAU_OFFSET_THRESHOLD_HPA
        )
        if pd.isna(before_offset) and pd.isna(after_offset):
            continue
        if pd.isna(before_offset):
            before_offset = after_offset
        if pd.isna(after_offset):
            after_offset = before_offset

        for step, row_index in enumerate(range(start, end + 1), start=1):
            weight = step / (run_length + 1)
            target_offset = before_offset + (after_offset - before_offset) * weight
            baseline_value = joined.loc[row_index, "beacon_baseline_pressure"]
            corrected.loc[row_index, "PRESSURE"] = baseline_value + target_offset
            corrected_mask.iloc[row_index] = True

        segment = joined.iloc[start : end + 1]
        summary_rows.append(
            {
                "start_time": segment["time"].iloc[0],
                "end_time": segment["time"].iloc[-1],
                "duration_minutes": run_length * 0.5,
                "rows_corrected": run_length,
                "raw_pressure_min_hpa": segment["PRESSURE"].min(),
                "raw_pressure_max_hpa": segment["PRESSURE"].max(),
                "raw_offset_median_hpa": offset.iloc[start : end + 1].median(),
                "raw_offset_min_hpa": offset.iloc[start : end + 1].min(),
                "raw_offset_max_hpa": offset.iloc[start : end + 1].max(),
                "before_context_offset_hpa": before_offset,
                "after_context_offset_hpa": after_offset,
            }
        )

    return corrected, corrected_mask, pd.DataFrame(summary_rows)


def correct_residual_offset_segments(bracelet_pressure, beacon_pressure, beacon_columns):
    corrected = bracelet_pressure.copy()
    target_times = bracelet_pressure["time"]
    baseline = build_beacon_baseline(
        beacon_pressure, beacon_columns, pd.DatetimeIndex(target_times)
    )
    joined = corrected[["time", "PRESSURE"]].merge(baseline, on="time", how="left")
    offset = joined["PRESSURE"] - joined["beacon_baseline_pressure"]
    segment_mask = offset.abs().gt(RESIDUAL_OFFSET_THRESHOLD_HPA)

    summary_rows = []
    corrected_mask = pd.Series(False, index=corrected.index)
    for start, end in find_true_runs(segment_mask.fillna(False).to_list()):
        run_length = end - start + 1
        if run_length > RESIDUAL_MAX_ROWS:
            continue

        before_offset, after_offset = normal_context_offset(
            offset, segment_mask, start, end, RESIDUAL_OFFSET_THRESHOLD_HPA
        )
        if pd.isna(before_offset) and pd.isna(after_offset):
            continue
        if pd.isna(before_offset):
            before_offset = after_offset
        if pd.isna(after_offset):
            after_offset = before_offset

        for step, row_index in enumerate(range(start, end + 1), start=1):
            weight = step / (run_length + 1)
            target_offset = before_offset + (after_offset - before_offset) * weight
            baseline_value = joined.loc[row_index, "beacon_baseline_pressure"]
            corrected.loc[row_index, "PRESSURE"] = baseline_value + target_offset
            corrected_mask.iloc[row_index] = True

        segment = joined.iloc[start : end + 1]
        summary_rows.append(
            {
                "start_time": segment["time"].iloc[0],
                "end_time": segment["time"].iloc[-1],
                "duration_minutes": run_length * 0.5,
                "rows_corrected": run_length,
                "raw_pressure_min_hpa": segment["PRESSURE"].min(),
                "raw_pressure_max_hpa": segment["PRESSURE"].max(),
                "raw_offset_median_hpa": offset.iloc[start : end + 1].median(),
                "raw_offset_min_hpa": offset.iloc[start : end + 1].min(),
                "raw_offset_max_hpa": offset.iloc[start : end + 1].max(),
                "before_context_offset_hpa": before_offset,
                "after_context_offset_hpa": after_offset,
            }
        )

    return corrected, corrected_mask, pd.DataFrame(summary_rows)


def correct_baseline_offset_short_segments(
    bracelet_pressure, beacon_pressure, beacon_columns
):
    corrected = bracelet_pressure.copy()
    target_times = bracelet_pressure["time"]
    baseline = build_beacon_baseline(
        beacon_pressure, beacon_columns, pd.DatetimeIndex(target_times)
    )
    joined = corrected[["time", "PRESSURE"]].merge(baseline, on="time", how="left")
    offset = joined["PRESSURE"] - joined["beacon_baseline_pressure"]
    segment_mask = offset.abs().gt(RESIDUAL_OFFSET_THRESHOLD_HPA)

    summary_rows = []
    short_mask = pd.Series(False, index=corrected.index)
    long_mask = pd.Series(False, index=corrected.index)
    for start, end in find_true_runs(segment_mask.fillna(False).to_list()):
        run_length = end - start + 1
        if run_length > RESIDUAL_MAX_ROWS:
            long_mask.iloc[start : end + 1] = True
            continue

        before_offset, after_offset = normal_context_offset(
            offset, segment_mask, start, end, RESIDUAL_OFFSET_THRESHOLD_HPA
        )
        if pd.isna(before_offset) and pd.isna(after_offset):
            continue
        if pd.isna(before_offset):
            before_offset = after_offset
        if pd.isna(after_offset):
            after_offset = before_offset

        for step, row_index in enumerate(range(start, end + 1), start=1):
            weight = step / (run_length + 1)
            target_offset = before_offset + (after_offset - before_offset) * weight
            baseline_value = joined.loc[row_index, "beacon_baseline_pressure"]
            corrected.loc[row_index, "PRESSURE"] = baseline_value + target_offset
            short_mask.iloc[row_index] = True

        segment = joined.iloc[start : end + 1]
        summary_rows.append(
            {
                "start_time": segment["time"].iloc[0],
                "end_time": segment["time"].iloc[-1],
                "duration_minutes": run_length * 0.5,
                "rows_corrected": run_length,
                "raw_pressure_min_hpa": segment["PRESSURE"].min(),
                "raw_pressure_max_hpa": segment["PRESSURE"].max(),
                "raw_offset_median_hpa": offset.iloc[start : end + 1].median(),
                "raw_offset_min_hpa": offset.iloc[start : end + 1].min(),
                "raw_offset_max_hpa": offset.iloc[start : end + 1].max(),
                "before_context_offset_hpa": before_offset,
                "after_context_offset_hpa": after_offset,
            }
        )

    return corrected, short_mask, long_mask, pd.DataFrame(summary_rows)


def build_cleaning_summary(
    raw,
    corrected,
    short_spike_masks,
    long_spike_masks,
    source_name,
    window,
    max_run_rows,
):
    rows = []
    for column in pressure_columns(raw):
        raw_values = pd.to_numeric(raw[column], errors="coerce")
        corrected_values = pd.to_numeric(corrected[column], errors="coerce")
        out_of_range = raw_values.notna() & ~raw_values.between(
            PRESSURE_MIN_HPA, PRESSURE_MAX_HPA
        )
        changed = raw_values.ne(corrected_values) & raw_values.notna() & corrected_values.notna()
        short_spike_mask = short_spike_masks[column]
        long_spike_mask = long_spike_masks[column]
        rows.append(
            {
                "source": source_name,
                "sensor": column,
                "rows": len(raw_values),
                "raw_missing_rows": int(raw_values.isna().sum()),
                "out_of_range_rows": int(out_of_range.sum()),
                "out_of_range_fraction": out_of_range.mean(),
                "short_spike_corrected_rows": int(short_spike_mask.sum()),
                "short_spike_corrected_fraction": short_spike_mask.mean(),
                "long_spike_preserved_rows": int(long_spike_mask.sum()),
                "long_spike_preserved_fraction": long_spike_mask.mean(),
                "changed_rows": int(changed.sum()),
                "cleaned_missing_rows": int(corrected_values.isna().sum()),
                "detection_window_rows": window,
                "short_spike_max_run_rows": max_run_rows,
                "raw_min_hpa": raw_values.min(),
                "raw_max_hpa": raw_values.max(),
                "cleaned_min_hpa": corrected_values.min(),
                "cleaned_max_hpa": corrected_values.max(),
            }
        )
    return rows


def plot_raw_pressure(beacon_pressure, bracelet_pressure):
    beacon_cols = pressure_columns(beacon_pressure)

    fig, axes = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
    for column in beacon_cols:
        axes[0].plot(
            beacon_pressure["time"],
            pd.to_numeric(beacon_pressure[column], errors="coerce"),
            linewidth=0.8,
            alpha=0.9,
            label=f"Beacon {column}",
        )
    axes[0].plot(
        bracelet_pressure["time"],
        pd.to_numeric(bracelet_pressure["PRESSURE"], errors="coerce"),
        color="black",
        linewidth=1.4,
        label="Bracelet",
    )
    axes[0].set_title("Raw pressure timeline: beacon and bracelet sensors")
    axes[0].set_ylabel("Pressure (hPa)")
    axes[0].grid(alpha=0.2)
    axes[0].legend(ncol=5, fontsize=8, loc="best")

    for column in beacon_cols:
        axes[1].plot(
            beacon_pressure["time"],
            pd.to_numeric(beacon_pressure[column], errors="coerce"),
            linewidth=0.8,
            alpha=0.9,
            label=f"Beacon {column}",
        )
    axes[1].plot(
        bracelet_pressure["time"],
        pd.to_numeric(bracelet_pressure["PRESSURE"], errors="coerce"),
        color="black",
        linewidth=1.4,
        label="Bracelet",
    )
    axes[1].set_ylim(PLOT_PRESSURE_MIN_HPA, PLOT_PRESSURE_MAX_HPA)
    axes[1].set_title("Raw pressure timeline zoomed to plausible pressure range")
    axes[1].set_ylabel("Pressure (hPa)")
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.2)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(RAW_OUTPUT, dpi=220)
    plt.close(fig)
    return RAW_OUTPUT


def plot_pressure_timeline(beacon_pressure, bracelet_pressure, title, output_path):
    beacon_cols = pressure_columns(beacon_pressure)

    fig, ax = plt.subplots(figsize=(13, 5.8))
    for column in beacon_cols:
        ax.plot(
            beacon_pressure["time"],
            pd.to_numeric(beacon_pressure[column], errors="coerce"),
            linewidth=1.0,
            alpha=0.9,
            label=f"Beacon {column}",
        )
    ax.plot(
        bracelet_pressure["time"],
        pd.to_numeric(bracelet_pressure["PRESSURE"], errors="coerce"),
        color="black",
        linewidth=1.7,
        label="Bracelet",
    )
    ax.set_title(title)
    ax.set_ylabel("Pressure (hPa)")
    ax.set_xlabel("Time")
    ax.set_ylim(PLOT_PRESSURE_MIN_HPA, PLOT_PRESSURE_MAX_HPA)
    ax.grid(alpha=0.2)
    ax.legend(ncol=5, fontsize=8, loc="best")

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)
    return output_path


def main():
    beacon_pressure = load_pressure_csv(BEACON_PRESSURE_PATH)
    bracelet_pressure = load_pressure_csv(BRACELET_PRESSURE_PATH)

    beacon_cols = pressure_columns(beacon_pressure)
    bracelet_cols = pressure_columns(bracelet_pressure)

    beacon_corrected, beacon_short_spike_masks, beacon_long_spike_masks = (
        correct_short_spikes(
            beacon_pressure,
            beacon_cols,
            BEACON_SPIKE_WINDOW,
            SPIKE_THRESHOLD_HPA,
            BEACON_SHORT_SPIKE_MAX_ROWS,
        )
    )
    bracelet_corrected, bracelet_short_spike_masks, bracelet_long_spike_masks = (
        correct_short_spikes(
            bracelet_pressure,
            bracelet_cols,
            BRACELET_SPIKE_WINDOW,
            SPIKE_THRESHOLD_HPA,
            BRACELET_SHORT_SPIKE_MAX_ROWS,
        )
    )
    bracelet_plateau_first, bracelet_plateau_mask, plateau_summary = (
        correct_long_plateaus(bracelet_pressure, beacon_corrected, beacon_cols)
    )
    bracelet_final_corrected, final_short_spike_masks, final_long_spike_masks, final_short_summary = (
        correct_baseline_offset_short_segments(
            bracelet_plateau_first,
            beacon_corrected,
            beacon_cols,
        )
    )

    summary_rows = []
    summary_rows.extend(
        build_cleaning_summary(
            beacon_pressure,
            beacon_corrected,
            beacon_short_spike_masks,
            beacon_long_spike_masks,
            "beacon",
            BEACON_SPIKE_WINDOW,
            BEACON_SHORT_SPIKE_MAX_ROWS,
        )
    )
    summary_rows.extend(
        build_cleaning_summary(
            bracelet_pressure,
            bracelet_corrected,
            bracelet_short_spike_masks,
            bracelet_long_spike_masks,
            "bracelet",
            BRACELET_SPIKE_WINDOW,
            BRACELET_SHORT_SPIKE_MAX_ROWS,
        )
    )
    pd.DataFrame(summary_rows).to_csv(SUMMARY_OUTPUT, index=False)
    plateau_summary.to_csv(PLATEAU_SUMMARY_OUTPUT, index=False)
    pd.DataFrame(
        final_short_summary
    ).to_csv(RESIDUAL_SEGMENT_SUMMARY_OUTPUT, index=False)

    outputs = [
        plot_raw_pressure(beacon_pressure, bracelet_pressure),
        plot_pressure_timeline(
            beacon_corrected,
            bracelet_corrected,
            "Cleaned pressure timeline: short spike correction only",
            CLEANED_OUTPUT,
        ),
        plot_pressure_timeline(
            beacon_corrected,
            bracelet_final_corrected,
            "Cleaned pressure timeline: long plateau correction, then offset short-segment correction",
            PLATEAU_OUTPUT,
        ),
        SUMMARY_OUTPUT,
        PLATEAU_SUMMARY_OUTPUT,
        RESIDUAL_SEGMENT_SUMMARY_OUTPUT,
    ]

    print("Pressure-only quick plot complete")
    print("Data directory:", DATA_DIR)
    print("Saved outputs:")
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
