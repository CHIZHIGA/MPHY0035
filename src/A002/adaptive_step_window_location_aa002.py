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

# Chosen from the previous threshold experiment:
# 10min <= 10 steps gives high-confidence low-motion periods;
# 5min <= 20 steps expands coverage while still avoiding high-motion windows.
ADAPTIVE_10MIN_STEP_MAX = 10
ADAPTIVE_5MIN_STEP_MAX = 20
ADAPTIVE_10MIN_STABILITY_MIN = 0.70
ADAPTIVE_5MIN_STABILITY_MIN = 0.60
ADAPTIVE_10MIN_GAP_MIN = 3.0
ADAPTIVE_5MIN_GAP_MIN = 2.0

RSSI_FILES = {
    "0805": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_0805.csv"),
    "6AA8": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_6AA8.csv"),
    "8248": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_8248.csv"),
    "ACC6": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_ACC6.csv"),
    "BA31": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_BA31.csv"),
}

METRICS_PATH = os.path.join(RESULTS_DIR, "AA002_adaptive_step_window_location_metrics.csv")
PREDICTIONS_PATH = os.path.join(RESULTS_DIR, "AA002_adaptive_step_window_location_predictions.csv")
CONFIDENCE_METRICS_PATH = os.path.join(
    RESULTS_DIR,
    "AA002_rssi_stability_confidence_metrics.csv",
)


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

    return pd.concat(frames, ignore_index=True).sort_values("time")


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
# Window features
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
    max_strongest_prop = strongest_prop_frame.max(axis=1)
    strongest_second_gap_series = mean_rssi.apply(strongest_second_gap, axis=1)
    features = pd.concat(
        [
            mean_rssi.add_prefix("mean_"),
            strongest_prop_frame,
            count_features,
        ],
        axis=1,
    )
    features["strongest_beacon"] = strongest
    features["max_strongest_prop"] = max_strongest_prop
    features["strongest_second_gap"] = strongest_second_gap_series
    features["total_rssi_samples"] = count_features.sum(axis=1)
    return features.loc[features["total_rssi_samples"] > 0].copy()


def build_step_windows(steps, window):
    window_minutes = pd.to_timedelta(window).total_seconds() / 60.0
    windows = steps.resample(window).agg(
        steps_in_window=("step_increment", "sum"),
        step_samples=("step_count", "count"),
    )
    windows["steps_per_minute"] = windows["steps_in_window"] / window_minutes
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


def build_window_tables(rssi_samples, step_samples, annotations):
    tables = {}
    for window in WINDOWS:
        rssi = build_rssi_windows(rssi_samples, window)
        steps = build_step_windows(step_samples, window)
        features = rssi.join(steps, how="left")
        features = features.fillna(
            {
                "steps_in_window": 0,
                "step_samples": 0,
                "steps_per_minute": 0,
            }
        )
        labelled = assign_reference_labels(features, annotations, window)
        tables[window] = labelled
    return tables


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


def calibrate_strongest_beacon(train_df):
    return majority_label_mapping(train_df, "strongest_beacon")


def predict_strongest_beacon(test_df, mapping, fallback):
    return test_df["strongest_beacon"].map(mapping).fillna(fallback)


def choose_adaptive_window(row):
    if row["steps_10min"] <= ADAPTIVE_10MIN_STEP_MAX:
        return "10min"
    if row["steps_5min"] <= ADAPTIVE_5MIN_STEP_MAX:
        return "5min"
    return "1min"


def choose_stability_adaptive_window(row):
    ten_min_stable = (
        row["steps_10min"] <= ADAPTIVE_10MIN_STEP_MAX
        and row["stability_10min"] >= ADAPTIVE_10MIN_STABILITY_MIN
        and row["gap_10min"] >= ADAPTIVE_10MIN_GAP_MIN
    )
    if ten_min_stable:
        return "10min"

    five_min_stable = (
        row["steps_5min"] <= ADAPTIVE_5MIN_STEP_MAX
        and row["stability_5min"] >= ADAPTIVE_5MIN_STABILITY_MIN
        and row["gap_5min"] >= ADAPTIVE_5MIN_GAP_MIN
    )
    if five_min_stable:
        return "5min"

    return "1min"


