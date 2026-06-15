import json
import os
import uuid
from datetime import time

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_A002", "AA002")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")
os.makedirs(RESULTS_DIR, exist_ok=True)

ACC_PATH = os.path.join(DATA_DIR, "SAMPLES_HE_ACC.csv")
STEP_PATH = os.path.join(DATA_DIR, "SAMPLES_Step_count.csv")

STEP_JSON_PATH = os.path.join(DATA_DIR, "auto_activity_level_steps_10min.json")
ACC_JSON_PATH = os.path.join(DATA_DIR, "auto_activity_level_acc_10min.json")
FUSED_JSON_PATH = os.path.join(DATA_DIR, "auto_activity_level_fused_10min.json")
COMPARISON_CSV_PATH = os.path.join(RESULTS_DIR, "AA002_activity_level_comparison_10min.csv")

WINDOW = "10min"
ACC_CHUNKSIZE = 1_000_000
RANDOM_STATE = 42

ACTIVITY_LABELS = [
    "Sleep",
    "Sedentary",
    "Light activity",
    "Moderate to Vigorous activity",
]


# =====================================
# Time and label helpers
# =====================================

def annotation_string(value):
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def is_night_time(value):
    current = value.time()
    return current >= time(22, 0) or current < time(7, 0)


def low_night_mask(index, metric, threshold):
    return pd.Series(
        [is_night_time(value) for value in index],
        index=index,
        dtype=bool,
    ) & (metric <= threshold)


def thresholds(series, quantiles):
    clean = series.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return [0 for _ in quantiles]
    return clean.quantile(quantiles).tolist()


def label_by_threshold(value, low_cut, high_cut):
    if pd.isna(value):
        return "Sedentary"
    if value <= low_cut:
        return "Sedentary"
    if value <= high_cut:
        return "Light activity"
    return "Moderate to Vigorous activity"


# =====================================
# Loading and aggregation
# =====================================

def load_step_windows():
    cols = ["timestamp_ms", "timestamp_str", "step_count"]
    steps = pd.read_csv(STEP_PATH, header=None, names=cols)
    steps["time"] = pd.to_datetime(steps["timestamp_ms"], unit="ms")
    steps = steps.sort_values("time").set_index("time")

    step_diff = steps["step_count"].diff().fillna(0)
    step_diff = step_diff.clip(lower=0)
    steps["steps_10min_source"] = step_diff

    windows = steps["steps_10min_source"].resample(WINDOW).sum().to_frame("steps_10min")
    windows["step_samples"] = steps["step_count"].resample(WINDOW).count()
    return windows


def load_acc_windows():
    cols = ["timestamp_ms", "timestamp_str", "acc_x", "acc_y", "acc_z"]
    partials = []

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
        chunk = chunk.set_index("time")

        acc_x = chunk["acc_x"].astype("float64")
        acc_y = chunk["acc_y"].astype("float64")
        acc_z = chunk["acc_z"].astype("float64")
        acc_mag = np.sqrt(acc_x.pow(2) + acc_y.pow(2) + acc_z.pow(2))

        chunk_features = pd.DataFrame(
            {
                "acc_mag": acc_mag,
                "acc_mag_sq": acc_mag.pow(2),
            },
            index=chunk.index,
        )
        grouped = chunk_features.resample(WINDOW).agg(
            acc_count=("acc_mag", "count"),
            acc_sum=("acc_mag", "sum"),
            acc_sumsq=("acc_mag_sq", "sum"),
            acc_min=("acc_mag", "min"),
            acc_max=("acc_mag", "max"),
        )
        partials.append(grouped)

        if chunk_no % 5 == 0:
            print(f"  processed {chunk_no * ACC_CHUNKSIZE:,} acceleration rows...")

    partials = pd.concat(partials)
    combined = partials.groupby(level=0).agg(
        acc_count=("acc_count", "sum"),
        acc_sum=("acc_sum", "sum"),
        acc_sumsq=("acc_sumsq", "sum"),
        acc_min=("acc_min", "min"),
        acc_max=("acc_max", "max"),
    )
    combined["acc_mean"] = combined["acc_sum"] / combined["acc_count"]
    variance = (combined["acc_sumsq"] / combined["acc_count"]) - combined["acc_mean"].pow(2)
    combined["acc_std"] = np.sqrt(variance.clip(lower=0))
    combined["acc_range"] = combined["acc_max"] - combined["acc_min"]

    result = combined[["acc_count", "acc_mean", "acc_std", "acc_range"]]
    return result


