import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "labelledData"
RESULTS_DIR = ROOT / "Results" / "FifthPhase" / "Point1_5"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

WINDOWS = ["5min", "15min", "30min"]
LOW_MOTION_THRESHOLD = 10
MISSING_RSSI_VALUE = -100
K_CANDIDATES = [3, 4, 5, 6, 7, 8]
MIN_CLUSTER_FRACTION = 0.05
MIN_CLUSTER_TRAINING_WINDOWS = 10
MIN_CLUSTER_GAP = 8
WEAK_RSSI_GAP = 5
STRONG_RSSI_GAP = 8

METHODS = [
    ("Raw RSSI 5min strongest", "raw_rssi_5min_prediction"),
    ("Raw RSSI 15min strongest", "raw_rssi_15min_prediction"),
    ("Raw RSSI 30min strongest", "raw_rssi_30min_prediction"),
    ("4b step-adaptive RSSI threshold10", "step_adaptive_rssi_prediction"),
    ("4c low-motion RSSI cluster 30min", "cluster_30min_prediction"),
]

HYBRID_METHOD = ("Hybrid 4b + conditional cluster", "hybrid_step_cluster_prediction")

DATASETS = [
    {
        "dataset": "DH Paris",
        "raw_dir": DATA_DIR / "Paris NY2024" / "DH",
        "analysis_path": DATA_DIR / "Analysis" / "Analysis DH Paris.xlsx",
        "analysis_sheet": "output_15min_20240107_171435",
        "mapping_type": "beacon_workbook",
        "mapping_path": DATA_DIR / "Paris NY2024" / "beacons Paris NY 2024.xlsx",
    },
    {
        "dataset": "DH PanoH",
        "raw_dir": DATA_DIR / "DH DEC PANH",
        "analysis_path": DATA_DIR / "Analysis" / "data_analysed_DH_PanoH.xlsx",
        "analysis_sheet": "without fallen beacon",
        "mapping_type": "config_annotator",
        "mapping_path": DATA_DIR / "DH DEC PANH" / "CONFIG_ANNOTATOR.json",
    },
    {
        "dataset": "DH Strad",
        "raw_dir": DATA_DIR / "DH DEC STRAD",
        "analysis_path": DATA_DIR / "Analysis" / "data_analysed_DH_Strad.xlsx",
        "analysis_sheet": "data_analysed_DH_Strad",
        "mapping_type": "config_annotator",
        "mapping_path": DATA_DIR / "DH DEC STRAD" / "CONFIG_ANNOTATOR.json",
    },
    {
        "dataset": "KM Mal",
        "raw_dir": DATA_DIR / "KM DEC MAL",
        "analysis_path": DATA_DIR / "Analysis" / "data_analysed_KM_Mal.xlsx",
        "analysis_sheet": "analysis",
        "mapping_type": "config_annotator",
        "mapping_path": DATA_DIR / "KM DEC MAL" / "CONFIG_ANNOTATOR.json",
    },
]

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

ROOM_COLORS = {
    "Bedroom": "#f58518",
    "Living": "#72b7b2",
    "Dining": "#54a24b",
    "Kitchen": "#e45756",
    "Bathroom": "#4c78a8",
    "Toilet": "#9c755f",
    "Office": "#b279a2",
    "Out": "#8c8c8c",
    "Unmapped": "#b5b5b5",
    "Unknown": "#d0d0d0",
}


def xlsx_column_index(cell_ref):
    match = re.match(r"([A-Z]+)", str(cell_ref))
    letters = match.group(1) if match else "A"
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def read_shared_strings(zip_file):
    if "xl/sharedStrings.xml" not in zip_file.namelist():
        return []
    root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("a:si", NS):
        values.append("".join(text.text or "" for text in item.findall(".//a:t", NS)))
    return values


def cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//a:t", NS))
    value = cell.find("a:v", NS)
    if value is None:
        return ""
    raw = value.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def workbook_sheet_paths(zip_file):
    workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
    rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
    relmap = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("rel:Relationship", REL_NS)
    }
    paths = {}
    for sheet in workbook.findall(".//a:sheet", NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = relmap[rel_id]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        paths[name] = target
    return paths


def read_xlsx_rows(path, sheet_name=None):
    with zipfile.ZipFile(path) as zip_file:
        shared_strings = read_shared_strings(zip_file)
        sheet_paths = workbook_sheet_paths(zip_file)
        if sheet_name is None:
            sheet_name = next(iter(sheet_paths))
        sheet_path = sheet_paths.get(sheet_name)
        if sheet_path is None:
            raise ValueError(f"Sheet {sheet_name!r} not found in {path}")
        root = ET.fromstring(zip_file.read(sheet_path))
        rows = []
        for row in root.findall(".//a:sheetData/a:row", NS):
            values = []
            for cell in row.findall("a:c", NS):
                index = xlsx_column_index(cell.attrib.get("r", "A1"))
                while len(values) <= index:
                    values.append("")
                values[index] = cell_value(cell, shared_strings)
            rows.append(values)
        return rows


def rows_to_frame(rows):
    header_index = None
    for index, row in enumerate(rows):
        lowered = [str(value).strip().lower() for value in row]
        if "from_date" in lowered and "to_date" in lowered and "diary" in lowered:
            header_index = index
            break
    if header_index is None:
        raise ValueError("Could not find header row with from_date, to_date, and Diary")

    header = [str(value).strip() or f"unnamed_{i}" for i, value in enumerate(rows[header_index])]
    body = rows[header_index + 1 :]
    width = len(header)
    normalised = [row[:width] + [""] * max(0, width - len(row)) for row in body]
    frame = pd.DataFrame(normalised, columns=header)
    frame = frame.loc[frame["from_date"].astype(str).str.strip().ne("")].copy()
    return frame


def parse_excel_datetime(value):
    text = str(value).strip()
    if not text:
        return pd.NaT
    if re.fullmatch(r"\d+(\.\d+)?", text):
        number = float(text)
        if number > 20000:
            return pd.Timestamp("1899-12-30", tz="UTC") + pd.to_timedelta(number, unit="D")
    return pd.to_datetime(text, utc=True, errors="coerce")


def normalise_location(value):
    if pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    if not text:
        return "Unknown"
    lowered = text.lower()
    if lowered in {"?", "unknown", "nan"}:
        return "Unknown"
    if lowered in {"out", "outside", "away"}:
        return "Out"
    if "bedroom" in lowered:
        return "Bedroom"
    if "living" in lowered:
        return "Living"
    if "dining" in lowered:
        return "Dining"
    if "kitchen" in lowered:
        return "Kitchen"
    if "bathroom" in lowered:
        return "Bathroom"
    if "toilet" in lowered:
        return "Toilet"
    if "office" in lowered:
        return "Office"
    return text[:1].upper() + text[1:]


def load_reference(config):
    rows = read_xlsx_rows(config["analysis_path"], config["analysis_sheet"])
    frame = rows_to_frame(rows)
    diary_column = next(
        column for column in frame.columns if column.strip().lower() == "diary"
    )
    frame["from_date"] = frame["from_date"].map(parse_excel_datetime)
    frame["to_date"] = frame["to_date"].map(parse_excel_datetime)
    frame["reference_location"] = frame[diary_column].map(normalise_location)
    frame = frame.dropna(subset=["from_date", "to_date"]).copy()
    frame = frame.loc[frame["reference_location"].ne("Unknown")].copy()
    frame["window_start"] = frame["from_date"].dt.floor("15min")
    return frame[
        [
            "window_start",
            "from_date",
            "to_date",
            "reference_location",
        ]
    ].drop_duplicates("window_start")


def load_beacon_workbook_mapping(path):
    with zipfile.ZipFile(path) as zip_file:
        sheet_name = "Sheet1" if "Sheet1" in workbook_sheet_paths(zip_file) else None
    rows = read_xlsx_rows(path, sheet_name)
    mapping = {}
    for row in rows:
        if len(row) < 2:
            continue
        room_text = str(row[0]).strip()
        beacon = str(row[1]).strip().upper()
        if re.fullmatch(r"[0-9A-F]{4}", beacon):
            location = normalise_location(room_text)
            if location != "Unknown":
                mapping[beacon] = location
    return mapping


def load_config_mapping(path):
    with open(path, "r") as file:
        config = json.load(file)
    locations = config.get("tagsLocation", {})
    whitelist = {item.upper() for item in config.get("tagsWhitelist", [])}
    use_whitelist = bool(config.get("isWhitelistEnabled", False))
    mapping = {}
    for beacon, location in locations.items():
        beacon_id = str(beacon).upper()
        if use_whitelist and beacon_id not in whitelist:
            continue
        normalised = normalise_location(location)
        if normalised != "Unknown":
            mapping[beacon_id] = normalised
    return mapping


def load_beacon_mapping(config):
    if config["mapping_type"] == "beacon_workbook":
        return load_beacon_workbook_mapping(config["mapping_path"])
    return load_config_mapping(config["mapping_path"])


def load_raw_tags(raw_dir):
    path = raw_dir / "SAMPLES_tags.csv"
    tags = pd.read_csv(path, usecols=["time", "rssi", "uuid"], low_memory=False)
    tags["time_ms"] = pd.to_numeric(tags["time"], errors="coerce")
    tags["rssi"] = pd.to_numeric(tags["rssi"], errors="coerce")
    tags["beacon"] = tags["uuid"].astype(str).str.slice(0, 4).str.upper()
    tags = tags.dropna(subset=["time_ms", "rssi"])
    tags = tags.loc[tags["beacon"].str.fullmatch(r"[0-9A-F]{4}", na=False)].copy()
    tags["time"] = pd.to_datetime(tags["time_ms"], unit="ms", utc=True)
    return tags[["time", "beacon", "rssi"]].sort_values("time")


def load_step_count(raw_dir):
    path = raw_dir / "SAMPLES_Step_count.csv"
    if not path.exists():
        return pd.DataFrame(columns=["time", "step_count", "step_increment"])
    steps = pd.read_csv(path, header=None, names=["time_ms", "time_text", "step_count"])
    steps["time_ms"] = pd.to_numeric(steps["time_ms"], errors="coerce")
    steps["step_count"] = pd.to_numeric(steps["step_count"], errors="coerce")
    steps = steps.dropna(subset=["time_ms", "step_count"]).copy()
    steps["time"] = pd.to_datetime(steps["time_ms"], unit="ms", utc=True)
    steps = steps.sort_values("time")
    diff = steps["step_count"].diff()
    steps["step_increment"] = diff.where(diff.ge(0), np.nan).fillna(0)
    return steps[["time", "step_count", "step_increment"]]


def strongest_second_gap(values):
    clean = values.dropna().sort_values(ascending=False)
    if len(clean) < 2:
        return np.nan
    return clean.iloc[0] - clean.iloc[1]


def build_rssi_windows(tags, beacon_mapping, window):
    mapped = tags.loc[tags["beacon"].isin(beacon_mapping)].copy()
    if mapped.empty:
        return pd.DataFrame(
            columns=[
                "window_start",
                "prediction",
                "strongest_beacon",
                "strongest_rssi",
                "strongest_second_gap",
                "strongest_beacon_proportion",
                "rssi_sample_count",
            ]
        )
    mapped["window_start"] = mapped["time"].dt.floor(window)
    mean_rssi = (
        mapped.groupby(["window_start", "beacon"])["rssi"]
        .mean()
        .unstack("beacon")
        .sort_index()
    )
    counts = mapped.groupby("window_start").size().rename("rssi_sample_count")
    strongest_beacon = mean_rssi.idxmax(axis=1)
    strongest_rssi = mean_rssi.max(axis=1)
    gap = mean_rssi.apply(strongest_second_gap, axis=1)

    row_winners = mapped.loc[mapped.groupby("window_start")["rssi"].idxmax()]
    winner_counts = (
        row_winners.groupby(["window_start", "beacon"]).size().unstack("beacon").fillna(0)
    )
    strongest_prop = []
    for window_start, beacon in strongest_beacon.items():
        if window_start not in winner_counts.index or pd.isna(beacon):
            strongest_prop.append(np.nan)
            continue
        total = winner_counts.loc[window_start].sum()
        strongest_prop.append(
            winner_counts.loc[window_start].get(beacon, 0) / total if total else np.nan
        )

    output = pd.DataFrame(
        {
            "window_start": mean_rssi.index,
            "prediction": [beacon_mapping.get(beacon, "Unmapped") for beacon in strongest_beacon],
            "strongest_beacon": strongest_beacon.values,
            "strongest_rssi": strongest_rssi.values,
            "strongest_second_gap": gap.values,
            "strongest_beacon_proportion": strongest_prop,
        }
    )
    output = output.merge(counts.reset_index(), on="window_start", how="left")
    return output


def build_step_windows(steps, window):
    if steps.empty:
        return pd.DataFrame(columns=["window_start", "step_increment"])
    frame = steps.copy()
    frame["window_start"] = frame["time"].dt.floor(window)
    return (
        frame.groupby("window_start")["step_increment"]
        .sum()
        .rename("step_increment")
        .reset_index()
    )


def lookup_single_window(windows, timestamp, window):
    window_start = timestamp.floor(window)
    subset = windows.loc[windows["window_start"].eq(window_start)]
    if subset.empty:
        return {
            "prediction": "Out",
            "rssi_sample_count": 0,
            "strongest_second_gap": np.nan,
            "strongest_beacon": "",
        }
    row = subset.iloc[0]
    return {
        "prediction": row["prediction"],
        "rssi_sample_count": int(row["rssi_sample_count"]),
        "strongest_second_gap": row["strongest_second_gap"],
        "strongest_beacon": row["strongest_beacon"],
    }


def lookup_interval_mode(windows, start, end):
    subset = windows.loc[
        windows["window_start"].ge(start) & windows["window_start"].lt(end)
    ].copy()
    if subset.empty:
        return {
            "prediction": "Out",
            "rssi_sample_count": 0,
            "strongest_second_gap": np.nan,
            "strongest_beacon": "",
        }
    counts = subset.groupby("prediction")["rssi_sample_count"].sum()
    prediction = counts.sort_values(ascending=False).index[0]
    chosen = subset.loc[subset["prediction"].eq(prediction)]
    best = chosen.sort_values("rssi_sample_count", ascending=False).iloc[0]
    return {
        "prediction": prediction,
        "rssi_sample_count": int(subset["rssi_sample_count"].sum()),
        "strongest_second_gap": best["strongest_second_gap"],
        "strongest_beacon": best["strongest_beacon"],
    }


def reference_aligned_rssi_prediction(reference, windows, window):
    rows = []
    for ref in reference.itertuples(index=False):
        if window == "5min":
            result = lookup_interval_mode(windows, ref.from_date, ref.to_date)
        else:
            result = lookup_single_window(windows, ref.window_start, window)
        rows.append(result)
    return pd.DataFrame(rows)


def step_value(step_windows, timestamp, window):
    subset = step_windows.loc[step_windows["window_start"].eq(timestamp.floor(window))]
    if subset.empty:
        return 0.0
    return float(subset.iloc[0]["step_increment"])


def build_step_adaptive_predictions(reference, rssi_by_window, step_by_window):
    rows = []
    for ref in reference.itertuples(index=False):
        steps_30 = step_value(step_by_window["30min"], ref.window_start, "30min")
        steps_15 = step_value(step_by_window["15min"], ref.window_start, "15min")
        if steps_30 <= LOW_MOTION_THRESHOLD:
            selected = "30min"
            reason = "30min_low_step"
            result = lookup_single_window(rssi_by_window["30min"], ref.window_start, "30min")
        elif steps_15 <= LOW_MOTION_THRESHOLD:
            selected = "15min"
            reason = "15min_low_step"
            result = lookup_single_window(rssi_by_window["15min"], ref.window_start, "15min")
        else:
            selected = "5min"
            reason = "5min_high_motion"
            result = lookup_interval_mode(rssi_by_window["5min"], ref.from_date, ref.to_date)
        rows.append(
            {
                "step_adaptive_rssi_prediction": result["prediction"],
                "step_adaptive_selected_window": selected,
                "step_adaptive_reason": reason
                if result["rssi_sample_count"] > 0
                else f"{reason}_no_rssi",
                "step_adaptive_rssi_sample_count": result["rssi_sample_count"],
                "steps_30min": steps_30,
                "steps_15min": steps_15,
            }
        )
    return pd.DataFrame(rows)


def weak_or_ambiguous_location(location, gap, sample_count):
    return (
        pd.isna(gap)
        or gap < WEAK_RSSI_GAP
        or location in {"Unmapped", "Out"}
        or pd.isna(sample_count)
        or sample_count <= 0
    )


def strong_base_evidence(gap):
    return pd.notna(gap) and gap >= STRONG_RSSI_GAP


def build_cluster_windows(tags, steps, beacon_mapping):
    mapped = tags.loc[tags["beacon"].isin(beacon_mapping)].copy()
    beacons = sorted(beacon_mapping)
    if mapped.empty or not beacons:
        return pd.DataFrame(), []
    mapped["window_start"] = mapped["time"].dt.floor("30min")
    mean_rssi = (
        mapped.groupby(["window_start", "beacon"])["rssi"]
        .mean()
        .unstack("beacon")
        .reindex(columns=beacons)
        .sort_index()
    )
    counts = (
        mapped.groupby(["window_start", "beacon"])["rssi"]
        .count()
        .unstack("beacon")
        .reindex(columns=beacons)
        .reindex(mean_rssi.index)
    )
    observed = mean_rssi.where(counts > 0)
    total_samples = counts.sum(axis=1).fillna(0)
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

    features = mean_rssi.fillna(MISSING_RSSI_VALUE)
    features.columns = [f"rssi_{beacon}" for beacon in features.columns]
    output = features.reset_index()
    output["has_rssi"] = total_samples.gt(0).values
    output["total_rssi_samples"] = total_samples.values
    output["strongest_beacon"] = strongest_beacon.values
    output["strongest_location"] = [
        beacon_mapping.get(beacon, "Unmapped") if pd.notna(beacon) else "Unmapped"
        for beacon in strongest_beacon.values
    ]
    output["strongest_second_gap"] = (strongest_rssi - second_rssi).values
    step_windows = build_step_windows(steps, "30min")
    output = output.merge(step_windows, on="window_start", how="left")
    output["step_increment"] = output["step_increment"].fillna(0)
    output["low_motion_training_candidate"] = (
        output["step_increment"].le(LOW_MOTION_THRESHOLD) & output["has_rssi"]
    )
    return output, [column for column in output.columns if column.startswith("rssi_")]


def evaluate_cluster_k(feature_matrix):
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
        try:
            model = KMeans(n_clusters=k, random_state=42, n_init=20)
            labels = model.fit_predict(feature_matrix)
            if len(set(labels)) < 2:
                raise ValueError("single effective cluster")
            fractions = pd.Series(labels).value_counts(normalize=True)
            min_fraction = fractions.min()
            rows.append(
                {
                    "candidate_k": k,
                    "valid_candidate": bool(min_fraction >= MIN_CLUSTER_FRACTION),
                    "silhouette_score": silhouette_score(feature_matrix, labels),
                    "min_cluster_fraction": min_fraction,
                    "reason": "ok"
                    if min_fraction >= MIN_CLUSTER_FRACTION
                    else "small cluster",
                }
            )
        except Exception as error:
            rows.append(
                {
                    "candidate_k": k,
                    "valid_candidate": False,
                    "silhouette_score": np.nan,
                    "min_cluster_fraction": np.nan,
                    "reason": str(error)[:80],
                }
            )
    return pd.DataFrame(rows)


def select_cluster_k(selection):
    valid = selection.loc[selection["valid_candidate"]].copy()
    if valid.empty:
        valid = selection.dropna(subset=["silhouette_score"]).copy()
    if valid.empty:
        return None
    return int(
        valid.sort_values(
            ["silhouette_score", "candidate_k"],
            ascending=[False, True],
        ).iloc[0]["candidate_k"]
    )


def build_cluster_predictions(dataset, cluster_windows, feature_cols):
    status = {
        "dataset": dataset,
        "method": "4c low-motion RSSI cluster 30min",
        "status": "ok",
        "reason": "",
    }
    if cluster_windows.empty or not feature_cols:
        status.update(status="unavailable", reason="no mapped RSSI features")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), status
    training = cluster_windows.loc[cluster_windows["low_motion_training_candidate"]].copy()
    if len(training) < 4:
        status.update(status="unavailable", reason="fewer than 4 low-motion training windows")
        return pd.DataFrame(), training, pd.DataFrame(), pd.DataFrame(), status

    scaler = StandardScaler()
    train_features = scaler.fit_transform(training[feature_cols])
    selection = evaluate_cluster_k(train_features)
    selected_k = select_cluster_k(selection)
    if selected_k is None:
        status.update(status="unavailable", reason="no valid cluster model")
        return selection, training, pd.DataFrame(), pd.DataFrame(), status

    model = KMeans(n_clusters=selected_k, random_state=42, n_init=20)
    training["cluster"] = model.fit_predict(train_features)

    predicted = cluster_windows.copy()
    predicted["cluster"] = pd.NA
    has_rssi = predicted["has_rssi"]
    if has_rssi.any():
        predict_features = scaler.transform(predicted.loc[has_rssi, feature_cols])
        predicted.loc[has_rssi, "cluster"] = model.predict(predict_features)
    predicted["cluster"] = predicted["cluster"].astype("Int64")

    profiles = []
    for cluster, group in training.groupby("cluster"):
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
        profiles.append(
            {
                "dataset": dataset,
                "cluster": int(cluster),
                "training_windows": len(group),
                "predicted_windows": int(predicted["cluster"].eq(cluster).sum()),
                "dominant_strongest_beacon": dominant_beacon,
                "dominant_mapped_location": dominant_location,
                "mean_rssi_evidence_samples": group["total_rssi_samples"].mean(),
                "mean_signal_separation_gap": group["strongest_second_gap"].mean(),
                "mean_steps_training": group["step_increment"].mean(),
            }
        )
    profiles = pd.DataFrame(profiles)
    predicted = predicted.merge(
        profiles[
            [
                "cluster",
                "dominant_mapped_location",
                "training_windows",
                "mean_signal_separation_gap",
            ]
        ],
        on="cluster",
        how="left",
    )
    predicted["cluster_30min_prediction"] = np.where(
        predicted["has_rssi"] & predicted["dominant_mapped_location"].notna(),
        predicted["dominant_mapped_location"],
        "Out",
    )
    selection["dataset"] = dataset
    selection["selected_k"] = selected_k
    selection["training_windows"] = len(training)
    training["dataset"] = dataset
    predicted["dataset"] = dataset
    return selection, training, profiles, predicted, status


