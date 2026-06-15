import json
import os
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_A002", "AA002")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")
os.makedirs(RESULTS_DIR, exist_ok=True)

ANNOTATION_PATH = os.path.join(DATA_DIR, "annotator.json")
RAW_TAGS_PATH = os.path.join(DATA_DIR, "SAMPLES_tags.csv")
WINDOWS = ["1min", "5min", "10min"]

RSSI_FILES = {
    "0805": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_0805.csv"),
    "6AA8": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_6AA8.csv"),
    "8248": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_8248.csv"),
    "ACC6": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_ACC6.csv"),
    "BA31": os.path.join(DATA_DIR, "SAMPLES_TAGS_RSSI_BA31.csv"),
}

INFO_TAG_CODE_MAP = {
    "08": "0805",
    "6A": "6AA8",
    "82": "8248",
    "AC": "ACC6",
    "BA": "BA31",
}

SUMMARY_PATH = os.path.join(RESULTS_DIR, "AA002_rssi_annotation_alignment_diagnostics.csv")
CONFUSION_PATH = os.path.join(
    RESULTS_DIR,
    "AA002_rssi_annotation_alignment_beacon_location_counts.csv",
)


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


def parse_other_tags(value):
    if pd.isna(value):
        return []

    readings = []
    for item in str(value).split(";"):
        parts = item.strip().split()
        if len(parts) != 2:
            continue
        rssi_text, code = parts
        beacon = INFO_TAG_CODE_MAP.get(code.upper())
        if beacon is None:
            continue
        try:
            rssi = float(rssi_text)
        except ValueError:
            continue
        readings.append((beacon, rssi))
    return readings


def load_raw_tag_vector_samples():
    raw = pd.read_csv(RAW_TAGS_PATH, low_memory=False, on_bad_lines="skip")
    raw["timestamp_ms"] = pd.to_numeric(raw["time"], errors="coerce")
    raw["rssi"] = pd.to_numeric(raw["rssi"], errors="coerce")
    raw["main_beacon"] = raw["uuid"].astype(str).str[:4]
    raw = raw.dropna(subset=["timestamp_ms", "rssi"])
    raw = raw.loc[raw["main_beacon"].isin(RSSI_FILES)]

    records = []
    for row in raw.itertuples(index=False):
        time = pd.to_datetime(row.timestamp_ms, unit="ms")
        records.append(
            {
                "time": time,
                "beacon": row.main_beacon,
                "rssi": row.rssi,
            }
        )
        for beacon, rssi in parse_other_tags(row.info_other_tags):
            records.append(
                {
                    "time": time,
                    "beacon": beacon,
                    "rssi": rssi,
                }
            )

    samples = pd.DataFrame(records)
    return samples.sort_values("time")


def load_annotations():
    with open(ANNOTATION_PATH, "r") as f:
        annot = json.load(f)

    records = []
    for shape in annot.get("shapes", []):
        if shape.get("type") != "timerange":
            continue
        location = shape.get("data", {}).get("location")
        if not location:
            continue
        records.append(
            {
                "start": pd.to_datetime(shape["start"], unit="ms"),
                "end": pd.to_datetime(shape["end"], unit="ms"),
                "sensor": shape.get("sensor", "Unknown"),
                "location": location,
            }
        )
    return pd.DataFrame(records).sort_values("start")


def winner(values, direction):
    clean = values.dropna()
    if clean.empty:
        return None
    if direction == "max":
        return clean.idxmax()
    if direction == "min":
        return clean.idxmin()
    raise ValueError(f"Unknown direction: {direction}")


def build_rssi_windows(samples, window):
    pivot = samples.pivot_table(
        index="time",
        columns="beacon",
        values="rssi",
        aggfunc="mean",
    ).sort_index()

    mean_rssi = pivot.resample(window).mean()
    out = pd.DataFrame(index=mean_rssi.index)
    out["mean_max_beacon"] = mean_rssi.apply(winner, axis=1, direction="max")
    out["mean_min_beacon"] = mean_rssi.apply(winner, axis=1, direction="min")
    out["sample_count"] = pivot.resample(window).count().sum(axis=1)

    prop_rows = []
    for start, window_frame in pivot.resample(window):
        if window_frame.empty:
            continue
        max_winners = window_frame.apply(winner, axis=1, direction="max").dropna()
        min_winners = window_frame.apply(winner, axis=1, direction="min").dropna()
        prop_rows.append(
            {
                "time": start,
                "prop_max_beacon": (
                    max_winners.value_counts().idxmax()
                    if not max_winners.empty
                    else None
                ),
                "prop_min_beacon": (
                    min_winners.value_counts().idxmax()
                    if not min_winners.empty
                    else None
                ),
                "prop_max_fraction": (
                    max_winners.value_counts(normalize=True).max()
                    if not max_winners.empty
                    else np.nan
                ),
                "prop_min_fraction": (
                    min_winners.value_counts(normalize=True).max()
                    if not min_winners.empty
                    else np.nan
                ),
            }
        )

    props = pd.DataFrame(prop_rows).set_index("time")
    out = out.join(props, how="left")
    return out.loc[out["sample_count"] > 0].copy()


