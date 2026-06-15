import json
import os
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_A002", "AA002")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")
os.makedirs(RESULTS_DIR, exist_ok=True)

ANNOTATION_PATH = os.path.join(DATA_DIR, "annotator.json")
STEP_PATH = os.path.join(DATA_DIR, "SAMPLES_Step_count.csv")
WINDOWS = ["1min", "5min", "10min"]
STEP_THRESHOLDS = [0, 5, 10, 20, 30, 50, 100]
FILL_RSSI = -110.0

RSSI_FILES = {
    "0805": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_0805.csv"),
    "6AA8": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_6AA8.csv"),
    "8248": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_8248.csv"),
    "ACC6": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_ACC6.csv"),
    "BA31": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_BA31.csv"),
}

METRICS_PATH = os.path.join(RESULTS_DIR, "AA002_step_low_motion_location_metrics.csv")
PREDICTIONS_PATH = os.path.join(RESULTS_DIR, "AA002_step_low_motion_location_predictions.csv")


# =====================================
# Loading helpers
# =====================================

def load_rssi_samples():
    frames = []
    cols = ["timestamp_ms", "timestamp_str", "rssi"]

    for beacon, path in RSSI_FILES.items():
        frame = pd.read_csv(path, header=None, names=cols)
        frame["time"] = pd.to_datetime(frame["timestamp_ms"], unit="ms")
        frame["rssi"] = pd.to_numeric(frame["rssi"], errors="coerce")
        frame = frame.dropna(subset=["time", "rssi"])
        frame["beacon"] = beacon
        frames.append(frame[["time", "beacon", "rssi"]])

    samples = pd.concat(frames, ignore_index=True)
    return samples.sort_values("time")


def load_step_samples():
    cols = ["timestamp_ms", "timestamp_str", "step_count"]
    steps = pd.read_csv(STEP_PATH, header=None, names=cols)
    steps["time"] = pd.to_datetime(steps["timestamp_ms"], unit="ms")
    steps["step_count"] = pd.to_numeric(steps["step_count"], errors="coerce")
    steps = steps.dropna(subset=["time", "step_count"])
    steps = steps.sort_values("time").set_index("time")
    steps["step_increment"] = steps["step_count"].diff().fillna(0).clip(lower=0)
    return steps


def load_location_annotations():
    with open(ANNOTATION_PATH, "r") as f:
        annot = json.load(f)

    records = []
    for shape in annot.get("shapes", []):
        if shape.get("type") != "timerange":
            continue

        location = shape.get("data", {}).get("location")
        if location is None:
            continue

        records.append(
            {
                "start": pd.to_datetime(shape["start"], unit="ms"),
                "end": pd.to_datetime(shape["end"], unit="ms"),
                "location": location,
            }
        )

    annotations = pd.DataFrame(records)
    if annotations.empty:
        raise ValueError("No location annotations found for AA002.")
    return annotations.sort_values("start")


# =====================================
# Feature extraction
# =====================================

def strongest_beacon(values):
    clean = values.dropna()
    if clean.empty:
        return None
    return clean.idxmax()


def build_rssi_windows(samples, window):
    pivot = samples.pivot_table(
        index="time",
        columns="beacon",
        values="rssi",
        aggfunc="mean",
    ).sort_index()

    mean_rssi = pivot.resample(window).mean()
    count_features = pivot.resample(window).count().add_prefix("count_")
    strongest = mean_rssi.apply(strongest_beacon, axis=1)

    strongest_props = []
    for start, window_frame in pivot.resample(window):
        if window_frame.empty:
            continue

        row_winners = window_frame.apply(strongest_beacon, axis=1).dropna()
        counts = row_winners.value_counts(normalize=True)
        row = {"time": start}
        for beacon in RSSI_FILES:
            row[f"strongest_prop_{beacon}"] = counts.get(beacon, 0.0)
        strongest_props.append(row)

    strongest_prop_frame = pd.DataFrame(strongest_props).set_index("time")
    features = pd.concat(
        [
            mean_rssi.add_prefix("mean_"),
            strongest_prop_frame,
            count_features,
        ],
        axis=1,
    )
    features["strongest_beacon"] = strongest
    features["total_rssi_samples"] = count_features.sum(axis=1)
    return features.loc[features["total_rssi_samples"] > 0].copy()


