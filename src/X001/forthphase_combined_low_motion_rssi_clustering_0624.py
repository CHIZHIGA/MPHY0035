import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from forthphase_fixed_rssi_window_comparison import (
    RESULTS_DIR,
    SIDES,
    SIDE_TO_ROLE,
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
    classify_state,
)
from forthphase_hierarchical_step_adaptive_rssi import transition_count_for_locations
from forthphase_low_motion_rssi_clustering import (
    K_CANDIDATES,
    LOW_MOTION_THRESHOLD,
    MIN_CLUSTER_FRACTION,
    MISSING_RSSI_VALUE,
    WINDOW,
    WINDOW_HOURS,
    build_role_feature_table,
)


PREFIX = "X001_forthphase_combined_low_motion_cluster"
TRAINING_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_training_windows.csv")
MODEL_SELECTION_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_model_selection.csv")
PROFILE_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_profiles.csv")
TIMELINE_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_timeline.csv")
COPRESENCE_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_copresence_summary.csv")
COMPARISON_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_comparison.csv")
BEFORE_AFTER_PATH = os.path.join(RESULTS_DIR, f"{PREFIX}_before_after_summary.csv")

MODEL_SELECTION_FIG = os.path.join(RESULTS_DIR, f"{PREFIX}_model_selection.png")
SIZE_FIG = os.path.join(RESULTS_DIR, f"{PREFIX}_size_distribution.png")
EVIDENCE_FIG = os.path.join(RESULTS_DIR, f"{PREFIX}_rssi_evidence_summary.png")
COPRESENCE_FIG = os.path.join(RESULTS_DIR, f"{PREFIX}_copresence_summary.png")
BEFORE_AFTER_FIG = os.path.join(RESULTS_DIR, f"{PREFIX}_before_after_summary.png")


def union_feature_columns(tables):
    columns = set()
    for table in tables:
        columns.update(col for col in table.columns if col.startswith("rssi_"))
    return sorted(columns)


def build_pooled_table():
    tables = []
    for side in SIDES:
        table, _ = build_role_feature_table(side)
        tables.append(table)
    feature_cols = union_feature_columns(tables)
    aligned = []
    for table in tables:
        output = table.copy()
        for col in feature_cols:
            if col not in output:
                output[col] = MISSING_RSSI_VALUE
        aligned.append(output)
    return pd.concat(aligned, ignore_index=True), feature_cols


def evaluate_k(feature_matrix):
    rows = []
    n_samples = len(feature_matrix)
    for k in K_CANDIDATES:
        if n_samples <= k:
            rows.append(
                {
                    "candidate_k": k,
                    "valid_candidate": False,
                    "silhouette_score": np.nan,
                    "min_cluster_fraction": np.nan,
                    "reason": "not enough training windows",
                }
            )
            continue
        model = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels = model.fit_predict(feature_matrix)
        fractions = pd.Series(labels).value_counts(normalize=True)
        min_fraction = fractions.min()
        valid = min_fraction >= MIN_CLUSTER_FRACTION
        rows.append(
            {
                "candidate_k": k,
                "valid_candidate": bool(valid),
                "silhouette_score": silhouette_score(feature_matrix, labels),
                "min_cluster_fraction": min_fraction,
                "reason": "ok" if valid else "small cluster",
            }
        )
    return pd.DataFrame(rows)


def select_k(selection):
    valid = selection.loc[selection["valid_candidate"]].copy()
    if valid.empty:
        valid = selection.dropna(subset=["silhouette_score"]).copy()
    if valid.empty:
        return min(K_CANDIDATES)
    return int(
        valid.sort_values(
            ["silhouette_score", "candidate_k"],
            ascending=[False, True],
        ).iloc[0]["candidate_k"]
    )


def train_combined_cluster(table, feature_cols):
    training = table.loc[table["low_motion_training_candidate"]].copy()
    scaler = StandardScaler()
    train_features = scaler.fit_transform(training[feature_cols])
    selection = evaluate_k(train_features)
    selected_k = select_k(selection)
    model = KMeans(n_clusters=selected_k, random_state=42, n_init=20)
    training["cluster"] = model.fit_predict(train_features)

    predicted = table.copy()
    predicted["cluster"] = np.nan
    has_rssi = predicted["has_rssi"]
    predicted_features = scaler.transform(predicted.loc[has_rssi, feature_cols])
    predicted.loc[has_rssi, "cluster"] = model.predict(predicted_features)
    predicted["cluster"] = predicted["cluster"].astype("Int64")
    selection["selected_k"] = selected_k
    selection["training_windows"] = len(training)
    return selection, training, predicted