def assign_reference_labels(windows, annotations, window):
    labelled = windows.copy()
    window_delta = pd.to_timedelta(window)
    labels = []
    sensors = []
    overlaps = []

    for start in labelled.index:
        end = start + window_delta
        possible = annotations[
            (annotations["start"] < end) & (annotations["end"] > start)
        ]

        overlap_by_pair = Counter()
        for _, row in possible.iterrows():
            overlap_start = max(start, row["start"])
            overlap_end = min(end, row["end"])
            seconds = max((overlap_end - overlap_start).total_seconds(), 0)
            if seconds > 0:
                overlap_by_pair[(row["location"], row["sensor"])] += seconds

        if overlap_by_pair:
            (label, sensor), seconds = overlap_by_pair.most_common(1)[0]
            labels.append(label)
            sensors.append(sensor)
            overlaps.append(seconds / window_delta.total_seconds())
        else:
            labels.append(np.nan)
            sensors.append(np.nan)
            overlaps.append(0.0)

    labelled["reference_location"] = labels
    labelled["reference_sensor"] = sensors
    labelled["annotation_overlap_fraction"] = overlaps
    labelled = labelled.dropna(subset=["reference_location"])
    return labelled.loc[labelled["annotation_overlap_fraction"] >= 0.5].copy()


def majority_mapping(df, beacon_col):
    mapping = {}
    for beacon, group in df.groupby(beacon_col):
        if pd.isna(beacon):
            continue
        mapping[beacon] = group["reference_location"].mode().iloc[0]
    fallback = df["reference_location"].mode().iloc[0]
    return mapping, fallback


def evaluate_with_global_mapping(labelled, beacon_col):
    clean = labelled.dropna(subset=[beacon_col, "reference_location"]).copy()
    mapping, fallback = majority_mapping(clean, beacon_col)
    pred = clean[beacon_col].map(mapping).fillna(fallback)
    return clean, pred, mapping


def main():
    rssi_sources = {
        "split_rssi_files": load_rssi_samples(),
        "raw_tags_with_other_beacons": load_raw_tag_vector_samples(),
    }
    annotations = load_annotations()

    print("Annotation intervals by sensor:")
    print(annotations["sensor"].value_counts().to_string())
    print("\nAnnotation duration by sensor (hours):")
    duration_hours = (
        (annotations["end"] - annotations["start"]).dt.total_seconds() / 3600
    )
    print(duration_hours.groupby(annotations["sensor"]).sum().to_string())

    rows = []
    beacon_location_rows = []
    for source_name, rssi in rssi_sources.items():
        print(f"\nRSSI source: {source_name}")
        print(f"RSSI rows: {len(rssi):,}")
        for window in WINDOWS:
            features = build_rssi_windows(rssi, window)
            labelled_all = assign_reference_labels(features, annotations, window)

            for reference_set, labelled in [
                ("all_annotation_sensors", labelled_all),
                (
                    "beacons_rssi_annotations_only",
                    labelled_all.loc[
                        labelled_all["reference_sensor"] == "Beacons RSSI"
                    ],
                ),
            ]:
                for beacon_col in [
                    "mean_max_beacon",
                    "prop_max_beacon",
                    "mean_min_beacon",
                    "prop_min_beacon",
                ]:
                    clean, pred, mapping = evaluate_with_global_mapping(
                        labelled,
                        beacon_col,
                    )
                    rows.append(
                        {
                            "rssi_source": source_name,
                            "window": window,
                            "reference_set": reference_set,
                            "beacon_rule": beacon_col,
                            "agreement_global_mapping": accuracy_score(
                                clean["reference_location"],
                                pred,
                            ),
                            "n_windows": len(clean),
                            "n_reference_locations": clean[
                                "reference_location"
                            ].nunique(),
                            "mapping": "; ".join(
                                f"{beacon}->{location}"
                                for beacon, location in sorted(mapping.items())
                            ),
                        }
                    )

                    if (
                        source_name == "raw_tags_with_other_beacons"
                        and reference_set == "beacons_rssi_annotations_only"
                        and beacon_col == "prop_max_beacon"
                    ):
                        counts = pd.crosstab(
                            clean[beacon_col],
                            clean["reference_location"],
                        )
                        for beacon in counts.index:
                            for location in counts.columns:
                                beacon_location_rows.append(
                                    {
                                        "rssi_source": source_name,
                                        "window": window,
                                        "beacon": beacon,
                                        "location": location,
                                        "n_windows": int(
                                            counts.loc[beacon, location]
                                        ),
                                    }
                                )

    summary = pd.DataFrame(rows).sort_values(
        ["rssi_source", "reference_set", "window", "agreement_global_mapping"],
        ascending=[True, True, True, False],
    )
    summary.to_csv(SUMMARY_PATH, index=False)
    pd.DataFrame(beacon_location_rows).to_csv(CONFUSION_PATH, index=False)

    print("\nRSSI/annotation alignment diagnostics:")
    print(summary.to_string(index=False))
    print(f"\nSaved diagnostics: {SUMMARY_PATH}")
    print(f"Saved beacon-location counts: {CONFUSION_PATH}")


if __name__ == "__main__":
    main()
