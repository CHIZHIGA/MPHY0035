import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forthphase_fixed_rssi_window_comparison import (
    RESULTS_DIR,
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
)


FIXED_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_copresence_timeline.csv",
)
ADAPTIVE_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_rssi_timeline.csv",
)
CLUSTER_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_timeline.csv",
)
FIXED_COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_copresence_summary.csv",
)
ADAPTIVE_COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_copresence_summary.csv",
)
CLUSTER_COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_copresence_summary.csv",
)

MAIN_TIMELINE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_integrated_main_4b_timeline.png",
)
METHOD_TIMELINE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_integrated_method_comparison_timeline.png",
)
COPRESENCE_COMPARISON_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_integrated_copresence_summary_comparison.png",
)
MOVEMENT_CONFIDENCE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_integrated_movement_confidence_context.png",
)
SUMMARY_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_integrated_visualisation_summary.csv",
)


LOCATION_COLORS = {
    "Bathroom": "#4c78a8",
    "Bedroom": "#f58518",
    "Dining": "#54a24b",
    "Kitchen": "#e45756",
    "Living": "#72b7b2",
    "Office": "#b279a2",
    "Other 1": "#ff9da6",
    "Unmapped": "#9d9da1",
}
WINDOW_ORDER = ["1min", "5min", "10min", "30min"]
WINDOW_TO_Y = {window: index for index, window in enumerate(WINDOW_ORDER)}


