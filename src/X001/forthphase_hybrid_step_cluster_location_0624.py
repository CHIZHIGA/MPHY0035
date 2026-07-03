import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forthphase_fixed_rssi_window_comparison import (
    RESULTS_DIR,
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
    classify_state,
)
from forthphase_hierarchical_step_adaptive_rssi import transition_count_for_locations


THRESHOLD_STEPS = 10
MIN_CLUSTER_TRAINING_WINDOWS = 10
MIN_CLUSTER_GAP = 8
WEAK_RSSI_GAP = 5
STRONG_RSSI_GAP = 8

ADAPTIVE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hierarchical_step_adaptive_rssi_timeline.csv",
)
CLUSTER_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_combined_low_motion_cluster_timeline.csv",
)
CLUSTER_PROFILE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_combined_low_motion_cluster_profiles.csv",
)

TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_timeline.csv",
)
COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_copresence_summary.csv",
)
COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_comparison.csv",
)
OVERRIDE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_override_summary.csv",
)

COPRESENCE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_copresence_summary.png",
)
COMPARISON_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_comparison.png",
)
OVERRIDE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hybrid_step_cluster_override_summary.png",
)


def clean_location(value):
    if pd.isna(value):
        return "Unmapped"
    text = str(value)
    return text if text else "Unmapped"


def weak_or_ambiguous(base_location, base_gap, base_samples):
    return (
        pd.isna(base_gap)
        or base_gap < WEAK_RSSI_GAP
        or clean_location(base_location) in {"Unmapped", "Out"}
        or pd.isna(base_samples)
        or base_samples <= 0
    )


def strong_base_evidence(base_gap):
    return pd.notna(base_gap) and base_gap >= STRONG_RSSI_GAP


def profile_lookup(profiles):
    return (
        profiles[
            [
                "cluster",
                "training_windows",
                "dominant_mapped_location",
                "mean_signal_separation_gap",
            ]
        ]
        .rename(
            columns={
                "training_windows": "cluster_profile_training_windows",
                "dominant_mapped_location": "cluster_profile_location",
                "mean_signal_separation_gap": "cluster_profile_gap",
            }
        )
        .copy()
    )


def hybrid_decision(row, prefix):
    base_location = clean_location(row[f"{prefix}_base_4b_location"])
    cluster_location = clean_location(row[f"{prefix}_cluster_location"])
    selected_window = row[f"{prefix}_selected_window"]
    base_gap = row[f"{prefix}_base_rssi_gap"]
    base_samples = row[f"{prefix}_base_rssi_samples"]
    profile_training = row[f"{prefix}_cluster_profile_training_windows"]
    profile_gap = row[f"{prefix}_cluster_profile_gap"]

    low_motion_candidate = selected_window == "30min"
    usable_cluster = (
        cluster_location not in {"Unmapped", "Out"}
        and pd.notna(profile_training)
        and profile_training >= MIN_CLUSTER_TRAINING_WINDOWS
        and pd.notna(profile_gap)
        and profile_gap >= MIN_CLUSTER_GAP
    )
    weak_base = weak_or_ambiguous(base_location, base_gap, base_samples)
    strong_base = strong_base_evidence(base_gap)

    if not low_motion_candidate:
        return base_location, "step_adaptive_rssi", False, "not_30min_low_motion"
    if not usable_cluster:
        return base_location, "step_adaptive_rssi", False, "cluster_not_usable"
    if strong_base:
        return base_location, "step_adaptive_rssi", False, "strong_4b_evidence"
    if weak_base:
        return cluster_location, "cluster_override", True, "low_motion_weak_4b"
    return base_location, "step_adaptive_rssi", False, "4b_not_ambiguous"


