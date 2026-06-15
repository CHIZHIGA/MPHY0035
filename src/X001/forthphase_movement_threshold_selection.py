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
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
    build_rssi_windows,
    classify_state,
    load_rssi_samples,
)


RSSI_WINDOWS = ["1min", "5min", "10min", "30min"]
STATIONARY_CANDIDATES = [1, 2, 5, 10]
DEFAULT_STATIONARY_THRESHOLD = 5

STATIONARY_COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_stationary_threshold_comparison.csv",
)
MOVEMENT_THRESHOLDS_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_movement_state_thresholds.csv",
)
MOVEMENT_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_movement_state_timeline.csv",
)
ADAPTIVE_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_adaptive_step_rssi_timeline.csv",
)
ADAPTIVE_COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_adaptive_step_rssi_copresence_summary.csv",
)
ADAPTIVE_COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_adaptive_step_rssi_comparison.csv",
)
STATIONARY_SELECTION_SCORE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_stationary_threshold_selection_score.csv",
)
FIXED_WINDOW_COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_comparison.csv",
)

STATIONARY_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_stationary_threshold_comparison.png",
)
MOVEMENT_STATE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_movement_state_distribution.png",
)
WINDOW_CHOICE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_adaptive_selected_window_distribution.png",
)
ADAPTIVE_COPRESENCE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_adaptive_step_rssi_copresence_summary.png",
)
ADAPTIVE_COMPARISON_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_adaptive_step_rssi_confidence_transition_comparison.png",
)

MOVEMENT_STATES = ["stationary", "low_movement", "active", "high_activity"]
MOVEMENT_COLORS = {
    "stationary": "#4c78a8",
    "low_movement": "#72b7b2",
    "active": "#f58518",
    "high_activity": "#e45756",
}
WINDOW_FOR_STATE = {
    "stationary": "30min",
    "low_movement": "10min",
    "active": "5min",
    "high_activity": "1min",
}


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
        step_resets=("step_reset_flag", "sum"),
    )
    grouped["side"] = side
    grouped["role"] = SIDE_TO_ROLE[side]
    grouped["window"] = window
    return grouped.reset_index()


def build_all_features():
    rssi_features = []
    step_features = []
    for side in SIDES:
        print(f"Loading RSSI and step data for {side}...")
        rssi_samples = load_rssi_samples(side)
        for window in RSSI_WINDOWS:
            print(f"  Building {window} RSSI and step windows...")
            rssi_features.append(build_rssi_windows(side, rssi_samples, window))
            step_features.append(build_step_windows(side, window))

    rssi = pd.concat(rssi_features, ignore_index=True)
    steps = pd.concat(step_features, ignore_index=True)
    features = rssi.merge(
        steps[["time", "side", "window", "steps_in_window", "step_samples"]],
        on=["time", "side", "window"],
        how="outer",
    )
    features["role"] = features["side"].map(SIDE_TO_ROLE)
    features["steps_in_window"] = features["steps_in_window"].fillna(0)
    features["step_samples"] = features["step_samples"].fillna(0)
    features["estimated_in_home"] = features["estimated_in_home"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )
    return features


def common_index_for_window(features, window):
    subset = features.loc[features["window"] == window]
    subject = subset.loc[subset["role"] == "SUBJECT", "time"]
    partner = subset.loc[subset["role"] == "STUDY_PARTNER", "time"]
    common_start = max(subject.min(), partner.min())
    common_end = min(subject.max(), partner.max())
    return pd.date_range(common_start, common_end, freq=window)


def aligned_role_table(features, role, window, common_index):
    keep_cols = [
        "strongest_beacon",
        "strongest_location",
        "estimated_in_home",
        "rssi_confidence_score",
        "strongest_beacon_proportion",
        "strongest_second_gap",
        "total_rssi_samples",
        "steps_in_window",
    ]
    table = (
        features.loc[(features["role"] == role) & (features["window"] == window)]
        .sort_values("time")
        .set_index("time")
        .reindex(common_index)
    )
    table = table[keep_cols]
    table["estimated_in_home"] = table["estimated_in_home"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )
    table["steps_in_window"] = table["steps_in_window"].fillna(0)
    return table


