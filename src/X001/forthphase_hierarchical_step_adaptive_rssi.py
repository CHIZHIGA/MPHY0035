import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forthphase_fixed_rssi_window_comparison import (
    RESULTS_DIR,
    SIDES,
    SIDE_TO_ROLE,
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
    build_rssi_windows,
    classify_state,
    load_rssi_samples,
)
from forthphase_step_threshold_diagnostics import build_uniformized_step_windows


WINDOWS = ["1min", "5min", "10min", "30min"]
WINDOW_PRIORITY = ["30min", "10min", "5min"]
THRESHOLDS = [1, 2, 5, 10]

TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_rssi_timeline.csv",
)
WINDOW_DISTRIBUTION_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_window_distribution.csv",
)
COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_copresence_summary.csv",
)
COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_comparison.csv",
)

WINDOW_DISTRIBUTION_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_window_distribution.png",
)
COPRESENCE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_copresence_summary.png",
)
COMPARISON_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_comparison.png",
)


def transition_count_for_locations(locations):
    clean = locations.fillna("Missing")
    return max(int(clean.ne(clean.shift()).sum() - 1), 0)


def build_rssi_feature_tables():
    rows = []
    for side in SIDES:
        print(f"Loading RSSI data for {side}...")
        samples = load_rssi_samples(side)
        for window in WINDOWS:
            print(f"  Building {window} RSSI windows...")
            rows.append(build_rssi_windows(side, samples, window))
    return pd.concat(rows, ignore_index=True)


def build_step_feature_tables():
    rows = []
    for side in SIDES:
        print(f"Building uniformized step windows for {side}...")
        for window in WINDOWS:
            rows.append(build_uniformized_step_windows(side, window))
    return pd.concat(rows, ignore_index=True)


def common_1min_index(rssi_features, step_features):
    starts = []
    ends = []
    for role in ["SUBJECT", "STUDY_PARTNER"]:
        role_rssi = rssi_features.loc[
            (rssi_features["role"] == role) & (rssi_features["window"] == "1min"),
            "time",
        ]
        role_step = step_features.loc[
            (step_features["role"] == role) & (step_features["window"] == "1min"),
            "time",
        ]
        starts.append(max(role_rssi.min(), role_step.min()))
        ends.append(min(role_rssi.max(), role_step.max()))
    return pd.date_range(max(starts).floor("min"), min(ends).floor("min"), freq="1min")


def align_rssi_table(rssi_features, role, window, common_index):
    columns = [
        "strongest_beacon",
        "strongest_location",
        "estimated_in_home",
        "rssi_confidence_score",
        "strongest_beacon_proportion",
        "strongest_second_gap",
        "total_rssi_samples",
    ]
    table = (
        rssi_features.loc[
            (rssi_features["role"] == role) & (rssi_features["window"] == window)
        ]
        .sort_values("time")
        .set_index("time")
    )
    aligned = table.reindex(common_index.floor(window))[columns]
    aligned.index = common_index
    aligned["estimated_in_home"] = aligned["estimated_in_home"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )
    return aligned


def align_step_table(step_features, role, window, common_index):
    table = (
        step_features.loc[
            (step_features["role"] == role) & (step_features["window"] == window)
        ]
        .sort_values("time")
        .set_index("time")
    )
    aligned = table.reindex(common_index.floor(window))[["steps_in_window"]]
    aligned.index = common_index
    return aligned["steps_in_window"]


def choose_window(row, threshold):
    for window in WINDOW_PRIORITY:
        value = row[f"steps_{window}"]
        if pd.notna(value) and value <= threshold:
            return window
    return "1min"