def cluster_profiles(training, predicted, feature_cols):
    rows = []
    for cluster, group in training.groupby("cluster"):
        predicted_cluster = predicted.loc[predicted["cluster"].eq(cluster)]
        pair = (
            group["strongest_beacon"].fillna("Missing").astype(str)
            + "|||"
            + group["strongest_location"].fillna("Unmapped").astype(str)
        )
        mode = pair.mode()
        if mode.empty:
            dominant_beacon, dominant_location = "Missing", "Unmapped"
        else:
            dominant_beacon, dominant_location = mode.iloc[0].split("|||", 1)
        row = {
            "cluster": int(cluster),
            "training_windows": len(group),
            "predicted_windows": len(predicted_cluster),
            "subject_training_windows": int(group["role"].eq("SUBJECT").sum()),
            "study_partner_training_windows": int(
                group["role"].eq("STUDY_PARTNER").sum()
            ),
            "dominant_strongest_beacon": dominant_beacon,
            "dominant_mapped_location": dominant_location,
            "mean_rssi_evidence_samples": group["total_rssi_samples"].mean(),
            "mean_signal_separation_gap": group["strongest_second_gap"].mean(),
            "mean_steps_window_training": group["steps_window"].mean(),
        }
        for col in feature_cols:
            row[f"mean_{col}"] = group[col].replace(MISSING_RSSI_VALUE, np.nan).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def attach_cluster_location(predicted, profiles):
    lookup = profiles[
        ["cluster", "dominant_mapped_location", "dominant_strongest_beacon"]
    ].copy()
    output = predicted.merge(lookup, on="cluster", how="left")
    output["cluster_location"] = np.where(
        output["has_rssi"] & output["dominant_mapped_location"].notna(),
        output["dominant_mapped_location"],
        "Unmapped",
    )
    output["cluster_label"] = np.where(
        output["has_rssi"] & output["cluster"].notna(),
        "C" + output["cluster"].astype(str),
        "Unmapped",
    )
    output["estimated_in_home"] = output["cluster_location"].ne("Unmapped")
    return output


def build_copresence_timeline(clustered):
    keep_cols = [
        "time",
        "role",
        "cluster",
        "cluster_label",
        "cluster_location",
        "strongest_location",
        "estimated_in_home",
        "total_rssi_samples",
        "strongest_second_gap",
        "steps_window",
        "has_rssi",
    ]
    subject = (
        clustered.loc[clustered["role"] == "SUBJECT", keep_cols]
        .sort_values("time")
        .set_index("time")
        .add_prefix("subject_")
    )
    partner = (
        clustered.loc[clustered["role"] == "STUDY_PARTNER", keep_cols]
        .sort_values("time")
        .set_index("time")
        .add_prefix("study_partner_")
    )
    common_index = subject.index.intersection(partner.index).sort_values()
    timeline = subject.loc[common_index].join(partner.loc[common_index], how="inner")
    timeline["subject_rssi_strongest_location"] = timeline["subject_strongest_location"]
    timeline["study_partner_rssi_strongest_location"] = timeline[
        "study_partner_strongest_location"
    ]
    timeline["subject_strongest_location"] = timeline["subject_cluster_location"]
    timeline["study_partner_strongest_location"] = timeline[
        "study_partner_cluster_location"
    ]
    timeline["copresence_state"] = timeline.apply(classify_state, axis=1)
    timeline["copresence_label"] = timeline["copresence_state"].map(STATE_LABELS)
    return timeline.reset_index().rename(columns={"index": "time"})


def summarize_copresence(timeline):
    counts = timeline["copresence_state"].value_counts()
    total = len(timeline)
    rows = []
    for state in STATE_ORDER:
        windows = int(counts.get(state, 0))
        rows.append(
            {
                "method": "combined_low_motion_rssi_clustering",
                "copresence_state": state,
                "copresence_label": STATE_LABELS[state],
                "windows": windows,
                "hours": windows * WINDOW_HOURS,
                "percentage_of_shared_time": windows / total if total else np.nan,
                "total_shared_windows": total,
                "total_shared_hours": total * WINDOW_HOURS,
            }
        )
    return pd.DataFrame(rows)