def add_role_hybrid(frame, role_prefix):
    rows = []
    for _, row in frame.iterrows():
        location, source, used, reason = hybrid_decision(row, role_prefix)
        rows.append(
            {
                f"{role_prefix}_final_hybrid_location": location,
                f"{role_prefix}_final_source": source,
                f"{role_prefix}_cluster_override_used": used,
                f"{role_prefix}_override_reason": reason,
                f"{role_prefix}_hybrid_estimated_in_home": location
                not in {"Unmapped", "Out"},
            }
        )
    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def load_inputs():
    adaptive = pd.read_csv(ADAPTIVE_PATH, parse_dates=["time"])
    adaptive = adaptive.loc[adaptive["threshold_steps"].eq(THRESHOLD_STEPS)].copy()

    cluster = pd.read_csv(CLUSTER_TIMELINE_PATH, parse_dates=["time"])
    profiles = pd.read_csv(CLUSTER_PROFILE_PATH)
    lookup = profile_lookup(profiles)

    subject_cluster = (
        cluster[
            [
                "time",
                "subject_cluster",
                "subject_cluster_location",
                "subject_cluster_label",
                "subject_total_rssi_samples",
                "subject_strongest_second_gap",
            ]
        ]
        .rename(
            columns={
                "subject_cluster": "subject_cluster",
                "subject_cluster_location": "subject_cluster_location",
                "subject_cluster_label": "subject_cluster_label",
                "subject_total_rssi_samples": "subject_cluster_rssi_samples",
                "subject_strongest_second_gap": "subject_cluster_rssi_gap",
            }
        )
        .merge(lookup, left_on="subject_cluster", right_on="cluster", how="left")
        .drop(columns=["cluster"])
        .rename(
            columns={
                "cluster_profile_training_windows": "subject_cluster_profile_training_windows",
                "cluster_profile_location": "subject_cluster_profile_location",
                "cluster_profile_gap": "subject_cluster_profile_gap",
            }
        )
    )
    partner_cluster = (
        cluster[
            [
                "time",
                "study_partner_cluster",
                "study_partner_cluster_location",
                "study_partner_cluster_label",
                "study_partner_total_rssi_samples",
                "study_partner_strongest_second_gap",
            ]
        ]
        .rename(
            columns={
                "study_partner_cluster": "study_partner_cluster",
                "study_partner_cluster_location": "study_partner_cluster_location",
                "study_partner_cluster_label": "study_partner_cluster_label",
                "study_partner_total_rssi_samples": "study_partner_cluster_rssi_samples",
                "study_partner_strongest_second_gap": "study_partner_cluster_rssi_gap",
            }
        )
        .merge(lookup, left_on="study_partner_cluster", right_on="cluster", how="left")
        .drop(columns=["cluster"])
        .rename(
            columns={
                "cluster_profile_training_windows": "study_partner_cluster_profile_training_windows",
                "cluster_profile_location": "study_partner_cluster_profile_location",
                "cluster_profile_gap": "study_partner_cluster_profile_gap",
            }
        )
    )

    cluster_30 = subject_cluster.merge(
        partner_cluster,
        on="time",
        how="inner",
    )
    cluster_30["join_time"] = cluster_30["time"]

    adaptive["join_time"] = adaptive["time"].dt.floor("30min")
    merged = adaptive.merge(
        cluster_30.drop(columns=["time"]),
        on="join_time",
        how="left",
    )
    return merged


def prepare_base_columns(frame):
    output = frame.copy()
    rename = {
        "subject_strongest_location": "subject_base_4b_location",
        "study_partner_strongest_location": "study_partner_base_4b_location",
        "subject_strongest_second_gap": "subject_base_rssi_gap",
        "study_partner_strongest_second_gap": "study_partner_base_rssi_gap",
        "subject_total_rssi_samples": "subject_base_rssi_samples",
        "study_partner_total_rssi_samples": "study_partner_base_rssi_samples",
    }
    output = output.rename(columns=rename)
    return output


def build_hybrid_timeline():
    merged = prepare_base_columns(load_inputs())
    merged = add_role_hybrid(merged, "subject")
    merged = add_role_hybrid(merged, "study_partner")
    merged["subject_strongest_location"] = merged["subject_final_hybrid_location"]
    merged["study_partner_strongest_location"] = merged[
        "study_partner_final_hybrid_location"
    ]
    merged["subject_estimated_in_home"] = merged["subject_hybrid_estimated_in_home"]
    merged["study_partner_estimated_in_home"] = merged[
        "study_partner_hybrid_estimated_in_home"
    ]
    merged["copresence_state"] = merged.apply(classify_state, axis=1)
    merged["copresence_label"] = merged["copresence_state"].map(STATE_LABELS)
    return merged