def build_common_windows(step_windows, acc_windows):
    start = min(step_windows.index.min(), acc_windows.index.min())
    end = max(step_windows.index.max(), acc_windows.index.max())
    common_index = pd.date_range(start=start.floor(WINDOW), end=end.floor(WINDOW), freq=WINDOW)
    windows = pd.DataFrame(index=common_index)
    windows = windows.join(step_windows, how="left").join(acc_windows, how="left")
    windows["steps_10min"] = windows["steps_10min"].fillna(0)
    windows["step_samples"] = windows["step_samples"].fillna(0)
    windows["acc_count"] = windows["acc_count"].fillna(0)
    return windows


# =====================================
# Activity estimation
# =====================================

def estimate_from_steps(windows):
    active_steps = windows.loc[windows["steps_10min"] > 0, "steps_10min"]
    sed_cut, light_cut = thresholds(active_steps, [0.40, 0.80])
    sed_cut = max(10, min(40, sed_cut))
    light_cut = max(80, min(180, light_cut))
    sleep_cut = max(5, min(15, sed_cut / 2))

    labels = windows["steps_10min"].apply(
        lambda value: label_by_threshold(value, sed_cut, light_cut)
    )
    labels.loc[low_night_mask(windows.index, windows["steps_10min"], sleep_cut)] = "Sleep"
    return labels


def estimate_from_acc(windows):
    metric = windows["acc_std"].fillna(0)
    active_metric = metric[metric > 0]
    sed_cut, light_cut = thresholds(active_metric, [0.40, 0.80])
    sleep_cut = thresholds(active_metric, [0.20])[0] if not active_metric.empty else 0

    labels = metric.apply(lambda value: label_by_threshold(value, sed_cut, light_cut))
    labels.loc[low_night_mask(windows.index, metric, sleep_cut)] = "Sleep"
    return labels


def estimate_fused(windows):
    feature_frame = pd.DataFrame(index=windows.index)
    feature_frame["steps_10min"] = windows["steps_10min"].fillna(0)
    feature_frame["acc_std"] = windows["acc_std"].fillna(0)
    feature_frame["acc_range"] = windows["acc_range"].fillna(0)
    feature_frame["has_step"] = (windows["step_samples"].fillna(0) > 0).astype(int)
    feature_frame["has_acc"] = (windows["acc_count"].fillna(0) > 0).astype(int)

    valid = feature_frame["has_acc"] == 1
    labels = pd.Series("Sedentary", index=windows.index, dtype=object)
    if valid.sum() < 4:
        return labels

    model_features = feature_frame.loc[valid].copy()
    # Acceleration is weighted higher because it captures non-walking movement.
    model_features["acc_std"] = model_features["acc_std"] * 1.5
    model_features["acc_range"] = model_features["acc_range"] * 1.5

    scaled = StandardScaler().fit_transform(model_features)
    kmeans = KMeans(n_clusters=4, random_state=RANDOM_STATE, n_init=20)
    clusters = pd.Series(kmeans.fit_predict(scaled), index=model_features.index)

    intensity = model_features["acc_std"] + 0.40 * model_features["acc_range"] + 1.25 * model_features["steps_10min"]
    cluster_order = intensity.groupby(clusters).median().sort_values().index.tolist()
    cluster_to_label = {
        cluster_order[0]: "Sedentary",
        cluster_order[1]: "Sedentary",
        cluster_order[2]: "Light activity",
        cluster_order[3]: "Moderate to Vigorous activity",
    }
    labels.loc[valid] = clusters.map(cluster_to_label)

    sleep_metric = windows["acc_std"].fillna(0) + windows["steps_10min"].fillna(0)
    sleep_cut = thresholds(sleep_metric[sleep_metric > 0], [0.20])[0]
    labels.loc[low_night_mask(windows.index, sleep_metric, sleep_cut)] = "Sleep"
    return labels


# =====================================
# JSON output
# =====================================