def build_step_windows(steps, window):
    window_minutes = pd.to_timedelta(window).total_seconds() / 60.0
    windows = steps.resample(window).agg(
        steps_in_window=("step_increment", "sum"),
        step_samples=("step_count", "count"),
    )
    windows["steps_per_minute"] = windows["steps_in_window"] / window_minutes
    windows["has_step_data"] = (windows["step_samples"].fillna(0) > 0).astype(int)
    return windows


def assign_reference_labels(windows, annotations, window):
    labelled = windows.copy()
    labels = []
    overlaps = []
    window_delta = pd.to_timedelta(window)

    for start in labelled.index:
        end = start + window_delta
        overlap_by_location = Counter()
        possible = annotations[
            (annotations["start"] < end) & (annotations["end"] > start)
        ]

        for _, row in possible.iterrows():
            overlap_start = max(start, row["start"])
            overlap_end = min(end, row["end"])
            seconds = max((overlap_end - overlap_start).total_seconds(), 0)
            if seconds > 0:
                overlap_by_location[row["location"]] += seconds

        if overlap_by_location:
            label, seconds = overlap_by_location.most_common(1)[0]
            labels.append(label)
            overlaps.append(seconds / window_delta.total_seconds())
        else:
            labels.append(np.nan)
            overlaps.append(0.0)

    labelled["reference_location"] = labels
    labelled["annotation_overlap_fraction"] = overlaps
    labelled = labelled.dropna(subset=["reference_location"])
    return labelled.loc[labelled["annotation_overlap_fraction"] >= 0.5].copy()


# =====================================
# Location algorithms
# =====================================

def majority_label_mapping(train_df, key_col):
    mapping = {}
    for key, group in train_df.groupby(key_col):
        if pd.isna(key):
            continue
        mapping[key] = group["reference_location"].mode().iloc[0]
    fallback = train_df["reference_location"].mode().iloc[0]
    return mapping, fallback


def predict_strongest_beacon(train_df, test_df):
    mapping, fallback = majority_label_mapping(train_df, "strongest_beacon")
    return test_df["strongest_beacon"].map(mapping).fillna(fallback)


def numeric_frame(df, columns):
    frame = df[columns].replace([np.inf, -np.inf], np.nan)
    fill_values = {
        col: FILL_RSSI if col.startswith("mean_") else 0
        for col in columns
    }
    return frame.fillna(fill_values)


def predict_rssi_vector_signature(train_df, test_df):
    vector_cols = [f"mean_{beacon}" for beacon in RSSI_FILES]
    train_features = numeric_frame(train_df, vector_cols)
    center = train_features.mean()
    scale = train_features.std().replace(0, 1).fillna(1)
    scaled_train = (train_features - center) / scale
    signatures = scaled_train.groupby(train_df["reference_location"]).median()

    fallback = train_df["reference_location"].mode().iloc[0]
    if signatures.empty:
        return pd.Series(fallback, index=test_df.index)

    scaled_test = (numeric_frame(test_df, vector_cols) - center) / scale
    distances = pd.DataFrame(index=test_df.index)
    for location, signature in signatures.iterrows():
        diff = scaled_test - signature
        distances[location] = np.sqrt(diff.pow(2).sum(axis=1))
    return distances.idxmin(axis=1).fillna(fallback)


def algorithm_predictions(train_df, test_df):
    return {
        "strongest_beacon_low_motion": predict_strongest_beacon(train_df, test_df),
        "rssi_vector_signature_low_motion": predict_rssi_vector_signature(train_df, test_df),
    }


# =====================================
# Evaluation
# =====================================