def transition_count_for_locations(locations):
    clean = locations.fillna("Missing")
    return max(int(clean.ne(clean.shift()).sum() - 1), 0)


def build_10min_shared_tables(features):
    common_index = common_index_for_window(features, "10min")
    subject = aligned_role_table(features, "SUBJECT", "10min", common_index)
    partner = aligned_role_table(features, "STUDY_PARTNER", "10min", common_index)
    return common_index, subject, partner


def evaluate_stationary_thresholds(features):
    _, subject, partner = build_10min_shared_tables(features)
    rows = []

    for threshold in STATIONARY_CANDIDATES:
        for role, table in [("SUBJECT", subject), ("STUDY_PARTNER", partner)]:
            stationary = table.loc[table["steps_in_window"] <= threshold]
            rows.append(
                {
                    "threshold_steps": threshold,
                    "role": role,
                    "stationary_windows": len(stationary),
                    "stationary_coverage": len(stationary) / len(table),
                    "mean_steps_stationary": stationary["steps_in_window"].mean(),
                    "mean_rssi_confidence_stationary": stationary[
                        "rssi_confidence_score"
                    ].mean(),
                    "estimated_in_home_fraction_stationary": stationary[
                        "estimated_in_home"
                    ].mean(),
                    "location_transition_count_stationary": transition_count_for_locations(
                        stationary["strongest_location"]
                    ),
                }
            )

    comparison = pd.DataFrame(rows)
    return comparison


def select_stationary_threshold(comparison):
    summary = (
        comparison.groupby("threshold_steps")
        .agg(
            mean_stationary_coverage=("stationary_coverage", "mean"),
            mean_rssi_confidence_stationary=(
                "mean_rssi_confidence_stationary",
                "mean",
            ),
            mean_transition_count_stationary=(
                "location_transition_count_stationary",
                "mean",
            ),
        )
        .reset_index()
    )
    summary["coverage_score"] = 1 - (
        summary["mean_stationary_coverage"] - 0.35
    ).abs()
    summary["confidence_score"] = summary["mean_rssi_confidence_stationary"].rank(
        pct=True,
    )
    summary["transition_score"] = 1 - summary[
        "mean_transition_count_stationary"
    ].rank(pct=True)
    summary["selection_score"] = (
        0.40 * summary["coverage_score"]
        + 0.35 * summary["confidence_score"]
        + 0.25 * summary["transition_score"]
    )

    if summary["selection_score"].notna().any():
        selected = int(
            summary.sort_values(
                ["selection_score", "threshold_steps"],
                ascending=[False, True],
            ).iloc[0]["threshold_steps"]
        )
    else:
        selected = DEFAULT_STATIONARY_THRESHOLD
    return selected, summary


def choose_low_active_cut(non_stationary_steps):
    if non_stationary_steps.empty:
        return np.nan

    median = non_stationary_steps.quantile(0.50)
    q75 = non_stationary_steps.quantile(0.75)
    if median <= non_stationary_steps.min():
        return q75
    return median


def build_movement_thresholds(features, selected_stationary):
    rows = []
    ten_min = features.loc[features["window"] == "10min"].copy()
    for role, group in ten_min.groupby("role"):
        steps = group["steps_in_window"].dropna()
        non_stationary = steps.loc[steps > selected_stationary]
        low_active_cut = choose_low_active_cut(non_stationary)
        high_activity_cut = non_stationary.quantile(0.90) if not non_stationary.empty else np.nan
        rows.append(
            {
                "role": role,
                "stationary_steps_max": selected_stationary,
                "low_movement_steps_max": low_active_cut,
                "active_steps_max": high_activity_cut,
                "high_activity_steps_min": high_activity_cut,
                "threshold_basis": (
                    "selected stationary threshold plus non-stationary "
                    "median/90th percentile"
                ),
            }
        )
    return pd.DataFrame(rows)


def classify_movement_state(steps, thresholds):
    if steps <= thresholds["stationary_steps_max"]:
        return "stationary"
    if steps <= thresholds["low_movement_steps_max"]:
        return "low_movement"
    if steps <= thresholds["active_steps_max"]:
        return "active"
    return "high_activity"