def make_shape(start, end, label, author, sensor):
    return {
        "start": int(start.value // 1_000_000),
        "end": int(end.value // 1_000_000),
        "annotation_start": annotation_string(start),
        "annotation_end": annotation_string(end),
        "author": author,
        "insert_date": None,
        "sensor": sensor,
        "type": "timerange",
        "uuid": str(uuid.uuid4()),
        "data": {"activityLevel": label},
    }


def labels_to_shapes(labels, author, sensor):
    shapes = []
    current_label = None
    current_start = None
    previous_start = None

    for start, label in labels.items():
        if label not in ACTIVITY_LABELS:
            label = "Sedentary"
        if current_label is None:
            current_label = label
            current_start = start
        elif label != current_label:
            shapes.append(
                make_shape(
                    current_start,
                    previous_start + pd.Timedelta(WINDOW),
                    current_label,
                    author,
                    sensor,
                )
            )
            current_label = label
            current_start = start
        previous_start = start

    if current_label is not None and previous_start is not None:
        shapes.append(
            make_shape(
                current_start,
                previous_start + pd.Timedelta(WINDOW),
                current_label,
                author,
                sensor,
            )
        )
    return shapes


def write_activity_json(labels, path, author, sensor):
    payload = {
        "pdhGmtOffset": "+0",
        "pdh_gmt_offset": "+0",
        "points": [],
        "shapes": labels_to_shapes(labels, author, sensor),
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=4)


# =====================================
# Validation and reporting
# =====================================

def validate_shapes(path):
    with open(path, "r") as f:
        payload = json.load(f)

    previous_end = None
    for shape in payload.get("shapes", []):
        if shape["start"] >= shape["end"]:
            raise ValueError(f"Invalid interval in {path}: {shape}")
        if previous_end is not None and shape["start"] < previous_end:
            raise ValueError(f"Overlapping intervals in {path}: {shape}")
        label = shape.get("data", {}).get("activityLevel")
        if label not in ACTIVITY_LABELS:
            raise ValueError(f"Invalid label in {path}: {label}")
        previous_end = shape["end"]


def print_summary(windows):
    print("\nLabel distributions:")
    for col in ["step_activityLevel", "acc_activityLevel", "fused_activityLevel"]:
        print(f"\n{col}:")
        print(windows[col].value_counts().reindex(ACTIVITY_LABELS, fill_value=0).to_string())

    agreement = windows["step_vs_acc_agree"].mean() * 100
    print(f"\nStep vs acceleration agreement: {agreement:.1f}%")

    disagreement = windows.loc[~windows["step_vs_acc_agree"]].copy()
    if not disagreement.empty:
        disagreement["disagreement_score"] = (
            disagreement["steps_10min"].rank(pct=True)
            - disagreement["acc_metric"].rank(pct=True)
        ).abs()
        cols = [
            "start",
            "end",
            "steps_10min",
            "acc_metric",
            "step_activityLevel",
            "acc_activityLevel",
            "fused_activityLevel",
        ]
        print("\nHigh-disagreement examples:")
        print(disagreement.sort_values("disagreement_score", ascending=False).head(8)[cols].to_string(index=False))


def main():
    print(f"Loading step count data from: {STEP_PATH}")
    step_windows = load_step_windows()
    print(f"Step windows: {len(step_windows)}")

    print(f"Loading acceleration data from: {ACC_PATH}")
    acc_windows = load_acc_windows()
    print(f"Acceleration windows: {len(acc_windows)}")

    windows = build_common_windows(step_windows, acc_windows)
    windows["step_activityLevel"] = estimate_from_steps(windows)
    windows["acc_activityLevel"] = estimate_from_acc(windows)
    windows["fused_activityLevel"] = estimate_fused(windows)
    windows["acc_metric"] = windows["acc_std"].fillna(0)
    windows["step_vs_acc_agree"] = windows["step_activityLevel"] == windows["acc_activityLevel"]

    comparison = windows.reset_index(names="start")
    comparison["end"] = comparison["start"] + pd.Timedelta(WINDOW)
    comparison = comparison[
        [
            "start",
            "end",
            "steps_10min",
            "step_activityLevel",
            "acc_metric",
            "acc_activityLevel",
            "fused_activityLevel",
            "step_vs_acc_agree",
        ]
    ]
    comparison.to_csv(COMPARISON_CSV_PATH, index=False)

    write_activity_json(windows["step_activityLevel"], STEP_JSON_PATH, "AUTO_activity_level_steps_10min", "Step_count")
    write_activity_json(windows["acc_activityLevel"], ACC_JSON_PATH, "AUTO_activity_level_acc_10min", "HE_ACC")
    write_activity_json(windows["fused_activityLevel"], FUSED_JSON_PATH, "AUTO_activity_level_fused_10min", "HE_ACC + Step_count")

    for path in [STEP_JSON_PATH, ACC_JSON_PATH, FUSED_JSON_PATH]:
        validate_shapes(path)

    print_summary(comparison)
    print("\nSaved outputs:")
    print(f"  {STEP_JSON_PATH}")
    print(f"  {ACC_JSON_PATH}")
    print(f"  {FUSED_JSON_PATH}")
    print(f"  {COMPARISON_CSV_PATH}")


if __name__ == "__main__":
    main()