def evaluate_thresholds(feature_frame, window):
    groups = feature_frame.index.date
    n_splits = min(5, pd.Series(groups).nunique())
    if n_splits < 2:
        raise ValueError(f"Need at least two dates for cross-validation at {window}.")

    splitter = GroupKFold(n_splits=n_splits)
    predictions = []

    for threshold in STEP_THRESHOLDS:
        threshold_frame = feature_frame.loc[
            feature_frame["steps_in_window"].fillna(0) <= threshold
        ].copy()
        if threshold_frame["reference_location"].nunique() < 2:
            continue

        threshold_groups = threshold_frame.index.date
        if pd.Series(threshold_groups).nunique() < 2:
            continue

        fold_splitter = GroupKFold(
            n_splits=min(n_splits, pd.Series(threshold_groups).nunique())
        )
        for fold, (train_idx, test_idx) in enumerate(
            fold_splitter.split(
                threshold_frame,
                threshold_frame["reference_location"],
                threshold_groups,
            ),
            start=1,
        ):
            train_df = threshold_frame.iloc[train_idx]
            test_df = threshold_frame.iloc[test_idx]

            for method, pred in algorithm_predictions(train_df, test_df).items():
                predictions.append(
                    pd.DataFrame(
                        {
                            "window": window,
                            "step_threshold": threshold,
                            "fold": fold,
                            "time": test_df.index,
                            "method": method,
                            "reference_location": test_df["reference_location"].values,
                            "predicted_location": pred.values,
                            "steps_in_window": test_df["steps_in_window"].values,
                            "steps_per_minute": test_df["steps_per_minute"].values,
                            "strongest_beacon": test_df["strongest_beacon"].values,
                            "total_rssi_samples": test_df["total_rssi_samples"].values,
                            "annotation_overlap_fraction": test_df[
                                "annotation_overlap_fraction"
                            ].values,
                        }
                    )
                )

    if not predictions:
        raise ValueError(f"No threshold experiments could be evaluated for {window}.")
    return pd.concat(predictions, ignore_index=True)


def summarize_predictions(predictions, total_labelled_by_window):
    rows = []
    for (window, threshold, method), group in predictions.groupby(
        ["window", "step_threshold", "method"]
    ):
        total_labelled = total_labelled_by_window[window]
        rows.append(
            {
                "window": window,
                "step_threshold": threshold,
                "method": method,
                "accuracy": accuracy_score(
                    group["reference_location"],
                    group["predicted_location"],
                ),
                "balanced_accuracy": balanced_accuracy_score(
                    group["reference_location"],
                    group["predicted_location"],
                ),
                "macro_f1": f1_score(
                    group["reference_location"],
                    group["predicted_location"],
                    average="macro",
                    zero_division=0,
                ),
                "n_low_motion_windows": len(group),
                "n_total_labelled_windows": total_labelled,
                "coverage": len(group) / total_labelled,
                "n_reference_locations": group["reference_location"].nunique(),
                "mean_steps_in_window": group["steps_in_window"].mean(),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["window", "step_threshold", "method"]
    )


# =====================================
# Adaptive-window extension placeholder
# =====================================

def adaptive_window_next_stage():
    """Reserved for the next stage.

    The fixed-window threshold experiment below identifies useful low-motion
    step thresholds. The next version can use those findings to expand windows
    during low-motion, stable-RSSI periods and shorten windows during movement.
    """


# =====================================
# Main
# =====================================

def main():
    print("Loading AA002 RSSI samples...")
    rssi_samples = load_rssi_samples()
    print(f"RSSI samples: {len(rssi_samples):,}")

    print("Loading AA002 step count samples...")
    step_samples = load_step_samples()
    print(f"Step samples: {len(step_samples):,}")

    print("Loading AA002 room annotations...")
    annotations = load_location_annotations()
    print(f"Annotation intervals: {len(annotations):,}")

    all_predictions = []
    total_labelled_by_window = {}
    for window in WINDOWS:
        print(f"\nBuilding {window} RSSI and step windows...")
        rssi_windows = build_rssi_windows(rssi_samples, window)
        step_windows = build_step_windows(step_samples, window)
        features = rssi_windows.join(step_windows, how="left")
        features = features.fillna(
            {
                "steps_in_window": 0,
                "step_samples": 0,
                "steps_per_minute": 0,
                "has_step_data": 0,
            }
        )
        labelled = assign_reference_labels(features, annotations, window)
        total_labelled_by_window[window] = len(labelled)
        print(
            f"Labelled windows: {len(labelled):,} "
            f"({labelled['reference_location'].nunique()} locations)"
        )

        predictions = evaluate_thresholds(labelled, window)
        all_predictions.append(predictions)

    predictions = pd.concat(all_predictions, ignore_index=True)
    metrics = summarize_predictions(predictions, total_labelled_by_window)

    predictions.to_csv(PREDICTIONS_PATH, index=False)
    metrics.to_csv(METRICS_PATH, index=False)

    print("\nStep low-motion threshold comparison:")
    print(metrics.to_string(index=False))
    print(f"\nSaved predictions: {PREDICTIONS_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")


if __name__ == "__main__":
    main()

