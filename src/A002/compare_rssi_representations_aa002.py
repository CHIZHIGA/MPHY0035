import json
import os
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
)
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
ACC_PATH = os.path.join(DATA_DIR, "SAMPLES_HE_ACC.csv")
WINDOWS = ["1min", "5min", "10min"]
ACC_CHUNKSIZE = 1_000_000
FILL_RSSI = -110.0

RSSI_FILES = {
    "0805": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_0805.csv"),
    "6AA8": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_6AA8.csv"),
    "8248": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_8248.csv"),
    "ACC6": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_ACC6.csv"),
    "BA31": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_BA31.csv"),
}

METRICS_PATH = os.path.join(RESULTS_DIR, "AA002_rssi_representation_metrics.csv")
PREDICTIONS_PATH = os.path.join(RESULTS_DIR, "AA002_rssi_representation_predictions.csv")
CONFUSION_PATH = os.path.join(RESULTS_DIR, "AA002_rssi_representation_confusion_matrix.csv")


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
    samples = samples.sort_values("time")
    return samples


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


def load_step_samples():
    cols = ["timestamp_ms", "timestamp_str", "step_count"]
    steps = pd.read_csv(STEP_PATH, header=None, names=cols)
    steps["time"] = pd.to_datetime(steps["timestamp_ms"], unit="ms")
    steps["step_count"] = pd.to_numeric(steps["step_count"], errors="coerce")
    steps = steps.dropna(subset=["time", "step_count"])
    steps = steps.sort_values("time").set_index("time")

    step_diff = steps["step_count"].diff().fillna(0).clip(lower=0)
    steps["step_increment"] = step_diff
    return steps


# =====================================
# Feature extraction
# =====================================

def strongest_beacon(values):
    clean = values.dropna()
    if clean.empty:
        return None
    return clean.idxmax()


def strongest_second_gap(values):
    clean = values.dropna().sort_values(ascending=False)
    if len(clean) < 2:
        return np.nan
    return clean.iloc[0] - clean.iloc[1]


def build_rssi_windows(samples, window):
    pivot = (
        samples.pivot_table(
            index="time",
            columns="beacon",
            values="rssi",
            aggfunc="mean",
        )
        .sort_index()
    )

    mean_features = pivot.resample(window).mean().add_prefix("mean_")
    median_features = pivot.resample(window).median().add_prefix("median_")
    max_features = pivot.resample(window).max().add_prefix("max_")
    var_features = pivot.resample(window).var().add_prefix("var_")
    count_features = pivot.resample(window).count().add_prefix("count_")

    mean_rssi = pivot.resample(window).mean()
    strongest = mean_rssi.apply(strongest_beacon, axis=1)
    gap = mean_rssi.apply(strongest_second_gap, axis=1)

    strongest_counts = []
    for start, window_frame in pivot.resample(window):
        if window_frame.empty:
            continue

        row_winners = window_frame.apply(strongest_beacon, axis=1).dropna()
        counts = row_winners.value_counts(normalize=True)
        row = {"time": start}
        for beacon in RSSI_FILES:
            row[f"strongest_prop_{beacon}"] = counts.get(beacon, 0.0)
        strongest_counts.append(row)

    strongest_props = pd.DataFrame(strongest_counts).set_index("time")

    features = pd.concat(
        [
            mean_features,
            median_features,
            max_features,
            var_features,
            count_features,
            strongest_props,
        ],
        axis=1,
    )
    features["strongest_beacon"] = strongest
    features["strongest_second_gap"] = gap
    features["total_rssi_samples"] = count_features.sum(axis=1)
    features = features.loc[features["total_rssi_samples"] > 0].copy()
    return features


def build_step_windows(steps, window):
    window_minutes = pd.to_timedelta(window).total_seconds() / 60.0
    grouped = steps.resample(window).agg(
        steps_in_window=("step_increment", "sum"),
        step_samples=("step_count", "count"),
        step_count_start=("step_count", "first"),
        step_count_end=("step_count", "last"),
    )
    grouped["steps_per_minute"] = grouped["steps_in_window"] / window_minutes
    active_steps = grouped.loc[grouped["steps_in_window"] > 0, "steps_in_window"]
    low_motion_cut = active_steps.quantile(0.25) if not active_steps.empty else 0
    grouped["low_step_motion"] = (
        grouped["steps_in_window"].fillna(0) <= low_motion_cut
    ).astype(int)
    grouped["has_step_data"] = (grouped["step_samples"].fillna(0) > 0).astype(int)
    return grouped


