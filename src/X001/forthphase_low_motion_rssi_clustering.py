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
    active_beacon_location,
    classify_state,
    load_rssi_samples,
    read_metadata,
)
from forthphase_hierarchical_step_adaptive_rssi import transition_count_for_locations
from forthphase_step_threshold_diagnostics import build_uniformized_step_windows


WINDOW = "30min"
LOW_MOTION_THRESHOLD = 10
MISSING_RSSI_VALUE = -100
K_CANDIDATES = [3, 4, 5, 6, 7, 8]
MIN_CLUSTER_FRACTION = 0.05
WINDOW_HOURS = pd.Timedelta(WINDOW) / pd.Timedelta(hours=1)

TRAINING_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_training_windows.csv",
)
MODEL_SELECTION_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_model_selection.csv",
)
PROFILE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_profiles.csv",
)
TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_timeline.csv",
)
COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_copresence_summary.csv",
)
COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_comparison.csv",
)

MODEL_SELECTION_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_model_selection.png",
)
CLUSTER_SIZE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_size_distribution.png",
)
RSSI_PROFILE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_rssi_profile_heatmap.png",
)
TIMELINE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_timeline.png",
)
COPRESENCE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_copresence_summary.png",
)
COMPARISON_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_low_motion_cluster_comparison.png",
)


def mapped_beacon_ids(side, start_time=None, end_time=None):
    metadata = read_metadata(side)
    beacons = pd.DataFrame(metadata.get("beacons", []))
    if start_time is not None and end_time is not None:
        start_sec = int(start_time.timestamp())
        end_sec = int(end_time.timestamp())
        beacons = beacons.loc[
            (beacons["start_date"] <= end_sec)
            & ((beacons["end_date"] == 0) | (beacons["end_date"] > start_sec))
        ]
    return sorted(beacons["beacon_id"].dropna().astype(str).str.upper().unique())


def build_rssi_vector_windows(side):
    samples = load_rssi_samples(side)
    beacons = mapped_beacon_ids(
        side,
        samples["time"].min(),
        samples["time"].max(),
    )
    samples = samples.loc[samples["beacon_id"].isin(beacons)].copy()
    pivot = samples.pivot_table(
        index="time",
        columns="beacon_id",
        values="rssi",
        aggfunc="mean",
    ).sort_index()

    mean_rssi = pivot.resample(WINDOW).mean()
    counts = pivot.resample(WINDOW).count().reindex(mean_rssi.index)
    mean_rssi = mean_rssi.reindex(columns=beacons)
    counts = counts.reindex(columns=beacons)

    total_samples = counts.sum(axis=1).fillna(0)
    has_rssi = total_samples > 0
    observed = mean_rssi.where(counts > 0)
    strongest_beacon = observed.apply(
        lambda row: row.idxmax() if row.notna().any() else np.nan,
        axis=1,
    )
    strongest_rssi = observed.max(axis=1)
    second_rssi = observed.apply(
        lambda row: row.dropna().sort_values(ascending=False).iloc[1]
        if row.dropna().shape[0] >= 2
        else np.nan,
        axis=1,
    )
    strongest_second_gap = strongest_rssi - second_rssi

    feature_cols = [f"rssi_{beacon}" for beacon in beacons]
    features = mean_rssi.fillna(MISSING_RSSI_VALUE)
    features.columns = feature_cols
    output = features.reset_index().rename(columns={"index": "time"})
    output["side"] = side
    output["role"] = SIDE_TO_ROLE[side]
    output["has_rssi"] = has_rssi.values
    output["total_rssi_samples"] = total_samples.values
    output["strongest_beacon"] = strongest_beacon.values
    output["strongest_rssi"] = strongest_rssi.values
    output["strongest_second_gap"] = strongest_second_gap.values
    output["strongest_beacon_proportion"] = np.nan

    metadata = read_metadata(side)
    beacon_rows = pd.DataFrame(metadata.get("beacons", []))
    output["strongest_location"] = [
        active_beacon_location(beacon_rows, beacon, timestamp)
        if pd.notna(beacon)
        else "Unmapped"
        for timestamp, beacon in zip(output["time"], output["strongest_beacon"])
    ]
    output["rssi_confidence_score"] = (
        0.40 * (output["strongest_second_gap"].fillna(0).clip(0, 15) / 15)
        + 0.60 * output["has_rssi"].astype(float)
    )
    return output, feature_cols