def summarize_copresence(timeline):
    counts = timeline["copresence_state"].value_counts()
    total = len(timeline)
    rows = []
    for state in STATE_ORDER:
        windows = int(counts.get(state, 0))
        rows.append(
            {
                "method": "hybrid_step_cluster",
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
    for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
        transitions = transition_count_for_locations(
            timeline[f"{prefix}_final_hybrid_location"]
        )
        base_transitions = transition_count_for_locations(
            timeline[f"{prefix}_base_4b_location"]
        )
        agreement = timeline[f"{prefix}_final_hybrid_location"].eq(
            timeline[f"{prefix}_base_4b_location"]
        )
        rows.append(
            {
                "method": "hybrid_step_cluster",
                "role": role,
                "shared_timeline_windows": len(timeline),
                "hybrid_transition_count": transitions,
                "base_4b_transition_count": base_transitions,
                "hybrid_base_agreement_fraction": agreement.mean(),
                "cluster_override_windows": int(
                    timeline[f"{prefix}_cluster_override_used"].sum()
                ),
                "cluster_override_fraction": timeline[
                    f"{prefix}_cluster_override_used"
                ].mean(),
                "estimated_in_home_fraction": timeline[
                    f"{prefix}_hybrid_estimated_in_home"
                ].mean(),
            }
        )
    return pd.DataFrame(rows)


def summarize_overrides(timeline):
    rows = []
    for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
        reasons = timeline[f"{prefix}_override_reason"].value_counts()
        for reason, count in reasons.items():
            rows.append(
                {
                    "role": role,
                    "override_reason": reason,
                    "windows": int(count),
                    "fraction": count / len(timeline) if len(timeline) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def plot_copresence(summary):
    plot_data = summary.sort_values("hours")
    colors = [STATE_COLORS[state] for state in plot_data["copresence_state"]]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(plot_data["copresence_label"], plot_data["hours"], color=colors)
    for y, value in enumerate(plot_data["hours"]):
        ax.text(value + 0.6, y, f"{value:.1f} h", va="center")
    ax.set_xlabel("Hours")
    ax.set_title("X001 hybrid 4b+4c co-presence summary")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COPRESENCE_FIG, dpi=210)
    plt.close(fig)


def plot_comparison(comparison):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    metrics = [
        ("base_4b_transition_count", "Base 4b transitions"),
        ("hybrid_transition_count", "Hybrid transitions"),
        ("cluster_override_windows", "Cluster override windows"),
    ]
    for ax, (col, title) in zip(axes, metrics):
        ax.bar(comparison["role"], comparison[col])
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("X001 hybrid 4b+4c comparison")
    fig.tight_layout()
    fig.savefig(COMPARISON_FIG, dpi=210)
    plt.close(fig)


def plot_overrides(override_summary):
    pivot = override_summary.pivot(
        index="override_reason",
        columns="role",
        values="windows",
    ).fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5.2))
    pivot.plot(kind="barh", ax=ax)
    ax.set_xlabel("1min timeline windows")
    ax.set_title("X001 hybrid 4b+4c override reasons")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OVERRIDE_FIG, dpi=210, bbox_inches="tight")
    plt.close(fig)


def main():
    timeline = build_hybrid_timeline()
    copresence = summarize_copresence(timeline)
    comparison = summarize_comparison(timeline)
    overrides = summarize_overrides(timeline)

    timeline.to_csv(TIMELINE_PATH, index=False)
    copresence.to_csv(COPRESENCE_PATH, index=False)
    comparison.to_csv(COMPARISON_PATH, index=False)
    overrides.to_csv(OVERRIDE_PATH, index=False)

    plot_copresence(copresence)
    plot_comparison(comparison)
    plot_overrides(overrides)

    print("Hybrid comparison:")
    print(comparison.to_string(index=False))
    print("\nOverride summary:")
    print(overrides.to_string(index=False))
    print("\nCo-presence:")
    print(copresence.to_string(index=False))
    print("\nSaved:")
    for path in [
        TIMELINE_PATH,
        COPRESENCE_PATH,
        COMPARISON_PATH,
        OVERRIDE_PATH,
        COPRESENCE_FIG,
        COMPARISON_FIG,
        OVERRIDE_FIG,
    ]:
        print(path)


if __name__ == "__main__":
    main()