def load_acc_windows_by_window():
    cols = ["timestamp_ms", "timestamp_str", "acc_x", "acc_y", "acc_z"]
    partials_by_window = {window: [] for window in WINDOWS}

    for chunk_no, chunk in enumerate(
        pd.read_csv(
            ACC_PATH,
            header=None,
            names=cols,
            chunksize=ACC_CHUNKSIZE,
            low_memory=False,
        ),
        start=1,
    ):
        chunk["time"] = pd.to_datetime(chunk["timestamp_ms"], unit="ms")
        chunk = chunk.dropna(subset=["time"]).set_index("time")

        acc_x = pd.to_numeric(chunk["acc_x"], errors="coerce")
        acc_y = pd.to_numeric(chunk["acc_y"], errors="coerce")
        acc_z = pd.to_numeric(chunk["acc_z"], errors="coerce")
        acc_mag = np.sqrt(acc_x.pow(2) + acc_y.pow(2) + acc_z.pow(2))
        acc_frame = pd.DataFrame(
            {
                "acc_mag": acc_mag,
                "acc_mag_sq": acc_mag.pow(2),
            },
            index=chunk.index,
        ).dropna(subset=["acc_mag"])

        for window in WINDOWS:
            grouped = acc_frame.resample(window).agg(
                acc_count=("acc_mag", "count"),
                acc_sum=("acc_mag", "sum"),
                acc_sumsq=("acc_mag_sq", "sum"),
                acc_min=("acc_mag", "min"),
                acc_max=("acc_mag", "max"),
            )
            partials_by_window[window].append(grouped)

        if chunk_no % 5 == 0:
            print(f"  processed {chunk_no * ACC_CHUNKSIZE:,} acceleration rows...")

    windows_by_window = {}
    for window, partials in partials_by_window.items():
        partial_frame = pd.concat(partials)
        combined = partial_frame.groupby(level=0).agg(
            acc_count=("acc_count", "sum"),
            acc_sum=("acc_sum", "sum"),
            acc_sumsq=("acc_sumsq", "sum"),
            acc_min=("acc_min", "min"),
            acc_max=("acc_max", "max"),
        )
        combined["acc_mean"] = combined["acc_sum"] / combined["acc_count"]
        variance = (
            combined["acc_sumsq"] / combined["acc_count"]
        ) - combined["acc_mean"].pow(2)
        combined["acc_std"] = np.sqrt(variance.clip(lower=0))
        combined["acc_range"] = combined["acc_max"] - combined["acc_min"]

        active_acc = combined.loc[combined["acc_count"] > 0, "acc_std"].dropna()
        low_variation_cut = active_acc.quantile(0.25) if not active_acc.empty else 0
        combined["low_acc_variation"] = (
            combined["acc_std"].fillna(0) <= low_variation_cut
        ).astype(int)
        combined["has_acc_data"] = (combined["acc_count"].fillna(0) > 0).astype(int)
        windows_by_window[window] = combined[
            [
                "acc_count",
                "acc_mean",
                "acc_std",
                "acc_range",
                "low_acc_variation",
                "has_acc_data",
            ]
        ]

    return windows_by_window


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
    labelled = labelled.loc[labelled["annotation_overlap_fraction"] >= 0.5].copy()
    return labelled


# =====================================
# Evaluation helpers
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
    frame = df[columns].replace([np.inf, -np.inf], np.nan).copy()
    fill_values = {}
    for col in columns:
        if col.startswith(("mean_", "median_", "max_")):
            fill_values[col] = FILL_RSSI
        else:
            fill_values[col] = 0
    return frame.fillna(fill_values)


def calibrate_room_signatures(train_df, columns):
    train_features = numeric_frame(train_df, columns)
    center = train_features.mean()
    scale = train_features.std().replace(0, 1).fillna(1)
    scaled_features = (train_features - center) / scale
    signatures = scaled_features.groupby(train_df["reference_location"]).median()
    fallback = train_df["reference_location"].mode().iloc[0]
    return signatures, center, scale, fallback