def confidence_label(row):
    high_confidence = (
        row["steps_10min"] <= ADAPTIVE_10MIN_STEP_MAX
        and row["stability_10min"] >= ADAPTIVE_10MIN_STABILITY_MIN
        and row["gap_10min"] >= ADAPTIVE_10MIN_GAP_MIN
    )
    if high_confidence:
        return "High"

    medium_confidence = (
        row["steps_10min"] <= 100
        and row["stability_10min"] >= 0.50
        and row["gap_10min"] >= 1.0
    )
    if medium_confidence:
        return "Medium"

    return "Low"


def confidence_score(row):
    step_score = max(0.0, 1.0 - min(row["steps_10min"], 100) / 100.0)
    stability_score = min(max(row["stability_10min"], 0.0), 1.0)
    gap_score = min(max(row["gap_10min"], 0.0), 10.0) / 10.0
    return 0.40 * step_score + 0.40 * stability_score + 0.20 * gap_score


def floor_to_window(index, window):
    return pd.Series(index, index=index).dt.floor(window)


def anchor_table(tables):
    anchors = tables["1min"][
        [
            "reference_location",
            "annotation_overlap_fraction",
        ]
    ].copy()
    anchors["time_1min"] = anchors.index

    for window in WINDOWS:
        floored = floor_to_window(anchors.index, window)
        anchors[f"time_{window}"] = floored.values
        anchors[f"steps_{window}"] = (
            tables[window]
            .reindex(floored.values)["steps_in_window"]
            .fillna(0)
            .values
        )
        anchors[f"stability_{window}"] = (
            tables[window]
            .reindex(floored.values)["max_strongest_prop"]
            .fillna(0)
            .values
        )
        anchors[f"gap_{window}"] = (
            tables[window]
            .reindex(floored.values)["strongest_second_gap"]
            .fillna(0)
            .values
        )

    anchors["adaptive_window"] = anchors.apply(choose_adaptive_window, axis=1)
    anchors["stability_adaptive_window"] = anchors.apply(
        choose_stability_adaptive_window,
        axis=1,
    )
    anchors["confidence_label"] = anchors.apply(confidence_label, axis=1)
    anchors["confidence_score"] = anchors.apply(confidence_score, axis=1)
    return anchors


# =====================================
# Evaluation
# =====================================

def train_calibrations(tables, train_dates):
    calibrations = {}
    for window, table in tables.items():
        train_df = table.loc[pd.Series(table.index.date, index=table.index).isin(train_dates)]
        strongest_mapping, strongest_fallback = calibrate_strongest_beacon(train_df)
        calibrations[window] = (strongest_mapping, strongest_fallback)
    return calibrations


def predict_fixed_window(anchor_df, tables, calibrations, window):
    window_times = anchor_df[f"time_{window}"]
    feature_df = tables[window].reindex(window_times.values)
    feature_df.index = anchor_df.index

    mapping, fallback = calibrations[window]
    return predict_strongest_beacon(feature_df, mapping, fallback)


def predict_adaptive(anchor_df, tables, calibrations):
    output = pd.Series(index=anchor_df.index, dtype=object)
    for window in WINDOWS:
        mask = anchor_df["adaptive_window"] == window
        if not mask.any():
            continue
        output.loc[mask] = predict_fixed_window(
            anchor_df.loc[mask],
            tables,
            calibrations,
            window,
        )
    return output


def predict_stability_adaptive(anchor_df, tables, calibrations):
    output = pd.Series(index=anchor_df.index, dtype=object)
    for window in WINDOWS:
        mask = anchor_df["stability_adaptive_window"] == window
        if not mask.any():
            continue
        output.loc[mask] = predict_fixed_window(
            anchor_df.loc[mask],
            tables,
            calibrations,
            window,
        )
    return output