def build_role_timeline(rssi_features, step_features, role, threshold, common_index):
    rssi_by_window = {
        window: align_rssi_table(rssi_features, role, window, common_index)
        for window in WINDOWS
    }
    step_by_window = {
        window: align_step_table(step_features, role, window, common_index)
        for window in WINDOWS
    }

    base = pd.DataFrame(index=common_index)
    for window in WINDOWS:
        base[f"steps_{window}"] = step_by_window[window]
    base["selected_window"] = base.apply(
        lambda row: choose_window(row, threshold),
        axis=1,
    )
    base["possible_transition"] = base["selected_window"].eq("1min")

    rows = []
    for timestamp, row in base.iterrows():
        window = row["selected_window"]
        source = rssi_by_window[window].loc[timestamp]
        rows.append(
            {
                "time": timestamp,
                "role": role,
                "threshold_steps": threshold,
                "selected_window": window,
                "possible_transition": bool(row["possible_transition"]),
                "steps_1min": row["steps_1min"],
                "steps_5min": row["steps_5min"],
                "steps_10min": row["steps_10min"],
                "steps_30min": row["steps_30min"],
                "strongest_beacon": source["strongest_beacon"],
                "strongest_location": source["strongest_location"],
                "estimated_in_home": bool(source["estimated_in_home"]),
                "rssi_confidence_score": source["rssi_confidence_score"],
                "strongest_beacon_proportion": source[
                    "strongest_beacon_proportion"
                ],
                "strongest_second_gap": source["strongest_second_gap"],
                "total_rssi_samples": source["total_rssi_samples"],
            }
        )
    return pd.DataFrame(rows)


def build_threshold_timeline(rssi_features, step_features, threshold, common_index):
    role_rows = [
        build_role_timeline(rssi_features, step_features, role, threshold, common_index)
        for role in ["SUBJECT", "STUDY_PARTNER"]
    ]
    role_data = pd.concat(role_rows, ignore_index=True)
    subject = (
        role_data.loc[role_data["role"] == "SUBJECT"]
        .sort_values("time")
        .set_index("time")
        .add_prefix("subject_")
    )
    partner = (
        role_data.loc[role_data["role"] == "STUDY_PARTNER"]
        .sort_values("time")
        .set_index("time")
        .add_prefix("study_partner_")
    )
    timeline = subject.join(partner, how="inner")
    timeline["threshold_steps"] = threshold
    timeline["copresence_state"] = timeline.apply(classify_state, axis=1)
    timeline["copresence_label"] = timeline["copresence_state"].map(STATE_LABELS)
    timeline["minimum_rssi_confidence"] = timeline[
        ["subject_rssi_confidence_score", "study_partner_rssi_confidence_score"]
    ].min(axis=1)
    return timeline.reset_index().rename(columns={"index": "time"})


def build_all_timelines(rssi_features, step_features):
    common_index = common_1min_index(rssi_features, step_features)
    timelines = []
    for threshold in THRESHOLDS:
        print(f"Building hierarchical adaptive timeline for threshold <= {threshold}...")
        timelines.append(
            build_threshold_timeline(rssi_features, step_features, threshold, common_index)
        )
    return pd.concat(timelines, ignore_index=True)