def summarize_comparison(timeline):
    rows = []
    for role, prefix in [("SUBJECT", "subject"), ("STUDY_PARTNER", "study_partner")]:
        location = timeline[f"{prefix}_cluster_location"].fillna("Missing")
        transitions = transition_count_for_locations(location)
        has_rssi = timeline[f"{prefix}_has_rssi"]
        agreement_rows = timeline.loc[
            has_rssi
            & timeline[f"{prefix}_cluster_location"].ne("Unmapped")
            & timeline[f"{prefix}_rssi_strongest_location"].ne("Unmapped")
        ]
        strongest_agreement = (
            agreement_rows[f"{prefix}_cluster_location"]
            .eq(agreement_rows[f"{prefix}_rssi_strongest_location"])
            .mean()
            if not agreement_rows.empty
            else np.nan
        )
        rows.append(
            {
                "method": "combined_low_motion_rssi_clustering",
                "role": role,
                "shared_timeline_windows": len(timeline),
                "estimated_in_home_fraction": timeline[
                    f"{prefix}_estimated_in_home"
                ].mean(),
                "mean_rssi_evidence_samples": timeline[
                    f"{prefix}_total_rssi_samples"
                ].mean(),
                "mean_signal_separation_gap": timeline[
                    f"{prefix}_strongest_second_gap"
                ].mean(),
                "location_transition_count": transitions,
                "transitions_per_day": transitions
                / (len(timeline) * WINDOW_HOURS / 24),
                "cluster_strongest_location_agreement": strongest_agreement,
            }
        )
    return pd.DataFrame(rows)


def before_after_summary(new_comparison, new_copresence):
    rows = []
    old_path = os.path.join(
        RESULTS_DIR,
        "X001_forthphase_low_motion_cluster_comparison.csv",
    )
    if os.path.exists(old_path):
        old = pd.read_csv(old_path)
        old = old.loc[old["method"].eq("low_motion_rssi_clustering")].copy()
        for _, row in old.iterrows():
            rows.append(
                {
                    "comparison": "old_separate_4c",
                    "role": row["role"],
                    "estimated_in_home_fraction": row.get(
                        "estimated_in_home_fraction", np.nan
                    ),
                    "location_transition_count": row.get(
                        "location_transition_count", np.nan
                    ),
                    "cluster_strongest_location_agreement": row.get(
                        "cluster_strongest_location_agreement", np.nan
                    ),
                }
            )
    for _, row in new_comparison.iterrows():
        rows.append(
            {
                "comparison": "new_combined_4c",
                "role": row["role"],
                "estimated_in_home_fraction": row["estimated_in_home_fraction"],
                "location_transition_count": row["location_transition_count"],
                "cluster_strongest_location_agreement": row[
                    "cluster_strongest_location_agreement"
                ],
            }
        )

    cop_rows = []
    old_cop_path = os.path.join(
        RESULTS_DIR,
        "X001_forthphase_low_motion_cluster_copresence_summary.csv",
    )
    if os.path.exists(old_cop_path):
        old_cop = pd.read_csv(old_cop_path)
        old_cop["comparison"] = "old_separate_4c"
        cop_rows.append(old_cop)
    new_cop = new_copresence.copy()
    new_cop["comparison"] = "new_combined_4c"
    cop_rows.append(new_cop)
    copresence = pd.concat(cop_rows, ignore_index=True)
    return pd.DataFrame(rows), copresence


def plot_model_selection(selection):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(selection["candidate_k"], selection["silhouette_score"], marker="o")
    selected = selection["selected_k"].iloc[0]
    selected_score = selection.loc[
        selection["candidate_k"].eq(selected), "silhouette_score"
    ]
    if not selected_score.empty:
        ax.scatter([selected], [selected_score.iloc[0]], s=120, marker="*", zorder=5)
    ax.set_xlabel("Candidate k")
    ax.set_ylabel("Silhouette score")
    ax.set_title("Combined 4c: shared cluster model selection")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(MODEL_SELECTION_FIG, dpi=210)
    plt.close(fig)


def plot_cluster_sizes(profiles):
    labels = "C" + profiles["cluster"].astype(str) + " " + profiles[
        "dominant_mapped_location"
    ].astype(str)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(labels, profiles["predicted_windows"])
    ax.set_ylabel(f"Predicted {WINDOW} windows")
    ax.set_title("Combined 4c: cluster size distribution")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SIZE_FIG, dpi=210)
    plt.close(fig)