def evaluate(tables):
    anchors = anchor_table(tables)
    groups = anchors.index.date
    n_splits = min(5, pd.Series(groups).nunique())
    splitter = GroupKFold(n_splits=n_splits)
    predictions = []

    methods = []
    for window in WINDOWS:
        methods.append((f"pure_rssi_{window}_strongest", window, "fixed"))
    methods.append(("adaptive_step_window_strongest", None, "adaptive"))
    methods.append(
        (
            "adaptive_step_rssi_stability_strongest",
            None,
            "stability_adaptive",
        )
    )

    for fold, (train_idx, test_idx) in enumerate(
        splitter.split(anchors, anchors["reference_location"], groups),
        start=1,
    ):
        train_dates = set(pd.Series(groups[train_idx]).unique())
        test_anchors = anchors.iloc[test_idx]
        calibrations = train_calibrations(tables, train_dates)

        for method, window, mode in methods:
            if mode == "fixed":
                pred = predict_fixed_window(
                    test_anchors,
                    tables,
                    calibrations,
                    window,
                )
                selected_window = window
            else:
                if mode == "adaptive":
                    pred = predict_adaptive(test_anchors, tables, calibrations)
                    selected_window = test_anchors["adaptive_window"].values
                else:
                    pred = predict_stability_adaptive(
                        test_anchors,
                        tables,
                        calibrations,
                    )
                    selected_window = test_anchors["stability_adaptive_window"].values

            predictions.append(
                pd.DataFrame(
                    {
                        "fold": fold,
                        "time": test_anchors.index,
                        "method": method,
                        "mode": mode,
                        "selected_window": selected_window,
                        "reference_location": test_anchors["reference_location"].values,
                        "predicted_location": pred.values,
                        "steps_1min": test_anchors["steps_1min"].values,
                        "steps_5min": test_anchors["steps_5min"].values,
                        "steps_10min": test_anchors["steps_10min"].values,
                        "adaptive_window": test_anchors["adaptive_window"].values,
                        "stability_adaptive_window": test_anchors[
                            "stability_adaptive_window"
                        ].values,
                        "stability_1min": test_anchors["stability_1min"].values,
                        "stability_5min": test_anchors["stability_5min"].values,
                        "stability_10min": test_anchors["stability_10min"].values,
                        "gap_1min": test_anchors["gap_1min"].values,
                        "gap_5min": test_anchors["gap_5min"].values,
                        "gap_10min": test_anchors["gap_10min"].values,
                        "confidence_label": test_anchors["confidence_label"].values,
                        "confidence_score": test_anchors["confidence_score"].values,
                    }
                )
            )

    return pd.concat(predictions, ignore_index=True)


def summarize(predictions):
    rows = []
    for method, group in predictions.groupby("method"):
        row = {
            "method": method,
            "mode": group["mode"].iloc[0],
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
            "n_anchor_windows": len(group),
        }
        for window in WINDOWS:
            row[f"selected_{window}_fraction"] = (
                group["selected_window"].eq(window).mean()
            )
        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        ["accuracy"],
        ascending=[False],
    )


def summarize_confidence(predictions):
    baseline = predictions.loc[
        predictions["method"] == "pure_rssi_10min_strongest"
    ].copy()
    rows = []
    for confidence, group in baseline.groupby("confidence_label"):
        rows.append(
            {
                "confidence_label": confidence,
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
                "n_windows": len(group),
                "coverage": len(group) / len(baseline),
                "mean_confidence_score": group["confidence_score"].mean(),
                "mean_steps_10min": group["steps_10min"].mean(),
                "mean_stability_10min": group["stability_10min"].mean(),
                "mean_gap_10min": group["gap_10min"].mean(),
            }
        )

    order = {"High": 0, "Medium": 1, "Low": 2}
    summary = pd.DataFrame(rows)
    summary["order"] = summary["confidence_label"].map(order)
    return summary.sort_values("order").drop(columns=["order"])


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

    print("Building fixed 1min/5min/10min windows...")
    tables = build_window_tables(rssi_samples, step_samples, annotations)
    for window, table in tables.items():
        print(
            f"{window}: {len(table):,} labelled windows, "
            f"{table['reference_location'].nunique()} locations"
        )

    print("Evaluating pure RSSI fixed windows vs step-aware adaptive windows...")
    predictions = evaluate(tables)
    metrics = summarize(predictions)
    confidence_metrics = summarize_confidence(predictions)

    predictions.to_csv(PREDICTIONS_PATH, index=False)
    metrics.to_csv(METRICS_PATH, index=False)
    confidence_metrics.to_csv(CONFIDENCE_METRICS_PATH, index=False)

    print("\nAdaptive step-window comparison:")
    print(metrics.to_string(index=False))
    print("\n10min strongest-beacon confidence groups:")
    print(confidence_metrics.to_string(index=False))
    print(f"\nSaved predictions: {PREDICTIONS_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Saved confidence metrics: {CONFIDENCE_METRICS_PATH}")


if __name__ == "__main__":
    main()