def summarize_window_distribution(timeline):
    rows = []
    for threshold, group in timeline.groupby("threshold_steps"):
        for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
            counts = group[f"{prefix}_selected_window"].value_counts()
            total = counts.sum()
            for window in WINDOWS:
                rows.append(
                    {
                        "threshold_steps": threshold,
                        "role": role,
                        "selected_window": window,
                        "windows": int(counts.get(window, 0)),
                        "fraction": counts.get(window, 0) / total if total else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def summarize_copresence(timeline):
    rows = []
    for threshold, group in timeline.groupby("threshold_steps"):
        counts = group["copresence_state"].value_counts()
        total = len(group)
        for state in STATE_ORDER:
            windows = int(counts.get(state, 0))
            rows.append(
                {
                    "method": "hierarchical_step_adaptive_rssi",
                    "threshold_steps": threshold,
                    "copresence_state": state,
                    "copresence_label": STATE_LABELS[state],
                    "windows": windows,
                    "hours": windows / 60,
                    "percentage_of_shared_time": windows / total if total else np.nan,
                    "total_shared_windows": total,
                    "total_shared_hours": total / 60,
                }
            )
    return pd.DataFrame(rows)


def summarize_comparison(timeline):
    rows = []
    for threshold, group in timeline.groupby("threshold_steps"):
        for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
            location = group[f"{prefix}_strongest_location"].fillna("Missing")
            transitions = transition_count_for_locations(location)
            hours = len(group) / 60
            rows.append(
                {
                    "method": "hierarchical_step_adaptive_rssi",
                    "threshold_steps": threshold,
                    "role": role,
                    "shared_timeline_windows": len(group),
                    "estimated_in_home_fraction": group[
                        f"{prefix}_estimated_in_home"
                    ].mean(),
                    "mean_rssi_confidence_score": group[
                        f"{prefix}_rssi_confidence_score"
                    ].mean(),
                    "median_rssi_confidence_score": group[
                        f"{prefix}_rssi_confidence_score"
                    ].median(),
                    "location_transition_count": transitions,
                    "location_transitions_per_hour": transitions / hours
                    if hours
                    else np.nan,
                    "possible_transition_fraction": group[
                        f"{prefix}_possible_transition"
                    ].mean(),
                }
            )
    return pd.DataFrame(rows)


def plot_window_distribution(summary):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    colors = {
        "1min": "#e45756",
        "5min": "#f58518",
        "10min": "#72b7b2",
        "30min": "#4c78a8",
    }
    for ax, role in zip(axes, ["SUBJECT", "STUDY_PARTNER"]):
        subset = summary.loc[summary["role"] == role]
        pivot = subset.pivot(
            index="threshold_steps",
            columns="selected_window",
            values="fraction",
        ).reindex(columns=WINDOWS)
        bottom = np.zeros(len(pivot))
        x = np.arange(len(pivot))
        for window in WINDOWS:
            values = pivot[window].fillna(0).values
            ax.bar(x, values, bottom=bottom, label=window, color=colors[window])
            bottom += values
        ax.set_title(role)
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index)
        ax.set_xlabel("Step threshold")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Fraction of 1min timeline")
    axes[1].legend(title="Selected RSSI window", loc="center left", bbox_to_anchor=(1, 0.5))
    fig.suptitle("Home_X001 ForthPhase: Hierarchical step-adaptive window choice")
    fig.tight_layout()
    fig.savefig(WINDOW_DISTRIBUTION_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_copresence(summary):
    pivot = summary.pivot(
        index="threshold_steps",
        columns="copresence_state",
        values="hours",
    ).reindex(columns=STATE_ORDER)
    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for state in STATE_ORDER:
        values = pivot[state].fillna(0).values
        ax.bar(x, values, bottom=bottom, color=STATE_COLORS[state], label=STATE_LABELS[state])
        bottom += values
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_xlabel("Step threshold")
    ax.set_ylabel("Hours")
    ax.set_title("Home_X001 ForthPhase: Hierarchical adaptive co-presence summary")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    fig.tight_layout()
    fig.savefig(COPRESENCE_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_comparison(comparison):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    metrics = [
        ("mean_rssi_confidence_score", "Mean RSSI confidence"),
        ("location_transitions_per_hour", "Location transitions per hour"),
        ("possible_transition_fraction", "1min selected fraction"),
    ]
    for ax, (metric, title) in zip(axes, metrics):
        pivot = comparison.pivot(
            index="threshold_steps",
            columns="role",
            values=metric,
        )
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("Step threshold")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="")
    fig.suptitle("Home_X001 ForthPhase: Hierarchical step-adaptive RSSI comparison")
    fig.tight_layout()
    fig.savefig(COMPARISON_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    rssi_features = build_rssi_feature_tables()
    step_features = build_step_feature_tables()
    timeline = build_all_timelines(rssi_features, step_features)
    window_distribution = summarize_window_distribution(timeline)
    copresence = summarize_copresence(timeline)
    comparison = summarize_comparison(timeline)

    timeline.to_csv(TIMELINE_PATH, index=False)
    window_distribution.to_csv(WINDOW_DISTRIBUTION_PATH, index=False)
    copresence.to_csv(COPRESENCE_PATH, index=False)
    comparison.to_csv(COMPARISON_PATH, index=False)

    plot_window_distribution(window_distribution)
    plot_copresence(copresence)
    plot_comparison(comparison)

    print("\nWindow selection distribution:")
    print(window_distribution.to_string(index=False))
    print("\nCo-presence summary:")
    print(copresence.to_string(index=False))
    print("\nComparison summary:")
    print(comparison.to_string(index=False))
    print("\nSaved outputs:")
    for path in [
        TIMELINE_PATH,
        WINDOW_DISTRIBUTION_PATH,
        COPRESENCE_PATH,
        COMPARISON_PATH,
        WINDOW_DISTRIBUTION_FIG,
        COPRESENCE_FIG,
        COMPARISON_FIG,
    ]:
        print(path)


if __name__ == "__main__":
    main()