def build_adaptive_role_timeline(features, role, thresholds):
    common_index = common_index_for_window(features, "1min")
    one_min = aligned_role_table(features, role, "1min", common_index)

    aligned_by_window = {
        window: aligned_role_table(features, role, window, common_index.floor(window))
        for window in RSSI_WINDOWS
    }
    for window, table in aligned_by_window.items():
        table.index = common_index
        table = table.add_prefix(f"{window}_")
        aligned_by_window[window] = table

    base = one_min[["steps_in_window"]].rename(columns={"steps_in_window": "steps_1min"})
    ten_min_steps = aligned_by_window["10min"]["10min_steps_in_window"].fillna(0)
    base["steps_10min"] = ten_min_steps
    base["movement_state"] = base["steps_10min"].apply(
        lambda value: classify_movement_state(value, thresholds)
    )
    base["selected_window"] = base["movement_state"].map(WINDOW_FOR_STATE)
    base["possible_transition"] = base["movement_state"].eq("high_activity")

    selected_rows = []
    for timestamp, row in base.iterrows():
        selected_window = row["selected_window"]
        source = aligned_by_window[selected_window].loc[timestamp]
        prefix = f"{selected_window}_"
        selected_rows.append(
            {
                "time": timestamp,
                "role": role,
                "movement_state": row["movement_state"],
                "selected_window": selected_window,
                "possible_transition": bool(row["possible_transition"]),
                "steps_1min": row["steps_1min"],
                "steps_10min": row["steps_10min"],
                "strongest_beacon": source.get(f"{prefix}strongest_beacon"),
                "strongest_location": source.get(f"{prefix}strongest_location"),
                "estimated_in_home": bool(source.get(f"{prefix}estimated_in_home", False)),
                "rssi_confidence_score": source.get(f"{prefix}rssi_confidence_score"),
                "strongest_beacon_proportion": source.get(
                    f"{prefix}strongest_beacon_proportion"
                ),
                "strongest_second_gap": source.get(f"{prefix}strongest_second_gap"),
                "total_rssi_samples": source.get(f"{prefix}total_rssi_samples"),
            }
        )
    return pd.DataFrame(selected_rows)


def build_adaptive_timeline(features, movement_thresholds):
    role_timelines = []
    for _, row in movement_thresholds.iterrows():
        role_timelines.append(build_adaptive_role_timeline(features, row["role"], row))

    role_data = pd.concat(role_timelines, ignore_index=True)
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
    common_index = subject.index.intersection(partner.index).sort_values()
    timeline = subject.loc[common_index].join(partner.loc[common_index], how="inner")
    timeline["copresence_state"] = timeline.apply(classify_state, axis=1)
    timeline["copresence_label"] = timeline["copresence_state"].map(STATE_LABELS)
    timeline["minimum_rssi_confidence"] = timeline[
        ["subject_rssi_confidence_score", "study_partner_rssi_confidence_score"]
    ].min(axis=1)
    return timeline.reset_index().rename(columns={"index": "time"})


def summarize_adaptive_copresence(timeline):
    total_windows = len(timeline)
    minutes_per_window = 1
    counts = timeline["copresence_state"].value_counts()
    rows = []
    for state in STATE_ORDER:
        windows = int(counts.get(state, 0))
        rows.append(
            {
                "method": "adaptive_step_rssi",
                "copresence_state": state,
                "copresence_label": STATE_LABELS[state],
                "windows": windows,
                "hours": windows * minutes_per_window / 60,
                "percentage_of_shared_time": windows / total_windows
                if total_windows
                else np.nan,
                "total_shared_windows": total_windows,
                "total_shared_hours": total_windows * minutes_per_window / 60,
            }
        )
    return pd.DataFrame(rows)


def summarize_adaptive_comparison(timeline):
    rows = []
    for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
        location = timeline[f"{prefix}_strongest_location"].fillna("Missing")
        rows.append(
            {
                "method": "adaptive_step_rssi",
                "role": role,
                "shared_timeline_windows": len(timeline),
                "estimated_in_home_fraction": timeline[
                    f"{prefix}_estimated_in_home"
                ].mean(),
                "mean_rssi_confidence_score": timeline[
                    f"{prefix}_rssi_confidence_score"
                ].mean(),
                "median_rssi_confidence_score": timeline[
                    f"{prefix}_rssi_confidence_score"
                ].median(),
                "location_transition_count": transition_count_for_locations(location),
                "possible_transition_fraction": timeline[
                    f"{prefix}_possible_transition"
                ].mean(),
            }
        )
    return pd.DataFrame(rows)


