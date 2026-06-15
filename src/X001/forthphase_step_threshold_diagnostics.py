import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forthphase_fixed_rssi_window_comparison import (
    DATA_DIR,
    RESULTS_DIR,
    SIDES,
    SIDE_TO_ROLE,
)


WINDOWS = ["1min", "5min", "10min", "30min"]
THRESHOLDS = [1, 2, 5, 10]

SUMMARY_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_step_threshold_counts_by_window.csv",
)
UNIFORMIZED_SUMMARY_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_step_threshold_counts_by_window_uniformized.csv",
)
FIGURE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_step_threshold_proportions_by_window.png",
)
UNIFORMIZED_FIGURE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_step_threshold_proportions_by_window_uniformized.png",
)


def load_step_samples(side):
    path = os.path.join(DATA_DIR, side, "SAMPLES_Step_count.csv")
    steps = pd.read_csv(
        path,
        header=None,
        names=["timestamp", "timestamp_str", "step_count"],
    )
    steps["time"] = pd.to_datetime(
        pd.to_numeric(steps["timestamp"], errors="coerce"),
        unit="ms",
    )
    steps["step_count"] = pd.to_numeric(steps["step_count"], errors="coerce")
    steps = steps.dropna(subset=["time", "step_count"]).sort_values("time")
    steps = steps.set_index("time")
    diff = steps["step_count"].diff().fillna(0)
    steps["step_increment"] = diff.clip(lower=0)
    steps["step_reset_flag"] = diff < 0
    return steps


def build_step_windows(side, window):
    steps = load_step_samples(side)
    grouped = steps.resample(window).agg(
        steps_in_window=("step_increment", "sum"),
        step_samples=("step_count", "count"),
    )
    grouped["side"] = side
    grouped["role"] = SIDE_TO_ROLE[side]
    grouped["window"] = window
    return grouped.reset_index()


def adjusted_cumulative_steps(steps):
    values = steps["step_count"].astype(float)
    adjusted = []
    offset = 0.0
    previous = None
    for value in values:
        if previous is not None and value < previous:
            offset += previous
        adjusted.append(value + offset)
        previous = value
    return pd.Series(adjusted, index=steps.index, name="adjusted_step_count")


def build_uniformized_step_windows(side, window):
    steps = load_step_samples(side)
    cumulative = adjusted_cumulative_steps(steps)
    minute_index = pd.date_range(
        cumulative.index.min().floor("min"),
        cumulative.index.max().ceil("min"),
        freq="1min",
    )
    combined_index = cumulative.index.union(minute_index).sort_values()
    uniform_cumulative = (
        cumulative.reindex(combined_index)
        .interpolate(method="time")
        .reindex(minute_index)
    )
    minute_steps = uniform_cumulative.diff().clip(lower=0).fillna(0)
    minute_table = pd.DataFrame({"steps_in_minute": minute_steps})
    grouped = minute_table.resample(window).agg(
        steps_in_window=("steps_in_minute", "sum"),
        step_samples=("steps_in_minute", "count"),
    )
    grouped.index.name = "time"
    grouped["side"] = side
    grouped["role"] = SIDE_TO_ROLE[side]
    grouped["window"] = window
    return grouped.reset_index()