def predict_signature_match(train_df, test_df, columns):
    signatures, center, scale, fallback = calibrate_room_signatures(train_df, columns)
    if signatures.empty:
        return pd.Series(fallback, index=test_df.index)

    test_features = (numeric_frame(test_df, columns) - center) / scale
    distances = pd.DataFrame(index=test_df.index)
    for location, signature in signatures.iterrows():
        diff = test_features - signature
        distances[location] = np.sqrt(diff.pow(2).sum(axis=1))

    predictions = distances.idxmin(axis=1).fillna(fallback)
    return predictions


def algorithm_specs(feature_frame):
    full_vector_cols = [f"mean_{beacon}" for beacon in RSSI_FILES]
    step_cols = [
        "steps_in_window",
        "step_samples",
        "steps_per_minute",
        "low_step_motion",
        "has_step_data",
    ]
    acc_cols = [
        "acc_count",
        "acc_mean",
        "acc_std",
        "acc_range",
        "low_acc_variation",
        "has_acc_data",
    ]
    summary_cols = [
        col
        for col in feature_frame.columns
        if col.startswith(("mean_", "median_", "max_", "var_", "count_", "strongest_prop_"))
    ]
    summary_cols.append("strongest_second_gap")
    summary_step_cols = summary_cols + step_cols
    summary_acc_cols = summary_cols + acc_cols
    summary_step_acc_cols = summary_cols + step_cols + acc_cols
    full_vector_step_cols = full_vector_cols + step_cols
    full_vector_acc_cols = full_vector_cols + acc_cols
    full_vector_step_acc_cols = full_vector_cols + step_cols + acc_cols

    return {
        "strongest_beacon_majority": {
            "type": "rule",
            "columns": [],
        },
        "summary_signature_match": {
            "type": "signature",
            "columns": summary_cols,
        },
        "summary_plus_step_signature_match": {
            "type": "signature",
            "columns": summary_step_cols,
        },
        "summary_plus_acc_signature_match": {
            "type": "signature",
            "columns": summary_acc_cols,
        },
        "summary_plus_step_acc_signature_match": {
            "type": "signature",
            "columns": summary_step_acc_cols,
        },
        "full_rssi_vector_signature_match": {
            "type": "signature",
            "columns": full_vector_cols,
        },
        "full_rssi_vector_plus_step_signature_match": {
            "type": "signature",
            "columns": full_vector_step_cols,
        },
        "full_rssi_vector_plus_acc_signature_match": {
            "type": "signature",
            "columns": full_vector_acc_cols,
        },
        "full_rssi_vector_plus_step_acc_signature_match": {
            "type": "signature",
            "columns": full_vector_step_acc_cols,
        },
    }


def evaluate_window(feature_frame, window):
    groups = feature_frame.index.date
    unique_groups = pd.Series(groups).nunique()
    n_splits = min(5, unique_groups)
    if n_splits < 2:
        raise ValueError(f"Need at least two dates for cross-validation at {window}.")

    splitter = GroupKFold(n_splits=n_splits)
    specs = algorithm_specs(feature_frame)
    predictions = []

    for fold, (train_idx, test_idx) in enumerate(
        splitter.split(feature_frame, feature_frame["reference_location"], groups),
        start=1,
    ):
        train_df = feature_frame.iloc[train_idx]
        test_df = feature_frame.iloc[test_idx]

        for method, spec in specs.items():
            if spec["type"] == "rule":
                pred = predict_strongest_beacon(train_df, test_df)
            else:
                pred = predict_signature_match(train_df, test_df, spec["columns"])

            fold_predictions = pd.DataFrame(
                {
                    "window": window,
                    "fold": fold,
                    "time": test_df.index,
                    "method": method,
                    "reference_location": test_df["reference_location"].values,
                    "predicted_location": pred.values,
                    "strongest_beacon": test_df["strongest_beacon"].values,
                    "annotation_overlap_fraction": test_df[
                        "annotation_overlap_fraction"
                    ].values,
                    "total_rssi_samples": test_df["total_rssi_samples"].values,
                    "steps_in_window": test_df["steps_in_window"].values,
                    "steps_per_minute": test_df["steps_per_minute"].values,
                    "low_step_motion": test_df["low_step_motion"].values,
                    "acc_mean": test_df["acc_mean"].values,
                    "acc_std": test_df["acc_std"].values,
                    "acc_range": test_df["acc_range"].values,
                    "low_acc_variation": test_df["low_acc_variation"].values,
                }
            )
            predictions.append(fold_predictions)

    return pd.concat(predictions, ignore_index=True)