def build_reference_predictions(config):
    dataset = config["dataset"]
    reference = load_reference(config)
    beacon_mapping = load_beacon_mapping(config)
    tags = load_raw_tags(config["raw_dir"])
    steps = load_step_count(config["raw_dir"])

    rssi_by_window = {
        window: build_rssi_windows(tags, beacon_mapping, window) for window in WINDOWS
    }
    step_by_window = {
        window: build_step_windows(steps, window) for window in WINDOWS
    }
    predictions = reference.copy()
    for window in WINDOWS:
        aligned = reference_aligned_rssi_prediction(reference, rssi_by_window[window], window)
        predictions[f"raw_rssi_{window}_prediction"] = aligned["prediction"].values
        predictions[f"raw_rssi_{window}_sample_count"] = aligned["rssi_sample_count"].values
        predictions[f"raw_rssi_{window}_second_gap"] = aligned["strongest_second_gap"].values
        predictions[f"raw_rssi_{window}_strongest_beacon"] = aligned["strongest_beacon"].values

    adaptive = build_step_adaptive_predictions(reference, rssi_by_window, step_by_window)
    predictions = pd.concat([predictions.reset_index(drop=True), adaptive], axis=1)

    cluster_windows, feature_cols = build_cluster_windows(tags, steps, beacon_mapping)
    selection, training, profiles, cluster_predictions, cluster_status = build_cluster_predictions(
        dataset,
        cluster_windows,
        feature_cols,
    )
    if cluster_predictions.empty:
        predictions["cluster_30min_prediction"] = "Out"
        predictions["cluster_30min_training_windows"] = np.nan
        predictions["cluster_30min_profile_gap"] = np.nan
    else:
        helper = cluster_predictions[
            [
                "window_start",
                "cluster_30min_prediction",
                "training_windows",
                "mean_signal_separation_gap",
            ]
        ].rename(columns={"window_start": "cluster_join_time"})
        predictions["cluster_join_time"] = predictions["window_start"].dt.floor("30min")
        predictions = predictions.merge(helper, on="cluster_join_time", how="left")
        predictions["cluster_30min_prediction"] = predictions[
            "cluster_30min_prediction"
        ].fillna("Out")
        predictions = predictions.rename(
            columns={
                "training_windows": "cluster_30min_training_windows",
                "mean_signal_separation_gap": "cluster_30min_profile_gap",
            }
        )

    hybrid_rows = []
    for row in predictions.itertuples(index=False):
        selected_window = row.step_adaptive_selected_window
        base_location = row.step_adaptive_rssi_prediction
        cluster_location = row.cluster_30min_prediction
        cluster_training = row.cluster_30min_training_windows
        cluster_gap = row.cluster_30min_profile_gap
        base_gap = getattr(row, f"raw_rssi_{selected_window}_second_gap")
        base_samples = getattr(row, f"raw_rssi_{selected_window}_sample_count")

        low_motion_candidate = selected_window == "30min"
        usable_cluster = (
            cluster_location not in {"Unmapped", "Out"}
            and pd.notna(cluster_training)
            and cluster_training >= MIN_CLUSTER_TRAINING_WINDOWS
            and pd.notna(cluster_gap)
            and cluster_gap >= MIN_CLUSTER_GAP
        )
        weak_base = weak_or_ambiguous_location(base_location, base_gap, base_samples)
        strong_base = strong_base_evidence(base_gap)

        final_location = base_location
        final_source = "step_adaptive_rssi"
        override_used = False
        if not low_motion_candidate:
            reason = "not_30min_low_motion"
        elif not usable_cluster:
            reason = "cluster_not_usable"
        elif strong_base:
            reason = "strong_4b_evidence"
        elif weak_base:
            final_location = cluster_location
            final_source = "cluster_override"
            override_used = True
            reason = "low_motion_weak_4b"
        else:
            reason = "4b_not_ambiguous"

        hybrid_rows.append(
            {
                "hybrid_step_cluster_prediction": final_location,
                "hybrid_final_source": final_source,
                "hybrid_cluster_override_used": override_used,
                "hybrid_override_reason": reason,
                "hybrid_base_rssi_gap": base_gap,
                "hybrid_cluster_profile_gap": cluster_gap,
            }
        )
    predictions = pd.concat(
        [predictions.reset_index(drop=True), pd.DataFrame(hybrid_rows)],
        axis=1,
    )

    predictions["dataset"] = dataset
    manifest = {
        "dataset": dataset,
        "raw_dir": str(config["raw_dir"].relative_to(ROOT)),
        "analysis_path": str(config["analysis_path"].relative_to(ROOT)),
        "analysis_sheet": config["analysis_sheet"],
        "reference_rows": len(reference),
        "raw_rssi_rows": len(tags),
        "step_rows": len(steps),
        "mapped_beacons": len(beacon_mapping),
        "reference_start": reference["from_date"].min(),
        "reference_end": reference["to_date"].max(),
    }
    return predictions, manifest, selection, training, profiles, cluster_status