def build_method_comparison(timeline):
    adaptive = summarize_adaptive_comparison(timeline)

    if not os.path.exists(FIXED_WINDOW_COMPARISON_PATH):
        return adaptive

    fixed = pd.read_csv(FIXED_WINDOW_COMPARISON_PATH)
    fixed = fixed.rename(
        columns={
            "shared_timeline_windows": "shared_timeline_windows",
        }
    )
    fixed["method"] = "fixed_rssi_" + fixed["window"].astype(str)
    fixed["possible_transition_fraction"] = np.nan
    fixed = fixed[
        [
            "method",
            "role",
            "shared_timeline_windows",
            "estimated_in_home_fraction",
            "mean_rssi_confidence_score",
            "median_rssi_confidence_score",
            "location_transition_count",
            "possible_transition_fraction",
        ]
    ]
    return pd.concat([fixed, adaptive], ignore_index=True)


def build_movement_state_timeline(timeline):
    rows = []
    for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
        role_rows = timeline[
            [
                "time",
                f"{prefix}_movement_state",
                f"{prefix}_selected_window",
                f"{prefix}_possible_transition",
                f"{prefix}_steps_10min",
            ]
        ].copy()
        role_rows.columns = [
            "time",
            "movement_state",
            "selected_window",
            "possible_transition",
            "steps_10min",
        ]
        role_rows["role"] = role
        rows.append(role_rows)
    return pd.concat(rows, ignore_index=True)


def plot_stationary_thresholds(comparison, selection_summary, selected):
    role_rows = comparison.loc[comparison["role"].isin(["SUBJECT", "STUDY_PARTNER"])]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    metrics = [
        ("stationary_coverage", "Stationary coverage"),
        ("mean_rssi_confidence_stationary", "Mean RSSI confidence"),
        ("location_transition_count_stationary", "Transitions in stationary windows"),
    ]
    for ax, (metric, title) in zip(axes, metrics):
        pivot = role_rows.pivot(index="threshold_steps", columns="role", values=metric)
        pivot.plot(kind="bar", ax=ax)
        ax.axvline(
            list(pivot.index).index(selected),
            color="black",
            linestyle="--",
            linewidth=1,
        )
        ax.set_title(title)
        ax.set_xlabel("Stationary threshold")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="")
    fig.suptitle(
        f"Home_X001 ForthPhase 4b: Stationary threshold selection; selected <= {selected}",
        y=1.03,
    )
    fig.tight_layout()
    fig.savefig(STATIONARY_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_movement_state_distribution(movement_timeline):
    summary = (
        movement_timeline.groupby(["role", "movement_state"])
        .size()
        .reset_index(name="windows")
    )
    summary["fraction"] = summary["windows"] / summary.groupby("role")[
        "windows"
    ].transform("sum")
    pivot = summary.pivot(index="role", columns="movement_state", values="fraction")
    pivot = pivot.reindex(columns=MOVEMENT_STATES).fillna(0)

    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for state in MOVEMENT_STATES:
        values = pivot[state].values
        ax.bar(
            x,
            values,
            bottom=bottom,
            color=MOVEMENT_COLORS[state],
            label=state,
        )
        bottom += values
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction of 1min windows")
    ax.set_title("Home_X001 ForthPhase 4b: Movement state distribution")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(MOVEMENT_STATE_FIG, dpi=200)
    plt.close(fig)


def plot_selected_window_distribution(movement_timeline):
    summary = (
        movement_timeline.groupby(["role", "selected_window"])
        .size()
        .reset_index(name="windows")
    )
    summary["fraction"] = summary["windows"] / summary.groupby("role")[
        "windows"
    ].transform("sum")
    pivot = summary.pivot(index="role", columns="selected_window", values="fraction")
    pivot = pivot.reindex(columns=RSSI_WINDOWS).fillna(0)

    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction of 1min windows")
    ax.set_title("Home_X001 ForthPhase 4b: Selected RSSI window distribution")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Selected window", loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    fig.savefig(WINDOW_CHOICE_FIG, dpi=200)
    plt.close(fig)


def plot_adaptive_copresence(summary):
    plot_data = summary.sort_values("hours")
    colors = [STATE_COLORS[state] for state in plot_data["copresence_state"]]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(plot_data["copresence_label"], plot_data["hours"], color=colors)
    for y, value in enumerate(plot_data["hours"]):
        ax.text(value + 0.5, y, f"{value:.1f} h", va="center")
    ax.set_xlabel("Hours")
    ax.set_title("Home_X001 ForthPhase 4b: Adaptive step-RSSI co-presence")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ADAPTIVE_COPRESENCE_FIG, dpi=200)
    plt.close(fig)