def plot_evidence_summary(profiles):
    labels = "C" + profiles["cluster"].astype(str) + " " + profiles[
        "dominant_mapped_location"
    ].astype(str)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    metrics = [
        ("mean_rssi_evidence_samples", "Mean RSSI samples"),
        ("mean_signal_separation_gap", "Mean strongest-second gap"),
        ("mean_steps_window_training", "Mean training-window steps"),
    ]
    for ax, (col, title) in zip(axes, metrics):
        ax.bar(labels, profiles[col])
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Combined 4c: RSSI evidence and signal stability by cluster")
    fig.tight_layout()
    fig.savefig(EVIDENCE_FIG, dpi=210, bbox_inches="tight")
    plt.close(fig)


def plot_copresence(summary):
    plot_data = summary.sort_values("hours")
    colors = [STATE_COLORS[state] for state in plot_data["copresence_state"]]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.barh(plot_data["copresence_label"], plot_data["hours"], color=colors)
    for y, value in enumerate(plot_data["hours"]):
        ax.text(value + 0.5, y, f"{value:.1f} h", va="center")
    ax.set_xlabel("Hours")
    ax.set_title("Combined 4c: co-presence summary")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COPRESENCE_FIG, dpi=210)
    plt.close(fig)


def plot_before_after(before_after):
    if before_after.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    metrics = [
        ("estimated_in_home_fraction", "Estimated in-home fraction"),
        ("location_transition_count", "Location transitions"),
        ("cluster_strongest_location_agreement", "Agreement with strongest beacon"),
    ]
    for ax, (col, title) in zip(axes, metrics):
        pivot = before_after.pivot(index="comparison", columns="role", values=col)
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("4c before/after: separate role clusters vs combined cluster")
    fig.tight_layout()
    fig.savefig(BEFORE_AFTER_FIG, dpi=210, bbox_inches="tight")
    plt.close(fig)


def main():
    pooled, feature_cols = build_pooled_table()
    selection, training, predicted = train_combined_cluster(pooled, feature_cols)
    profiles = cluster_profiles(training, predicted, feature_cols)
    clustered = attach_cluster_location(predicted, profiles)
    timeline = build_copresence_timeline(clustered)
    copresence = summarize_copresence(timeline)
    comparison = summarize_comparison(timeline)
    before_after, copresence_before_after = before_after_summary(comparison, copresence)

    training.to_csv(TRAINING_PATH, index=False)
    selection.to_csv(MODEL_SELECTION_PATH, index=False)
    profiles.to_csv(PROFILE_PATH, index=False)
    timeline.to_csv(TIMELINE_PATH, index=False)
    copresence.to_csv(COPRESENCE_PATH, index=False)
    comparison.to_csv(COMPARISON_PATH, index=False)
    before_after.to_csv(BEFORE_AFTER_PATH, index=False)
    copresence_before_after.to_csv(
        os.path.join(RESULTS_DIR, f"{PREFIX}_copresence_before_after.csv"),
        index=False,
    )

    plot_model_selection(selection)
    plot_cluster_sizes(profiles)
    plot_evidence_summary(profiles)
    plot_copresence(copresence)
    plot_before_after(before_after)

    print("Combined 4c model selection:")
    print(selection.to_string(index=False))
    print("\nCombined 4c profiles:")
    print(
        profiles[
            [
                "cluster",
                "training_windows",
                "predicted_windows",
                "subject_training_windows",
                "study_partner_training_windows",
                "dominant_strongest_beacon",
                "dominant_mapped_location",
                "mean_rssi_evidence_samples",
                "mean_signal_separation_gap",
            ]
        ].to_string(index=False)
    )
    print("\nCombined 4c comparison:")
    print(comparison.to_string(index=False))
    print("\nBefore/after:")
    print(before_after.to_string(index=False))
    print("\nSaved outputs:")
    for path in [
        TRAINING_PATH,
        MODEL_SELECTION_PATH,
        PROFILE_PATH,
        TIMELINE_PATH,
        COPRESENCE_PATH,
        COMPARISON_PATH,
        BEFORE_AFTER_PATH,
        MODEL_SELECTION_FIG,
        SIZE_FIG,
        EVIDENCE_FIG,
        COPRESENCE_FIG,
        BEFORE_AFTER_FIG,
    ]:
        print(path)


if __name__ == "__main__":
    main()
