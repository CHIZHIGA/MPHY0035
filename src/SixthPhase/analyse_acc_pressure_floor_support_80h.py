import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "New data- 80 hour single user" / "559662"
RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ACC_PATH = DATA_DIR / "HE_ACC.csv"
FLOOR_TIMELINE_PATH = RESULTS_DIR / "new80h_pressure_inferred_floor_timeline_5min.csv"
FLOOR_SEGMENTS_PATH = RESULTS_DIR / "new80h_pressure_inferred_floor_segments.csv"

ACC_FEATURES_OUTPUT = RESULTS_DIR / "new80h_acc_5min_features.csv"
SHIFT_SUPPORT_OUTPUT = RESULTS_DIR / "new80h_pressure_floor_shift_acc_support.csv"
ACC_SUPPORT_PLOT_OUTPUT = RESULTS_DIR / "new80h_pressure_floor_acc_support_timeline.png"

ACC_SPIKE_THRESHOLD = 1.2
ACC_SPIKE_REPLACEMENT = 1.0
ACC_SHIFT_STD_THRESHOLD = 0.010
SHIFT_SUPPORT_WINDOW_ROWS = 1


def load_timestamp_csv(path):
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).copy()
    frame["time"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.sort_values("time")


def load_floor_timeline():
    return pd.read_csv(FLOOR_TIMELINE_PATH, parse_dates=["time"]).sort_values("time")


def build_acc_5min_features(acc):
    acc_frame = acc[["time", "MAGNITUDE"]].copy()
    acc_frame["acc_magnitude_raw"] = pd.to_numeric(
        acc_frame["MAGNITUDE"], errors="coerce"
    )
    acc_frame["acc_spike_gt_1p2"] = acc_frame["acc_magnitude_raw"].gt(
        ACC_SPIKE_THRESHOLD
    )
    acc_frame["acc_magnitude_clean"] = acc_frame["acc_magnitude_raw"].mask(
        acc_frame["acc_spike_gt_1p2"], ACC_SPIKE_REPLACEMENT
    )
    acc_frame["window_start"] = acc_frame["time"].dt.floor("5min")

    features = (
        acc_frame.groupby("window_start")
        .agg(
            acc_magnitude_mean_clean=("acc_magnitude_clean", "mean"),
            acc_magnitude_std_clean=("acc_magnitude_clean", "std"),
            acc_magnitude_max_raw=("acc_magnitude_raw", "max"),
            acc_spike_count_gt_1p2=("acc_spike_gt_1p2", "sum"),
            acc_samples=("acc_magnitude_raw", "count"),
        )
        .reset_index()
        .rename(columns={"window_start": "time"})
    )
    features["acc_magnitude_std_clean"] = features[
        "acc_magnitude_std_clean"
    ].fillna(0)
    features["acc_motion_score"] = features["acc_magnitude_std_clean"]
    features["acc_high_motion_window"] = features["acc_motion_score"].ge(
        ACC_SHIFT_STD_THRESHOLD
    ) | features["acc_spike_count_gt_1p2"].gt(0)
    return features


def build_shift_support_table(floor_timeline, acc_features):
    merged = floor_timeline.merge(acc_features, on="time", how="left")
    floor_col = "pressure_inferred_floor_smoothed_label"
    previous_floor = merged[floor_col].shift()
    comparable_floor = merged[floor_col].fillna("__missing_floor__")
    merged["pressure_floor_shift"] = (
        merged[floor_col].notna()
        & previous_floor.notna()
        & comparable_floor.ne(comparable_floor.shift())
        & merged["time"].diff().eq(pd.Timedelta(minutes=5))
    )

    rows = []
    for row_index in merged.index[merged["pressure_floor_shift"].fillna(False)]:
        start_index = max(0, row_index - SHIFT_SUPPORT_WINDOW_ROWS)
        end_index = min(len(merged) - 1, row_index + SHIFT_SUPPORT_WINDOW_ROWS)
        support_window = merged.iloc[start_index : end_index + 1]
        acc_supported = bool(
            support_window["acc_motion_score"].ge(ACC_SHIFT_STD_THRESHOLD).any()
            or support_window["acc_spike_count_gt_1p2"].fillna(0).gt(0).any()
        )
        previous_floor = merged.loc[row_index - 1, floor_col] if row_index > 0 else pd.NA
        current_floor = merged.loc[row_index, floor_col]
        rows.append(
            {
                "shift_time": merged.loc[row_index, "time"],
                "previous_floor": previous_floor,
                "current_floor": current_floor,
                "support_window_start": support_window["time"].iloc[0],
                "support_window_end": support_window["time"].iloc[-1],
                "max_acc_motion_score": support_window["acc_motion_score"].max(),
                "max_acc_magnitude_raw": support_window["acc_magnitude_max_raw"].max(),
                "total_acc_spike_count_gt_1p2": int(
                    support_window["acc_spike_count_gt_1p2"].fillna(0).sum()
                ),
                "floor_shift_acc_supported": acc_supported,
                "unsupported_floor_shift_candidate": not acc_supported,
                "support_reason": "acc_supported"
                if acc_supported
                else "no_high_acc_in_shift_window",
            }
        )
    return pd.DataFrame(rows)


def plot_acc_pressure_floor_support(floor_timeline, acc_features, shift_support):
    merged = floor_timeline.merge(acc_features, on="time", how="left")
    floor_to_y = {"1F": 1, "2F": 2}
    y_values = merged["pressure_inferred_floor_smoothed_label"].map(floor_to_y)

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(13.5, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.1, 1.2, 1.2]},
    )

    axes[0].step(
        merged["time"],
        y_values,
        where="mid",
        color="black",
        linewidth=1.3,
        label="Smoothed pressure floor",
    )
    axes[0].scatter(
        merged["time"],
        merged["pressure_inferred_floor_label"].map(floor_to_y),
        c=merged["pressure_floor_confidence"],
        cmap="viridis",
        vmin=0,
        vmax=1,
        s=15,
        label="5-min pressure floor vote",
    )
    axes[0].set_yticks([1, 2])
    axes[0].set_yticklabels(["1F: CA59/1933", "2F: D7FD/3E05"])
    axes[0].set_ylim(0.6, 2.4)
    axes[0].set_ylabel("Floor")
    axes[0].set_title("ACC support for pressure-inferred floor shifts")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[0].grid(axis="x", alpha=0.2)

    axes[1].plot(
        merged["time"],
        merged["acc_magnitude_mean_clean"],
        linewidth=1.0,
        label="Clean ACC magnitude mean",
    )
    axes[1].plot(
        merged["time"],
        merged["acc_magnitude_max_raw"],
        linewidth=0.8,
        alpha=0.7,
        label="Raw ACC magnitude max",
    )
    axes[1].axhline(
        ACC_SPIKE_THRESHOLD,
        color="#b91c1c",
        linestyle="--",
        linewidth=0.9,
        label="Raw spike threshold 1.2",
    )
    axes[1].set_ylabel("ACC magnitude")
    axes[1].legend(fontsize=8, ncol=3)
    axes[1].grid(alpha=0.2)

    axes[2].plot(
        merged["time"],
        merged["acc_motion_score"],
        color="#4c78a8",
        linewidth=1.0,
        label="ACC motion score (clean std)",
    )
    axes[2].axhline(
        ACC_SHIFT_STD_THRESHOLD,
        color="#2ca02c",
        linestyle="--",
        linewidth=1.0,
        label=f"Shift support threshold {ACC_SHIFT_STD_THRESHOLD:.3f}",
    )
    axes[2].set_ylabel("ACC clean std")
    axes[2].set_xlabel("Time")
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.2)

    unsupported_index = 1
    for _, shift in shift_support.iterrows():
        is_supported = bool(shift["floor_shift_acc_supported"])
        color = "#15803d" if is_supported else "#b91c1c"
        alpha = 0.18 if is_supported else 0.72
        linewidth = 0.8 if is_supported else 1.5
        for ax in axes:
            ax.axvline(
                shift["shift_time"],
                color=color,
                alpha=alpha,
                linewidth=linewidth,
            )

        if not is_supported:
            label = f"U{unsupported_index}"
            axes[0].annotate(
                label,
                xy=(shift["shift_time"], 2.25),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color="#b91c1c",
                bbox={
                    "boxstyle": "round,pad=0.15",
                    "facecolor": "white",
                    "edgecolor": "#b91c1c",
                    "linewidth": 0.8,
                },
            )
            axes[2].scatter(
                shift["shift_time"],
                shift["max_acc_motion_score"],
                marker="x",
                s=42,
                color="#b91c1c",
                linewidths=1.3,
                zorder=5,
            )
            axes[2].annotate(
                label,
                xy=(shift["shift_time"], shift["max_acc_motion_score"]),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color="#b91c1c",
            )
            unsupported_index += 1

    shift_handles = [
        Line2D([0], [0], color="#15803d", linewidth=1.0, alpha=0.35),
        Line2D([0], [0], color="#b91c1c", linewidth=1.5, alpha=0.75),
    ]
    axes[0].legend(
        axes[0].get_legend_handles_labels()[0] + shift_handles,
        axes[0].get_legend_handles_labels()[1]
        + ["ACC-supported shift", "Unsupported shift (U labels)"],
        fontsize=8,
        loc="upper left",
    )

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(ACC_SUPPORT_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return ACC_SUPPORT_PLOT_OUTPUT


def main():
    acc = load_timestamp_csv(ACC_PATH)
    floor_timeline = load_floor_timeline()
    if FLOOR_SEGMENTS_PATH.exists():
        pd.read_csv(FLOOR_SEGMENTS_PATH)

    acc_features = build_acc_5min_features(acc)
    shift_support = build_shift_support_table(floor_timeline, acc_features)

    acc_features.to_csv(ACC_FEATURES_OUTPUT, index=False)
    shift_support.to_csv(SHIFT_SUPPORT_OUTPUT, index=False)
    plot_output = plot_acc_pressure_floor_support(
        floor_timeline, acc_features, shift_support
    )

    print("ACC pressure-floor support analysis complete")
    print("Saved outputs:")
    for output in [ACC_FEATURES_OUTPUT, SHIFT_SUPPORT_OUTPUT, plot_output]:
        print(output)
    print("\nACC spike summary:")
    print(
        acc_features[
            ["acc_spike_count_gt_1p2", "acc_magnitude_max_raw"]
        ].agg({"acc_spike_count_gt_1p2": "sum", "acc_magnitude_max_raw": "max"})
    )
    print("\nFloor shift ACC support summary:")
    if shift_support.empty:
        print("No pressure floor shifts found")
    else:
        print(
            shift_support["floor_shift_acc_supported"]
            .value_counts(dropna=False)
            .rename_axis("acc_supported")
            .reset_index(name="shift_count")
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