def predictions_to_long(predictions):
    rows = []
    for method, column in METHODS:
        frame = predictions[
            [
                "dataset",
                "window_start",
                "from_date",
                "to_date",
                "reference_location",
                column,
            ]
        ].copy()
        frame = frame.rename(columns={column: "predicted_location"})
        frame["method"] = method
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def hybrid_predictions_to_long(predictions):
    method, column = HYBRID_METHOD
    frame = predictions[
        [
            "dataset",
            "window_start",
            "from_date",
            "to_date",
            "reference_location",
            column,
            "hybrid_final_source",
            "hybrid_cluster_override_used",
            "hybrid_override_reason",
        ]
    ].copy()
    frame = frame.rename(columns={column: "predicted_location"})
    frame["method"] = method
    return frame


def metric_rows(long_predictions):
    rows = []
    for (dataset, method), group in long_predictions.groupby(["dataset", "method"]):
        valid = group.dropna(subset=["reference_location", "predicted_location"])
        correct = valid["reference_location"].eq(valid["predicted_location"])
        recalls = []
        for label, label_group in valid.groupby("reference_location"):
            recalls.append(label_group["predicted_location"].eq(label).mean())
        rows.append(
            {
                "dataset": dataset,
                "method": method,
                "n_windows": len(valid),
                "accuracy": correct.mean() if len(valid) else np.nan,
                "balanced_accuracy": float(np.mean(recalls)) if recalls else np.nan,
                "reference_labels": ", ".join(sorted(valid["reference_location"].unique())),
            }
        )
    return pd.DataFrame(rows)