def build_role_feature_table(side):
    rssi, feature_cols = build_rssi_vector_windows(side)
    steps = build_uniformized_step_windows(side, WINDOW)
    merged = rssi.merge(
        steps[["time", "steps_in_window"]],
        on="time",
        how="left",
    )
    merged["steps_window"] = merged["steps_in_window"]
    merged["low_motion_training_candidate"] = (
        merged["steps_window"].le(LOW_MOTION_THRESHOLD) & merged["has_rssi"]
    )
    return merged, feature_cols


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
        counts = pd.Series(labels).value_counts(normalize=True)
        min_fraction = counts.min()
        valid = min_fraction >= MIN_CLUSTER_FRACTION
        score = silhouette_score(feature_matrix, labels) if len(counts) > 1 else np.nan
        rows.append(
            {
                "candidate_k": k,
                "valid_candidate": bool(valid),
                "silhouette_score": score,
                "min_cluster_fraction": min_fraction,
                "reason": "ok" if valid else "small cluster",
            }
        )
    return pd.DataFrame(rows)


def select_k(selection):
    valid = selection.loc[selection["valid_candidate"]].copy()
    if valid.empty:
        fallback = selection.dropna(subset=["silhouette_score"]).copy()
        if fallback.empty:
            return min(K_CANDIDATES)
        valid = fallback
    best = valid.sort_values(
        ["silhouette_score", "candidate_k"],
        ascending=[False, True],
    ).iloc[0]
    return int(best["candidate_k"])


def cluster_role(role_table, role, feature_cols):
    training = role_table.loc[role_table["low_motion_training_candidate"]].copy()
    scaler = StandardScaler()
    train_features = scaler.fit_transform(training[feature_cols])
    selection = evaluate_k(train_features)
    selected_k = select_k(selection)
    model = KMeans(n_clusters=selected_k, random_state=42, n_init=20)
    training["cluster"] = model.fit_predict(train_features)

    predict_rows = role_table.copy()
    predict_rows["cluster"] = np.nan
    has_rssi = predict_rows["has_rssi"]
    predict_features = scaler.transform(predict_rows.loc[has_rssi, feature_cols])
    predict_rows.loc[has_rssi, "cluster"] = model.predict(predict_features)
    predict_rows["cluster"] = predict_rows["cluster"].astype("Int64")

    selection["role"] = role
    selection["selected_k"] = selected_k
    training["training_role"] = role
    return selection, training, predict_rows


def build_cluster_profiles(training, predicted, role, feature_cols):
    rows = []
    for cluster, group in training.groupby("cluster"):
        predicted_cluster = predicted.loc[predicted["cluster"].eq(cluster)]
        beacon_location_pair = (
            group["strongest_beacon"].fillna("Missing").astype(str)
            + "|||"
            + group["strongest_location"].fillna("Unmapped").astype(str)
        )
        dominant_pair = beacon_location_pair.mode()
        if dominant_pair.empty:
            dominant_beacon = np.nan
            dominant_location = "Unmapped"
        else:
            dominant_beacon, dominant_location = dominant_pair.iloc[0].split("|||", 1)
        row = {
            "role": role,
            "cluster": int(cluster),
            "training_windows": len(group),
            "predicted_windows": len(predicted_cluster),
            "dominant_strongest_beacon": dominant_beacon,
            "dominant_mapped_location": dominant_location,
            "mean_rssi_confidence_score": group["rssi_confidence_score"].mean(),
            "mean_steps_window_training": group["steps_window"].mean(),
        }
        for col in feature_cols:
            row[f"mean_{col}"] = group[col].replace(MISSING_RSSI_VALUE, np.nan).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def build_all_cluster_outputs():
    selections = []
    trainings = []
    predictions = []
    profiles = []
    for side in SIDES:
        role = SIDE_TO_ROLE[side]
        print(f"Building low-motion RSSI clusters for {role}...")
        role_table, feature_cols = build_role_feature_table(side)
        selection, training, predicted = cluster_role(role_table, role, feature_cols)
        profile = build_cluster_profiles(training, predicted, role, feature_cols)
        selections.append(selection)
        trainings.append(training)
        predictions.append(predicted)
        profiles.append(profile)
    return (
        pd.concat(selections, ignore_index=True),
        pd.concat(trainings, ignore_index=True),
        pd.concat(predictions, ignore_index=True),
        pd.concat(profiles, ignore_index=True),
    )