def summarize_thresholds(use_uniformized=False):
    rows = []
    for side in SIDES:
        for window in WINDOWS:
            if use_uniformized:
                step_windows = build_uniformized_step_windows(side, window)
                method = "uniformized_1min_interpolated"
            else:
                step_windows = build_step_windows(side, window)
                method = "raw_valid_windows"
            valid = step_windows.loc[step_windows["step_samples"] > 0].copy()
            total_windows = len(step_windows)
            valid_windows = len(valid)
            missing_windows = total_windows - valid_windows

            for threshold in THRESHOLDS:
                count = int((valid["steps_in_window"] <= threshold).sum())
                proportion = count / valid_windows if valid_windows else np.nan
                count_if_missing_as_zero = count + missing_windows
                proportion_if_missing_as_zero = (
                    count_if_missing_as_zero / total_windows if total_windows else np.nan
                )
                rows.append(
                    {
                        "step_method": method,
                        "side": side,
                        "role": SIDE_TO_ROLE[side],
                        "window": window,
                        "threshold_steps": threshold,
                        "total_resampled_windows": total_windows,
                        "valid_step_windows": valid_windows,
                        "missing_step_windows": missing_windows,
                        "count_steps_lte_threshold": count,
                        "proportion_steps_lte_threshold": proportion,
                        "count_steps_lte_threshold_if_missing_as_zero": (
                            count_if_missing_as_zero
                        ),
                        "proportion_steps_lte_threshold_if_missing_as_zero": (
                            proportion_if_missing_as_zero
                        ),
                        "mean_steps_per_valid_window": valid["steps_in_window"].mean(),
                        "median_steps_per_valid_window": valid[
                            "steps_in_window"
                        ].median(),
                        "p75_steps_per_valid_window": valid["steps_in_window"].quantile(
                            0.75
                        ),
                        "p90_steps_per_valid_window": valid["steps_in_window"].quantile(
                            0.90
                        ),
                        "max_steps_per_valid_window": valid["steps_in_window"].max(),
                    }
                )
    return pd.DataFrame(rows)


def plot_threshold_summary(summary, figure_path, title_suffix):
    fig, axes = plt.subplots(len(WINDOWS), 1, figsize=(10, 13), sharex=True)
    for ax, window in zip(axes, WINDOWS):
        subset = summary.loc[summary["window"] == window]
        pivot = subset.pivot(
            index="threshold_steps",
            columns="role",
            values="proportion_steps_lte_threshold",
        )
        pivot.plot(kind="bar", ax=ax, width=0.75)
        ax.set_title(f"{window} step windows: proportion at or below threshold")
        ax.set_ylabel("Proportion")
        ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="")
        for container in ax.containers:
            ax.bar_label(container, fmt="%.2f", fontsize=8, padding=2)
    axes[-1].set_xlabel("Step threshold")
    fig.suptitle(
        f"Home_X001 ForthPhase: Step threshold coverage by window size ({title_suffix})",
        y=1.0,
    )
    fig.tight_layout()
    fig.savefig(figure_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    summary = summarize_thresholds(use_uniformized=False)
    uniformized_summary = summarize_thresholds(use_uniformized=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    uniformized_summary.to_csv(UNIFORMIZED_SUMMARY_PATH, index=False)
    plot_threshold_summary(summary, FIGURE_PATH, "raw valid windows")
    plot_threshold_summary(
        uniformized_summary,
        UNIFORMIZED_FIGURE_PATH,
        "1min interpolated cumulative steps",
    )

    print("Step threshold coverage by window size: raw valid windows")
    print(
        summary[
            [
                "step_method",
                "role",
                "window",
                "threshold_steps",
                "valid_step_windows",
                "missing_step_windows",
                "count_steps_lte_threshold",
                "proportion_steps_lte_threshold",
                "proportion_steps_lte_threshold_if_missing_as_zero",
                "median_steps_per_valid_window",
                "p90_steps_per_valid_window",
            ]
        ].to_string(index=False)
    )
    print("\nStep threshold coverage by window size: 1min interpolated cumulative steps")
    print(
        uniformized_summary[
            [
                "step_method",
                "role",
                "window",
                "threshold_steps",
                "valid_step_windows",
                "missing_step_windows",
                "count_steps_lte_threshold",
                "proportion_steps_lte_threshold",
                "median_steps_per_valid_window",
                "p90_steps_per_valid_window",
            ]
        ].to_string(index=False)
    )
    print("\nSaved outputs:")
    print(SUMMARY_PATH)
    print(UNIFORMIZED_SUMMARY_PATH)
    print(FIGURE_PATH)
    print(UNIFORMIZED_FIGURE_PATH)


if __name__ == "__main__":
    main()