def confusion_rows(long_predictions):
    rows = []
    for (dataset, method), group in long_predictions.groupby(["dataset", "method"]):
        labels = sorted(set(group["reference_location"]) | set(group["predicted_location"]))
        for actual in labels:
            actual_mask = group["reference_location"].eq(actual)
            for predicted in labels:
                rows.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "actual": actual,
                        "predicted": predicted,
                        "count": int((actual_mask & group["predicted_location"].eq(predicted)).sum()),
                    }
                )
    return pd.DataFrame(rows)


def per_location_recall_rows(long_predictions):
    rows = []
    for (dataset, method, location), group in long_predictions.groupby(
        ["dataset", "method", "reference_location"]
    ):
        rows.append(
            {
                "dataset": dataset,
                "method": method,
                "reference_location": location,
                "n_windows": len(group),
                "recall": group["predicted_location"].eq(location).mean(),
                "most_common_prediction": group["predicted_location"].mode().iat[0]
                if not group["predicted_location"].mode().empty
                else "",
            }
        )
    return pd.DataFrame(rows)


def positive_negative_agreement_rows(long_predictions):
    rows = []
    for (dataset, method), group in long_predictions.groupby(["dataset", "method"]):
        locations = sorted(set(group["reference_location"]) | set(group["predicted_location"]))
        for location in locations:
            positive = group["reference_location"].eq(location)
            negative = ~positive
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "location": location,
                    "positive_windows": int(positive.sum()),
                    "negative_windows": int(negative.sum()),
                    "positive_percent_agreement": group.loc[
                        positive, "predicted_location"
                    ].eq(location).mean()
                    if positive.any()
                    else np.nan,
                    "negative_percent_agreement": group.loc[
                        negative, "predicted_location"
                    ].ne(location).mean()
                    if negative.any()
                    else np.nan,
                }
            )
    return pd.DataFrame(rows)