def summarize_predictions(predictions):
    metric_rows = []
    confusion_rows = []

    for (window, method), group in predictions.groupby(["window", "method"]):
        labels = sorted(
            set(group["reference_location"].unique())
            | set(group["predicted_location"].unique())
        )
        acc = accuracy_score(group["reference_location"], group["predicted_location"])
        balanced_acc = balanced_accuracy_score(
            group["reference_location"],
            group["predicted_location"],
        )
        macro_f1 = f1_score(
            group["reference_location"],
            group["predicted_location"],
            average="macro",
            zero_division=0,
        )
        metric_rows.append(
            {
                "window": window,
                "method": method,
                "accuracy": acc,
                "balanced_accuracy": balanced_acc,
                "macro_f1": macro_f1,
                "n_windows": len(group),
                "n_reference_locations": group["reference_location"].nunique(),
            }
        )

        matrix = confusion_matrix(
            group["reference_location"],
            group["predicted_location"],
            labels=labels,
        )
        for true_idx, true_label in enumerate(labels):
            for pred_idx, pred_label in enumerate(labels):
                confusion_rows.append(
                    {
                        "window": window,
                        "method": method,
                        "reference_location": true_label,
                        "predicted_location": pred_label,
                        "count": int(matrix[true_idx, pred_idx]),
                    }
                )

    metrics = pd.DataFrame(metric_rows).sort_values(
        ["window", "balanced_accuracy"],
        ascending=[True, False],
    )
    confusion = pd.DataFrame(confusion_rows)
    return metrics, confusion


# =====================================
# Main
# =====================================

def main():
    print("Loading AA002 RSSI samples...")
    samples = load_rssi_samples()
    print(f"RSSI samples: {len(samples):,}")

    print("Loading AA002 room annotations...")
    annotations = load_location_annotations()
    print(f"Annotation intervals: {len(annotations):,}")

    print("Loading AA002 step count samples...")
    steps = load_step_samples()
    print(f"Step samples: {len(steps):,}")

    print("Loading and aggregating AA002 acceleration samples...")
    acc_windows_by_window = load_acc_windows_by_window()

    all_predictions = []
    for window in WINDOWS:
        print(f"\nBuilding RSSI features for {window} windows...")
        rssi_features = build_rssi_windows(samples, window)
        step_features = build_step_windows(steps, window)
        acc_features = acc_windows_by_window[window]
        features = rssi_features.join(step_features, how="left").join(acc_features, how="left")
        step_fill = {
            "steps_in_window": 0,
            "step_samples": 0,
            "steps_per_minute": 0,
            "low_step_motion": 1,
            "has_step_data": 0,
        }
        acc_fill = {
            "acc_count": 0,
            "acc_mean": 0,
            "acc_std": 0,
            "acc_range": 0,
            "low_acc_variation": 1,
            "has_acc_data": 0,
        }
        features = features.fillna({**step_fill, **acc_fill})
        labelled = assign_reference_labels(features, annotations, window)
        print(
            f"Labelled windows: {len(labelled):,} "
            f"({labelled['reference_location'].nunique()} locations)"
        )

        if labelled["reference_location"].nunique() < 2:
            print(f"Skipping {window}: fewer than two reference locations.")
            continue

        predictions = evaluate_window(labelled, window)
        all_predictions.append(predictions)

    if not all_predictions:
        raise ValueError("No RSSI representation experiments were evaluated.")

    predictions = pd.concat(all_predictions, ignore_index=True)
    metrics, confusion = summarize_predictions(predictions)

    predictions.to_csv(PREDICTIONS_PATH, index=False)
    metrics.to_csv(METRICS_PATH, index=False)
    confusion.to_csv(CONFUSION_PATH, index=False)

    print("\nRSSI representation comparison:")
    print(metrics.to_string(index=False))
    print(f"\nSaved predictions: {PREDICTIONS_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Saved confusion matrix: {CONFUSION_PATH}")


if __name__ == "__main__":
    main()