def read_time_csv(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    return df


def location_palette(values):
    palette = dict(LOCATION_COLORS)
    fallback = plt.get_cmap("tab20")
    for value in sorted(set(values)):
        if pd.isna(value):
            continue
        if value not in palette:
            palette[value] = fallback(len(palette) % 20)
    return palette


def plot_categorical_timeline(ax, df, column, title, palette, y=0):
    for value, group in df.groupby(column, dropna=False):
        label = "Unmapped" if pd.isna(value) else value
        ax.scatter(
            group["time"],
            np.full(len(group), y),
            s=12,
            color=palette.get(label, "#9d9da1"),
            marker="s",
            label=label,
        )
    ax.set_title(title, loc="left")
    ax.set_yticks([])
    ax.grid(axis="x", alpha=0.2)


def format_time_axis(ax):
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    ax.grid(axis="x", which="minor", alpha=0.08)


def load_main_adaptive():
    adaptive = read_time_csv(ADAPTIVE_TIMELINE_PATH)
    return adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()


def plot_main_4b_timeline(adaptive):
    locations = pd.concat(
        [
            adaptive["subject_strongest_location"].fillna("Unmapped"),
            adaptive["study_partner_strongest_location"].fillna("Unmapped"),
        ],
        ignore_index=True,
    )
    palette = location_palette(locations)
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(15, 8.5),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1, 1.2, 1]},
    )
    plot_categorical_timeline(
        axes[0],
        adaptive,
        "subject_strongest_location",
        "SUBJECT estimated location, 4b hierarchical step-adaptive RSSI",
        palette,
    )
    plot_categorical_timeline(
        axes[1],
        adaptive,
        "study_partner_strongest_location",
        "STUDY_PARTNER estimated location, 4b hierarchical step-adaptive RSSI",
        palette,
    )

    state_palette = {STATE_LABELS[state]: STATE_COLORS[state] for state in STATE_ORDER}
    plot_categorical_timeline(
        axes[2],
        adaptive,
        "copresence_label",
        "Co-presence state",
        state_palette,
    )

    axes[3].plot(
        adaptive["time"],
        adaptive["subject_rssi_confidence_score"],
        label="SUBJECT confidence",
        linewidth=0.8,
    )
    axes[3].plot(
        adaptive["time"],
        adaptive["study_partner_rssi_confidence_score"],
        label="STUDY_PARTNER confidence",
        linewidth=0.8,
    )
    axes[3].set_ylim(0, 1)
    axes[3].set_ylabel("RSSI confidence")
    axes[3].set_title("RSSI confidence", loc="left")
    axes[3].legend(loc="upper right", ncol=2)
    axes[3].grid(alpha=0.25)

    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes[0].legend(
        by_label.values(),
        by_label.keys(),
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        title="Location",
    )
    for ax in axes:
        format_time_axis(ax)
    fig.suptitle("Home_X001 ForthPhase Point 5: Main movement-aware location timeline")
    fig.tight_layout()
    fig.savefig(MAIN_TIMELINE_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def prepare_method_state_rows():
    fixed = read_time_csv(FIXED_TIMELINE_PATH)
    fixed = fixed.loc[fixed["window"].eq("30min")].copy()
    fixed["method"] = "4a fixed 30min RSSI"
    fixed = fixed[["time", "method", "copresence_label"]]

    adaptive = load_main_adaptive()
    adaptive["method"] = "4b step-adaptive RSSI"
    adaptive = adaptive[["time", "method", "copresence_label"]]

    cluster = read_time_csv(CLUSTER_TIMELINE_PATH)
    cluster["method"] = "4c low-motion clustering"
    cluster = cluster[["time", "method", "copresence_label"]]

    return pd.concat([fixed, adaptive, cluster], ignore_index=True)


def plot_method_comparison_timeline():
    rows = prepare_method_state_rows()
    methods = [
        "4a fixed 30min RSSI",
        "4b step-adaptive RSSI",
        "4c low-motion clustering",
    ]
    state_palette = {STATE_LABELS[state]: STATE_COLORS[state] for state in STATE_ORDER}
    fig, axes = plt.subplots(3, 1, figsize=(15, 6.8), sharex=True)
    for ax, method in zip(axes, methods):
        subset = rows.loc[rows["method"].eq(method)]
        plot_categorical_timeline(
            ax,
            subset,
            "copresence_label",
            method,
            state_palette,
        )
        format_time_axis(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes[0].legend(
        by_label.values(),
        by_label.keys(),
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        title="Co-presence",
    )
    fig.suptitle("Home_X001 ForthPhase Point 5: Method comparison timeline")
    fig.tight_layout()
    fig.savefig(METHOD_TIMELINE_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def load_copresence_summary_for_plot():
    fixed = pd.read_csv(FIXED_COPRESENCE_PATH)
    fixed = fixed.loc[fixed["window"].eq("30min")].copy()
    fixed["method_label"] = "4a fixed 30min RSSI"

    adaptive = pd.read_csv(ADAPTIVE_COPRESENCE_PATH)
    adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
    adaptive["method_label"] = "4b step-adaptive RSSI"

    cluster = pd.read_csv(CLUSTER_COPRESENCE_PATH)
    cluster["method_label"] = "4c low-motion clustering"

    return pd.concat([fixed, adaptive, cluster], ignore_index=True)


def plot_copresence_comparison():
    summary = load_copresence_summary_for_plot()
    method_order = [
        "4a fixed 30min RSSI",
        "4b step-adaptive RSSI",
        "4c low-motion clustering",
    ]
    pivot = summary.pivot(
        index="method_label",
        columns="copresence_state",
        values="hours",
    ).reindex(index=method_order, columns=STATE_ORDER)

    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for state in STATE_ORDER:
        values = pivot[state].fillna(0).values
        ax.bar(
            x,
            values,
            bottom=bottom,
            color=STATE_COLORS[state],
            label=STATE_LABELS[state],
        )
        bottom += values
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=15, ha="right")
    ax.set_ylabel("Hours")
    ax.set_title("Home_X001 ForthPhase Point 5: Co-presence summary comparison")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    fig.savefig(COPRESENCE_COMPARISON_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return summary


def plot_movement_confidence_context(adaptive):
    fig, axes = plt.subplots(4, 1, figsize=(15, 8.5), sharex=True)
    axes[0].plot(
        adaptive["time"],
        adaptive["subject_steps_30min"],
        label="SUBJECT 30min steps",
        linewidth=0.8,
    )
    axes[0].plot(
        adaptive["time"],
        adaptive["study_partner_steps_30min"],
        label="STUDY_PARTNER 30min steps",
        linewidth=0.8,
    )
    axes[0].axhline(10, linestyle="--", color="black", linewidth=0.8, label="threshold 10")
    axes[0].set_ylabel("Steps")
    axes[0].set_title("30min step count context", loc="left")
    axes[0].legend(loc="upper right", ncol=3)
    axes[0].grid(alpha=0.25)

    for ax, prefix, title in [
        (axes[1], "subject", "SUBJECT selected RSSI window"),
        (axes[2], "study_partner", "STUDY_PARTNER selected RSSI window"),
    ]:
        ax.scatter(
            adaptive["time"],
            adaptive[f"{prefix}_selected_window"].map(WINDOW_TO_Y),
            s=8,
            c=adaptive[f"{prefix}_selected_window"].map(
                {
                    "1min": "#e45756",
                    "5min": "#f58518",
                    "10min": "#72b7b2",
                    "30min": "#4c78a8",
                }
            ),
            marker="s",
        )
        ax.set_yticks(list(WINDOW_TO_Y.values()))
        ax.set_yticklabels(WINDOW_ORDER)
        ax.set_title(title, loc="left")
        ax.grid(axis="x", alpha=0.2)

    axes[3].plot(
        adaptive["time"],
        adaptive["minimum_rssi_confidence"],
        color="#4c78a8",
        linewidth=0.8,
    )
    axes[3].set_ylim(0, 1)
    axes[3].set_ylabel("Min confidence")
    axes[3].set_title("Minimum RSSI confidence across the two people", loc="left")
    axes[3].grid(alpha=0.25)

    for ax in axes:
        format_time_axis(ax)
    fig.suptitle("Home_X001 ForthPhase Point 5: Movement and confidence context")
    fig.tight_layout()
    fig.savefig(MOVEMENT_CONFIDENCE_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_summary(copresence_summary):
    keep = copresence_summary[
        ["method_label", "copresence_label", "hours", "percentage_of_shared_time"]
    ].copy()
    keep.to_csv(SUMMARY_PATH, index=False)


def main():
    adaptive = load_main_adaptive()
    plot_main_4b_timeline(adaptive)
    plot_method_comparison_timeline()
    copresence_summary = plot_copresence_comparison()
    plot_movement_confidence_context(adaptive)
    save_summary(copresence_summary)

    print("Saved integrated visualisation outputs:")
    for path in [
        MAIN_TIMELINE_FIG,
        METHOD_TIMELINE_FIG,
        COPRESENCE_COMPARISON_FIG,
        MOVEMENT_CONFIDENCE_FIG,
        SUMMARY_PATH,
    ]:
        print(path)


if __name__ == "__main__":
    main()