def attach_cluster_location(predicted, profiles):
    profile_lookup = profiles[
        ["role", "cluster", "dominant_mapped_location", "dominant_strongest_beacon"]
    ].copy()
    output = predicted.merge(profile_lookup, on=["role", "cluster"], how="left")
    output["cluster_location"] = np.where(
        output["has_rssi"] & output["dominant_mapped_location"].notna(),
        output["dominant_mapped_location"],
        "Unmapped",
    )
    output["cluster_label"] = np.where(
        output["has_rssi"] & output["cluster"].notna(),
        output["role"] + "_C" + output["cluster"].astype(str),
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
        "rssi_confidence_score",
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
    timeline["minimum_rssi_confidence"] = timeline[
        ["subject_rssi_confidence_score", "study_partner_rssi_confidence_score"]
    ].min(axis=1)
    return timeline.reset_index().rename(columns={"index": "time"})


def summarize_copresence(timeline):
    counts = timeline["copresence_state"].value_counts()
    total = len(timeline)
    rows = []
    for state in STATE_ORDER:
        windows = int(counts.get(state, 0))
        rows.append(
            {
                "method": "low_motion_rssi_clustering",
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
        location_agreement = (
            agreement_rows[f"{prefix}_cluster_location"]
            .eq(agreement_rows[f"{prefix}_rssi_strongest_location"])
            .mean()
            if not agreement_rows.empty
            else np.nan
        )
        rows.append(
            {
                "method": "low_motion_rssi_clustering",
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
                "location_transition_count": transitions,
                "transitions_per_day": transitions
                / (len(timeline) * WINDOW_HOURS / 24),
                "cluster_strongest_location_agreement": location_agreement,
            }
        )
    return pd.DataFrame(rows)


def plot_model_selection(selection):
    fig, ax = plt.subplots(figsize=(9, 5))
    for role, group in selection.groupby("role"):
        ax.plot(
            group["candidate_k"],
            group["silhouette_score"],
            marker="o",
            label=role,
        )
        selected = group["selected_k"].iloc[0]
        selected_score = group.loc[group["candidate_k"].eq(selected), "silhouette_score"]
        if not selected_score.empty:
            ax.scatter([selected], [selected_score.iloc[0]], s=120, marker="*", zorder=5)
    ax.set_xlabel("Candidate k")
    ax.set_ylabel("Silhouette score")
    ax.set_title("Home_X001 ForthPhase 4c: Cluster model selection")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(MODEL_SELECTION_FIG, dpi=200)
    plt.close(fig)


def plot_cluster_sizes(profiles):
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = profiles["role"] + " C" + profiles["cluster"].astype(str)
    ax.bar(labels, profiles["predicted_windows"])
    ax.set_ylabel(f"Predicted {WINDOW} windows")
    ax.set_title("Home_X001 ForthPhase 4c: Cluster size distribution")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CLUSTER_SIZE_FIG, dpi=200)
    plt.close(fig)


def plot_rssi_profiles(profiles):
    rssi_cols = [col for col in profiles.columns if col.startswith("mean_rssi_")]
    matrix = profiles[rssi_cols].fillna(MISSING_RSSI_VALUE)
    labels = (
        profiles["role"]
        + " C"
        + profiles["cluster"].astype(str)
        + " "
        + profiles["dominant_mapped_location"].astype(str)
    )
    fig, ax = plt.subplots(figsize=(11, max(5, 0.4 * len(profiles))))
    image = ax.imshow(matrix.values, aspect="auto", cmap="viridis", vmin=-100, vmax=-35)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xticks(np.arange(len(rssi_cols)))
    ax.set_xticklabels([col.replace("mean_rssi_", "") for col in rssi_cols], rotation=45)
    ax.set_title("Home_X001 ForthPhase 4c: Mean RSSI profile by cluster")
    fig.colorbar(image, ax=ax, label="Mean RSSI")
    fig.tight_layout()
    fig.savefig(RSSI_PROFILE_FIG, dpi=200)
    plt.close(fig)


def plot_cluster_timeline(timeline):
    plot_data = timeline.copy()
    plot_data["time"] = pd.to_datetime(plot_data["time"])
    role_cols = [
        ("subject_cluster_label", "SUBJECT"),
        ("study_partner_cluster_label", "STUDY_PARTNER"),
    ]
    labels = sorted(
        set(plot_data["subject_cluster_label"].dropna())
        | set(plot_data["study_partner_cluster_label"].dropna())
    )
    label_to_y = {label: index for index, label in enumerate(labels)}
    fig, axes = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    for ax, (col, title) in zip(axes, role_cols):
        ax.scatter(
            plot_data["time"],
            plot_data[col].map(label_to_y),
            s=8,
            alpha=0.8,
        )
        ax.set_yticks(list(label_to_y.values()))
        ax.set_yticklabels(list(label_to_y.keys()))
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle("Home_X001 ForthPhase 4c: Cluster timeline")
    fig.tight_layout()
    fig.savefig(TIMELINE_FIG, dpi=200)
    plt.close(fig)


def plot_copresence(summary):
    plot_data = summary.sort_values("hours")
    colors = [STATE_COLORS[state] for state in plot_data["copresence_state"]]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(plot_data["copresence_label"], plot_data["hours"], color=colors)
    for y, value in enumerate(plot_data["hours"]):
        ax.text(value + 0.5, y, f"{value:.1f} h", va="center")
    ax.set_xlabel("Hours")
    ax.set_title("Home_X001 ForthPhase 4c: Cluster co-presence summary")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COPRESENCE_FIG, dpi=200)
    plt.close(fig)


def plot_comparison(comparison):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    metrics = [
        ("estimated_in_home_fraction", "Estimated in-home fraction"),
        ("mean_rssi_confidence_score", "Mean RSSI confidence"),
        ("location_transition_count", "Location transitions"),
    ]
    for ax, (metric, title) in zip(axes, metrics):
        pivot = comparison.pivot(index="method", columns="role", values=metric)
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="")
    fig.suptitle("Home_X001 ForthPhase 4c: Comparison with 4a and 4b")
    fig.tight_layout()
    fig.savefig(COMPARISON_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_method_comparison(cluster_comparison):
    rows = []
    fixed_path = os.path.join(
        RESULTS_DIR,
        "X001_forthphase_fixed_rssi_window_comparison.csv",
    )
    adaptive_path = os.path.join(
        RESULTS_DIR,
        "X001_forthphase_hierarchical_step_adaptive_comparison.csv",
    )
    if os.path.exists(fixed_path):
        fixed = pd.read_csv(fixed_path)
        fixed = fixed.loc[fixed["window"].eq(WINDOW)].copy()
        fixed["method"] = f"4a_fixed_{WINDOW}_rssi"
        fixed["cluster_strongest_location_agreement"] = np.nan
        rows.append(
            fixed[
                [
                    "method",
                    "role",
                    "shared_timeline_windows",
                    "estimated_in_home_fraction",
                    "mean_rssi_confidence_score",
                    "median_rssi_confidence_score",
                    "location_transition_count",
                    "cluster_strongest_location_agreement",
                ]
            ]
        )
    if os.path.exists(adaptive_path):
        adaptive = pd.read_csv(adaptive_path)
        adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
        adaptive["method"] = "4b_step_adaptive_rssi"
        adaptive["cluster_strongest_location_agreement"] = np.nan
        rows.append(
            adaptive[
                [
                    "method",
                    "role",
                    "shared_timeline_windows",
                    "estimated_in_home_fraction",
                    "mean_rssi_confidence_score",
                    "median_rssi_confidence_score",
                    "location_transition_count",
                    "cluster_strongest_location_agreement",
                ]
            ]
        )
    rows.append(cluster_comparison)
    return pd.concat(rows, ignore_index=True)


def main():
    selection, training, predicted, profiles = build_all_cluster_outputs()
    clustered = attach_cluster_location(predicted, profiles)
    timeline = build_copresence_timeline(clustered)
    copresence = summarize_copresence(timeline)
    cluster_comparison = summarize_comparison(timeline)
    comparison = build_method_comparison(cluster_comparison)

    training.to_csv(TRAINING_PATH, index=False)
    selection.to_csv(MODEL_SELECTION_PATH, index=False)
    profiles.to_csv(PROFILE_PATH, index=False)
    timeline.to_csv(TIMELINE_PATH, index=False)
    copresence.to_csv(COPRESENCE_PATH, index=False)
    comparison.to_csv(COMPARISON_PATH, index=False)

    plot_model_selection(selection)
    plot_cluster_sizes(profiles)
    plot_rssi_profiles(profiles)
    plot_cluster_timeline(timeline)
    plot_copresence(copresence)
    plot_comparison(comparison)

    print("\nModel selection:")
    print(selection.to_string(index=False))
    print("\nCluster profiles:")
    print(
        profiles[
            [
                "role",
                "cluster",
                "training_windows",
                "predicted_windows",
                "dominant_strongest_beacon",
                "dominant_mapped_location",
                "mean_rssi_confidence_score",
            ]
        ].to_string(index=False)
    )
    print("\nCo-presence summary:")
    print(copresence.to_string(index=False))
    print("\nMethod comparison:")
    print(comparison.to_string(index=False))
    print("\nSaved outputs:")
    for path in [
        TRAINING_PATH,
        MODEL_SELECTION_PATH,
        PROFILE_PATH,
        TIMELINE_PATH,
        COPRESENCE_PATH,
        COMPARISON_PATH,
        MODEL_SELECTION_FIG,
        CLUSTER_SIZE_FIG,
        RSSI_PROFILE_FIG,
        TIMELINE_FIG,
        COPRESENCE_FIG,
        COMPARISON_FIG,
    ]:
        print(path)


if __name__ == "__main__":
    main()