def pairwise_agreement_rows(long_predictions):
    rows = []
    for dataset, group in long_predictions.groupby("dataset"):
        wide = group.pivot_table(
            index="window_start",
            columns="method",
            values="predicted_location",
            aggfunc="first",
        )
        methods = list(wide.columns)
        for method_a in methods:
            for method_b in methods:
                comparable = pd.DataFrame(
                    {
                        "method_a": wide[method_a],
                        "method_b": wide[method_b],
                    }
                ).dropna()
                if comparable.empty:
                    agreement = np.nan
                else:
                    agreement = comparable["method_a"].eq(comparable["method_b"]).mean()
                rows.append(
                    {
                        "dataset": dataset,
                        "method_a": method_a,
                        "method_b": method_b,
                        "n_windows": len(comparable),
                        "agreement_fraction": agreement,
                        "difference_fraction": 1 - agreement if pd.notna(agreement) else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def hybrid_override_summary(predictions):
    rows = []
    for dataset, group in predictions.groupby("dataset"):
        counts = group["hybrid_override_reason"].value_counts()
        total = len(group)
        for reason, count in counts.items():
            rows.append(
                {
                    "dataset": dataset,
                    "override_reason": reason,
                    "windows": int(count),
                    "fraction": count / total if total else np.nan,
                }
            )
        rows.append(
            {
                "dataset": dataset,
                "override_reason": "cluster_override_used_total",
                "windows": int(group["hybrid_cluster_override_used"].sum()),
                "fraction": group["hybrid_cluster_override_used"].mean()
                if total
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def build_palette(values):
    palette = dict(ROOM_COLORS)
    cmap = plt.get_cmap("tab20")
    for value in sorted(set(values)):
        if value not in palette:
            palette[value] = cmap(len(palette) % 20)
    return palette


def plot_metrics_summary(metrics):
    order = [method for method, _ in METHODS]
    datasets = sorted(metrics["dataset"].unique())
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for ax, metric, title in [
        (axes[0], "accuracy", "Accuracy against Diary reference"),
        (axes[1], "balanced_accuracy", "Balanced accuracy against Diary reference"),
    ]:
        pivot = metrics.pivot(index="method", columns="dataset", values=metric).reindex(order)
        x = np.arange(len(order))
        width = 0.8 / max(len(datasets), 1)
        for index, dataset in enumerate(datasets):
            ax.bar(
                x - 0.4 + width / 2 + index * width,
                pivot[dataset],
                width,
                label=dataset,
            )
        ax.set_ylim(0, 1)
        ax.set_ylabel("Score")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)
    axes[1].set_xticks(np.arange(len(order)))
    axes[1].set_xticklabels(order, rotation=20, ha="right")
    axes[0].legend(loc="center left", bbox_to_anchor=(1.01, 0.5), title="Dataset")
    fig.tight_layout()
    output = RESULTS_DIR / "labelled_algorithm_metrics_summary.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_balanced_accuracy_by_dataset(metrics):
    order = [method for method, _ in METHODS]
    datasets = sorted(metrics["dataset"].unique())
    fig, axes = plt.subplots(len(datasets), 1, figsize=(11, 3.2 * len(datasets)))
    if len(datasets) == 1:
        axes = [axes]
    for ax, dataset in zip(axes, datasets):
        subset = metrics.loc[metrics["dataset"].eq(dataset)].set_index("method").reindex(order)
        ax.barh(order, subset["balanced_accuracy"], color="#4c78a8")
        ax.set_xlim(0, 1)
        ax.set_title(dataset)
        ax.set_xlabel("Balanced accuracy")
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle("LabelledData: balanced accuracy by dataset")
    fig.tight_layout()
    output = RESULTS_DIR / "labelled_algorithm_balanced_accuracy_by_dataset.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_pairwise_heatmaps(pairwise):
    outputs = []
    for dataset, group in pairwise.groupby("dataset"):
        matrix = group.pivot(
            index="method_a",
            columns="method_b",
            values="agreement_fraction",
        )
        matrix = matrix.reindex([method for method, _ in METHODS])[
            [method for method, _ in METHODS]
        ]
        fig, ax = plt.subplots(figsize=(8, 6))
        image = ax.imshow(matrix.values, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(np.arange(len(matrix.columns)))
        ax.set_xticklabels(matrix.columns, rotation=35, ha="right")
        ax.set_yticks(np.arange(len(matrix.index)))
        ax.set_yticklabels(matrix.index)
        ax.set_title(f"{dataset}: algorithm agreement")
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                value = matrix.iloc[i, j]
                if pd.notna(value):
                    ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=8)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        safe = re.sub(r"[^A-Za-z0-9]+", "_", dataset).strip("_")
        output = RESULTS_DIR / f"labelled_algorithm_pairwise_agreement_heatmap_{safe}.png"
        fig.savefig(output, dpi=220, bbox_inches="tight")
        plt.close(fig)
        outputs.append(output)
    return outputs


def plot_timeline(dataset, predictions):
    rows = [
        ("Diary reference", "reference_location"),
        ("Raw RSSI 5min", "raw_rssi_5min_prediction"),
        ("Raw RSSI 15min", "raw_rssi_15min_prediction"),
        ("Raw RSSI 30min", "raw_rssi_30min_prediction"),
        ("4b adaptive", "step_adaptive_rssi_prediction"),
        ("4c cluster", "cluster_30min_prediction"),
    ]
    values = []
    for _, column in rows:
        values.extend(predictions[column].dropna().unique())
    palette = build_palette(values)

    fig, ax = plt.subplots(figsize=(14, 5.6))
    y_positions = list(range(len(rows), 0, -1))
    for (label, column), y in zip(rows, y_positions):
        for row in predictions.itertuples(index=False):
            value = getattr(row, column)
            ax.plot(
                [row.from_date, row.to_date],
                [y, y],
                color=palette.get(value, "#b5b5b5"),
                linewidth=7,
                solid_capstyle="butt",
            )
    ax.set_yticks(y_positions)
    ax.set_yticklabels([label for label, _ in rows])
    ax.set_title(f"{dataset}: Diary reference and project algorithm estimates")
    ax.grid(axis="x", alpha=0.22)
    handles = [
        plt.Line2D([0], [0], color=palette[value], linewidth=7, label=value)
        for value in sorted(set(values))
    ]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), title="Location")
    fig.autofmt_xdate()
    fig.tight_layout()
    safe = re.sub(r"[^A-Za-z0-9]+", "_", dataset).strip("_")
    output = RESULTS_DIR / f"labelled_algorithm_timeline_{safe}.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_recall_heatmap(recall):
    recall = recall.copy()
    recall["dataset_method"] = recall["dataset"] + " | " + recall["method"]
    matrix = recall.pivot_table(
        index="dataset_method",
        columns="reference_location",
        values="recall",
        aggfunc="mean",
    )
    fig, ax = plt.subplots(figsize=(11, max(5, 0.35 * len(matrix))))
    image = ax.imshow(matrix.fillna(np.nan).values, cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    ax.set_title("Per-location recall against Diary reference")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iloc[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    output = RESULTS_DIR / "labelled_per_location_recall_heatmap.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_hybrid_metrics(core_metrics, hybrid_metrics):
    combined = pd.concat([core_metrics, hybrid_metrics], ignore_index=True)
    selected_methods = [
        "4b step-adaptive RSSI threshold10",
        "4c low-motion RSSI cluster 30min",
        "Hybrid 4b + conditional cluster",
    ]
    combined = combined.loc[combined["method"].isin(selected_methods)].copy()
    datasets = sorted(combined["dataset"].unique())
    fig, axes = plt.subplots(len(datasets), 1, figsize=(10, 3.2 * len(datasets)))
    if len(datasets) == 1:
        axes = [axes]
    for ax, dataset in zip(axes, datasets):
        subset = (
            combined.loc[combined["dataset"].eq(dataset)]
            .set_index("method")
            .reindex(selected_methods)
        )
        x = np.arange(len(selected_methods))
        width = 0.36
        ax.bar(x - width / 2, subset["accuracy"], width, label="Accuracy")
        ax.bar(x + width / 2, subset["balanced_accuracy"], width, label="Balanced accuracy")
        ax.set_xticks(x)
        ax.set_xticklabels(selected_methods, rotation=15, ha="right")
        ax.set_ylim(0, 1)
        ax.set_ylabel("Score")
        ax.set_title(dataset)
        ax.grid(axis="y", alpha=0.2)
    axes[0].legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    fig.suptitle("Hybrid check against 4b and 4c")
    fig.tight_layout()
    output = RESULTS_DIR / "labelled_hybrid_vs_4b_4c_metrics.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    manifests = []
    status_rows = []
    prediction_frames = []
    cluster_selection_frames = []
    cluster_profile_frames = []
    timeline_outputs = []

    for config in DATASETS:
        print(f"Processing {config['dataset']}...")
        predictions, manifest, selection, training, profiles, cluster_status = (
            build_reference_predictions(config)
        )
        prediction_frames.append(predictions)
        manifests.append(manifest)
        status_rows.append(cluster_status)
        if not selection.empty:
            cluster_selection_frames.append(selection)
        if not profiles.empty:
            cluster_profile_frames.append(profiles)
        timeline_outputs.append(plot_timeline(config["dataset"], predictions))

    predictions_wide = pd.concat(prediction_frames, ignore_index=True)
    predictions_long = predictions_to_long(predictions_wide)
    hybrid_long = hybrid_predictions_to_long(predictions_wide)
    metrics = metric_rows(predictions_long)
    hybrid_metrics = metric_rows(hybrid_long)
    confusion = confusion_rows(predictions_long)
    hybrid_confusion = confusion_rows(hybrid_long)
    recall = per_location_recall_rows(predictions_long)
    hybrid_recall = per_location_recall_rows(hybrid_long)
    posneg = positive_negative_agreement_rows(predictions_long)
    pairwise = pairwise_agreement_rows(predictions_long)
    hybrid_overrides = hybrid_override_summary(predictions_wide)

    manifest = pd.DataFrame(manifests)
    status = pd.DataFrame(status_rows)
    cluster_selection = (
        pd.concat(cluster_selection_frames, ignore_index=True)
        if cluster_selection_frames
        else pd.DataFrame()
    )
    cluster_profiles = (
        pd.concat(cluster_profile_frames, ignore_index=True)
        if cluster_profile_frames
        else pd.DataFrame()
    )

    manifest.to_csv(RESULTS_DIR / "labelled_dataset_manifest.csv", index=False)
    predictions_long.to_csv(
        RESULTS_DIR / "labelled_algorithm_predictions_long.csv",
        index=False,
    )
    predictions_wide.to_csv(
        RESULTS_DIR / "labelled_algorithm_predictions_wide.csv",
        index=False,
    )
    metrics.to_csv(RESULTS_DIR / "labelled_algorithm_reference_metrics.csv", index=False)
    hybrid_long.to_csv(
        RESULTS_DIR / "labelled_hybrid_predictions_long.csv",
        index=False,
    )
    hybrid_metrics.to_csv(
        RESULTS_DIR / "labelled_hybrid_reference_metrics.csv",
        index=False,
    )
    confusion.to_csv(
        RESULTS_DIR / "labelled_algorithm_confusion_matrix.csv",
        index=False,
    )
    hybrid_confusion.to_csv(
        RESULTS_DIR / "labelled_hybrid_confusion_matrix.csv",
        index=False,
    )
    recall.to_csv(
        RESULTS_DIR / "labelled_algorithm_per_location_recall.csv",
        index=False,
    )
    hybrid_recall.to_csv(
        RESULTS_DIR / "labelled_hybrid_per_location_recall.csv",
        index=False,
    )
    posneg.to_csv(
        RESULTS_DIR / "labelled_algorithm_positive_negative_agreement.csv",
        index=False,
    )
    pairwise.to_csv(
        RESULTS_DIR / "labelled_algorithm_pairwise_agreement.csv",
        index=False,
    )
    cluster_selection.to_csv(
        RESULTS_DIR / "labelled_cluster_model_selection.csv",
        index=False,
    )
    cluster_profiles.to_csv(
        RESULTS_DIR / "labelled_cluster_profiles.csv",
        index=False,
    )
    status.to_csv(RESULTS_DIR / "labelled_algorithm_status.csv", index=False)
    hybrid_overrides.to_csv(
        RESULTS_DIR / "labelled_hybrid_override_summary.csv",
        index=False,
    )

    figures = [
        plot_metrics_summary(metrics),
        plot_balanced_accuracy_by_dataset(metrics),
        plot_recall_heatmap(recall),
        plot_hybrid_metrics(metrics, hybrid_metrics),
    ]
    figures.extend(plot_pairwise_heatmaps(pairwise))
    figures.extend(timeline_outputs)

    print("\nMetrics:")
    print(metrics.sort_values(["dataset", "method"]).to_string(index=False))
    print("\nCluster status:")
    print(status.to_string(index=False))
    print("\nHybrid metrics:")
    print(hybrid_metrics.sort_values(["dataset", "method"]).to_string(index=False))
    print("\nHybrid override summary:")
    print(hybrid_overrides.to_string(index=False))
    print("\nSaved outputs:")
    for path in [
        RESULTS_DIR / "labelled_dataset_manifest.csv",
        RESULTS_DIR / "labelled_algorithm_predictions_long.csv",
        RESULTS_DIR / "labelled_algorithm_reference_metrics.csv",
        RESULTS_DIR / "labelled_hybrid_predictions_long.csv",
        RESULTS_DIR / "labelled_hybrid_reference_metrics.csv",
        RESULTS_DIR / "labelled_algorithm_confusion_matrix.csv",
        RESULTS_DIR / "labelled_hybrid_confusion_matrix.csv",
        RESULTS_DIR / "labelled_algorithm_per_location_recall.csv",
        RESULTS_DIR / "labelled_hybrid_per_location_recall.csv",
        RESULTS_DIR / "labelled_algorithm_positive_negative_agreement.csv",
        RESULTS_DIR / "labelled_algorithm_pairwise_agreement.csv",
        RESULTS_DIR / "labelled_cluster_model_selection.csv",
        RESULTS_DIR / "labelled_cluster_profiles.csv",
        RESULTS_DIR / "labelled_algorithm_status.csv",
        RESULTS_DIR / "labelled_hybrid_override_summary.csv",
        *figures,
    ]:
        print(path)


if __name__ == "__main__":
    main()