def plot_adaptive_comparison(comparison):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    metrics = [
        ("mean_rssi_confidence_score", "Mean RSSI confidence"),
        ("location_transition_count", "Location transitions"),
        ("possible_transition_fraction", "Possible transition fraction"),
    ]
    for ax, (metric, title) in zip(axes, metrics):
        pivot = comparison.pivot(index="method", columns="role", values=metric)
        method_order = [
            method
            for method in [
                "fixed_rssi_5min",
                "fixed_rssi_10min",
                "fixed_rssi_30min",
                "adaptive_step_rssi",
            ]
            if method in pivot.index
        ]
        pivot = pivot.reindex(method_order)
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="")
    fig.suptitle(
        "Home_X001 ForthPhase 4b: Adaptive step-RSSI vs fixed RSSI windows",
        y=1.03,
    )
    fig.tight_layout()
    fig.savefig(ADAPTIVE_COMPARISON_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    features = build_all_features()
    stationary_comparison = evaluate_stationary_thresholds(features)
    selected_stationary, selection_summary = select_stationary_threshold(
        stationary_comparison,
    )
    movement_thresholds = build_movement_thresholds(features, selected_stationary)
    adaptive_timeline = build_adaptive_timeline(features, movement_thresholds)
    movement_timeline = build_movement_state_timeline(adaptive_timeline)
    adaptive_copresence = summarize_adaptive_copresence(adaptive_timeline)
    adaptive_comparison = build_method_comparison(adaptive_timeline)

    stationary_comparison.to_csv(STATIONARY_COMPARISON_PATH, index=False)
    selection_summary.to_csv(STATIONARY_SELECTION_SCORE_PATH, index=False)
    movement_thresholds.to_csv(MOVEMENT_THRESHOLDS_PATH, index=False)
    movement_timeline.to_csv(MOVEMENT_TIMELINE_PATH, index=False)
    adaptive_timeline.to_csv(ADAPTIVE_TIMELINE_PATH, index=False)
    adaptive_copresence.to_csv(ADAPTIVE_COPRESENCE_PATH, index=False)
    adaptive_comparison.to_csv(ADAPTIVE_COMPARISON_PATH, index=False)

    plot_stationary_thresholds(
        stationary_comparison,
        selection_summary,
        selected_stationary,
    )
    plot_movement_state_distribution(movement_timeline)
    plot_selected_window_distribution(movement_timeline)
    plot_adaptive_copresence(adaptive_copresence)
    plot_adaptive_comparison(adaptive_comparison)

    print("\nSelected stationary threshold:")
    print(f"steps <= {selected_stationary}")
    print("\nMovement state thresholds:")
    print(movement_thresholds.to_string(index=False))
    print("\nAdaptive co-presence summary:")
    print(adaptive_copresence.to_string(index=False))
    print("\nAdaptive comparison:")
    print(adaptive_comparison.to_string(index=False))
    print("\nSaved outputs:")
    for path in [
        STATIONARY_COMPARISON_PATH,
        STATIONARY_SELECTION_SCORE_PATH,
        MOVEMENT_THRESHOLDS_PATH,
        MOVEMENT_TIMELINE_PATH,
        ADAPTIVE_TIMELINE_PATH,
        ADAPTIVE_COPRESENCE_PATH,
        ADAPTIVE_COMPARISON_PATH,
        STATIONARY_FIG,
        MOVEMENT_STATE_FIG,
        WINDOW_CHOICE_FIG,
        ADAPTIVE_COPRESENCE_FIG,
        ADAPTIVE_COMPARISON_FIG,
    ]:
        print(path)


if __name__ == "__main__":
    main()
