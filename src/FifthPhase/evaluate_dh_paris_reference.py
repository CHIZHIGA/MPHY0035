import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "labelledData"
RAW_DIR = DATA_DIR / "Paris NY2024" / "DH"
ANALYSIS_PATH = DATA_DIR / "Analysis" / "Analysis DH Paris.xlsx"
BEACON_PATH = DATA_DIR / "Paris NY2024" / "beacons Paris NY 2024.xlsx"
RESULTS_DIR = ROOT / "Results" / "FifthPhase"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

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
        sheet_path = sheet_paths[sheet_name]
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
        if "from_date" in lowered and "diary" in lowered:
            header_index = index
            break
    if header_index is None:
        raise ValueError("Could not find a header row containing from_date and Diary")

    header = [str(value).strip() or f"unnamed_{i}" for i, value in enumerate(rows[header_index])]
    body = rows[header_index + 1 :]
    width = len(header)
    normalised = [row[:width] + [""] * max(0, width - len(row)) for row in body]
    frame = pd.DataFrame(normalised, columns=header)
    frame = frame.loc[frame["from_date"].astype(str).str.strip().ne("")].copy()
    return frame


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


def load_reference():
    rows = read_xlsx_rows(ANALYSIS_PATH)
    frame = rows_to_frame(rows)
    frame = frame.rename(
        columns={
            "Diary": "reference_location",
            "location1": "analysis_location1",
            "location2": "analysis_location2",
        }
    )
    frame["from_date"] = pd.to_datetime(frame["from_date"], utc=True)
    frame["to_date"] = pd.to_datetime(frame["to_date"], utc=True)
    frame["window_start"] = frame["from_date"].dt.floor("15min")
    for column in ["reference_location", "analysis_location1", "analysis_location2"]:
        frame[column] = frame[column].map(normalise_location)
    frame["steps_analysis"] = pd.to_numeric(frame.get("Steps"), errors="coerce")
    frame = frame.loc[frame["reference_location"].ne("Unknown")].copy()
    return frame[
        [
            "window_start",
            "from_date",
            "to_date",
            "reference_location",
            "analysis_location1",
            "analysis_location2",
            "steps_analysis",
        ]
    ]


def load_beacon_mapping():
    rows = read_xlsx_rows(BEACON_PATH, "Sheet1")
    mapping = {}
    for row in rows:
        if len(row) < 2:
            continue
        room_text = str(row[0]).strip()
        beacon = str(row[1]).strip().upper()
        if not re.fullmatch(r"[0-9A-F]{4}", beacon):
            continue
        mapping[beacon] = normalise_location(room_text)
    return mapping


def load_raw_tags():
    path = RAW_DIR / "SAMPLES_tags.csv"
    tags = pd.read_csv(
        path,
        usecols=["time", "rssi", "uuid"],
        low_memory=False,
    )
    tags["time_ms"] = pd.to_numeric(tags["time"], errors="coerce")
    tags["rssi"] = pd.to_numeric(tags["rssi"], errors="coerce")
    tags["beacon"] = tags["uuid"].astype(str).str.slice(0, 4).str.upper()
    tags = tags.dropna(subset=["time_ms", "rssi"])
    tags = tags.loc[tags["beacon"].str.fullmatch(r"[0-9A-F]{4}", na=False)].copy()
    tags["time"] = pd.to_datetime(tags["time_ms"], unit="ms", utc=True)
    return tags[["time", "beacon", "rssi"]]


def load_step_count():
    path = RAW_DIR / "SAMPLES_Step_count.csv"
    steps = pd.read_csv(path, header=None, names=["time_ms", "time_text", "step_count"])
    steps["time_ms"] = pd.to_numeric(steps["time_ms"], errors="coerce")
    steps["step_count"] = pd.to_numeric(steps["step_count"], errors="coerce")
    steps = steps.dropna(subset=["time_ms", "step_count"]).copy()
    steps["time"] = pd.to_datetime(steps["time_ms"], unit="ms", utc=True)
    steps = steps.sort_values("time")
    steps["step_increment"] = steps["step_count"].diff()
    steps.loc[steps["step_increment"].lt(0), "step_increment"] = np.nan
    steps["step_increment"] = steps["step_increment"].fillna(0)
    return steps[["time", "step_count", "step_increment"]]


def strongest_second_gap(values):
    clean = values.dropna().sort_values(ascending=False)
    if clean.empty:
        return np.nan
    if len(clean) == 1:
        return np.nan
    return clean.iloc[0] - clean.iloc[1]


def build_rssi_windows(tags, beacon_mapping, window="15min"):
    mapped = tags.loc[tags["beacon"].isin(beacon_mapping)].copy()
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

    row_winners = mapped.loc[mapped.groupby(["window_start"])["rssi"].idxmax()]
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

    windows = pd.DataFrame(
        {
            "window_start": mean_rssi.index,
            "raw_rssi_strongest_beacon": strongest_beacon.values,
            "raw_rssi_prediction": [
                beacon_mapping.get(beacon, "Unmapped")
                for beacon in strongest_beacon.values
            ],
            "raw_rssi_strongest_rssi": strongest_rssi.values,
            "raw_rssi_second_gap": gap.values,
            "raw_rssi_strongest_prop": strongest_prop,
        }
    )
    windows = windows.merge(counts.reset_index(), on="window_start", how="left")
    return windows


def build_step_windows(steps, window="15min"):
    frame = steps.copy()
    frame["window_start"] = frame["time"].dt.floor(window)
    return (
        frame.groupby("window_start")["step_increment"]
        .sum()
        .rename("step_increment")
        .reset_index()
    )


def prefixed_windows(windows, prefix):
    renamed = windows.rename(
        columns={
            "raw_rssi_strongest_beacon": f"{prefix}_strongest_beacon",
            "raw_rssi_prediction": f"{prefix}_prediction",
            "raw_rssi_strongest_rssi": f"{prefix}_strongest_rssi",
            "raw_rssi_second_gap": f"{prefix}_second_gap",
            "raw_rssi_strongest_prop": f"{prefix}_strongest_prop",
            "rssi_sample_count": f"{prefix}_sample_count",
        }
    )
    return renamed


def prefixed_steps(windows, prefix):
    return windows.rename(columns={"step_increment": f"{prefix}_step_increment"})


def attach_predictions(reference, rssi_by_window, step_by_window):
    predictions = reference.copy()
    for window, rssi_windows in rssi_by_window.items():
        prefix = f"raw_rssi_{window}"
        helper = prefixed_windows(rssi_windows, prefix).copy()
        helper[f"{prefix}_join_time"] = helper["window_start"]
        predictions[f"{prefix}_join_time"] = predictions["window_start"].dt.floor(window)
        predictions = predictions.merge(
            helper.drop(columns=["window_start"]),
            on=f"{prefix}_join_time",
            how="left",
        )
        predictions[f"{prefix}_prediction"] = predictions[
            f"{prefix}_prediction"
        ].fillna("Out")
        predictions[f"{prefix}_sample_count"] = (
            predictions[f"{prefix}_sample_count"].fillna(0).astype(int)
        )

    for window, step_windows in step_by_window.items():
        prefix = f"{window}"
        helper = prefixed_steps(step_windows, prefix).copy()
        helper[f"{prefix}_step_join_time"] = helper["window_start"]
        predictions[f"{prefix}_step_join_time"] = predictions["window_start"].dt.floor(
            window
        )
        predictions = predictions.merge(
            helper.drop(columns=["window_start"]),
            on=f"{prefix}_step_join_time",
            how="left",
        )
        predictions[f"{prefix}_step_increment"] = predictions[
            f"{prefix}_step_increment"
        ].fillna(0)

    adaptive_rows = []
    for _, row in predictions.iterrows():
        selected = "5min"
        reason = "default_short_window"
        if row["30min_step_increment"] <= 10:
            selected = "30min"
            reason = "30min_low_step"
        elif row["15min_step_increment"] <= 10:
            selected = "15min"
            reason = "15min_low_step"

        prediction = row[f"raw_rssi_{selected}_prediction"]
        sample_count = row[f"raw_rssi_{selected}_sample_count"]
        if sample_count <= 0:
            prediction = "Out"
            reason = f"{reason}_no_rssi"

        adaptive_rows.append(
            {
                "step_adaptive_rssi_prediction": prediction,
                "step_adaptive_selected_window": selected,
                "step_adaptive_reason": reason,
                "step_adaptive_selected_sample_count": sample_count,
            }
        )

    predictions = pd.concat(
        [predictions.reset_index(drop=True), pd.DataFrame(adaptive_rows)],
        axis=1,
    )

    predictions["raw_rssi_prediction"] = predictions["raw_rssi_15min_prediction"]
    predictions["raw_rssi_strongest_beacon"] = predictions[
        "raw_rssi_15min_strongest_beacon"
    ]
    predictions["raw_rssi_second_gap"] = predictions["raw_rssi_15min_second_gap"]
    predictions["raw_rssi_strongest_prop"] = predictions["raw_rssi_15min_strongest_prop"]
    predictions["rssi_sample_count"] = predictions["raw_rssi_15min_sample_count"]
    predictions["raw_step_increment_15min"] = predictions["15min_step_increment"]
    return predictions


def confusion_rows(y_true, y_pred, method):
    labels = sorted(set(y_true) | set(y_pred))
    rows = []
    for actual in labels:
        actual_mask = y_true.eq(actual)
        for predicted in labels:
            rows.append(
                {
                    "method": method,
                    "actual": actual,
                    "predicted": predicted,
                    "count": int((actual_mask & y_pred.eq(predicted)).sum()),
                }
            )
    return rows


def metric_row(predictions, method, prediction_column):
    valid = predictions.loc[
        predictions["reference_location"].notna()
        & predictions[prediction_column].notna()
    ].copy()
    correct = valid["reference_location"].eq(valid[prediction_column])
    labels = sorted(valid["reference_location"].dropna().unique())
    recalls = []
    for label in labels:
        subset = valid.loc[valid["reference_location"].eq(label)]
        if len(subset):
            recalls.append(subset[prediction_column].eq(label).mean())
    return {
        "method": method,
        "prediction_column": prediction_column,
        "n_windows": len(valid),
        "accuracy": correct.mean() if len(valid) else np.nan,
        "balanced_accuracy": float(np.mean(recalls)) if recalls else np.nan,
        "reference_labels": ", ".join(labels),
    }


def per_location_recall(predictions, method, prediction_column):
    rows = []
    for label, group in predictions.groupby("reference_location"):
        if not len(group):
            continue
        rows.append(
            {
                "method": method,
                "reference_location": label,
                "n_windows": len(group),
                "recall": group[prediction_column].eq(label).mean(),
                "most_common_prediction": group[prediction_column].mode().iat[0]
                if not group[prediction_column].mode().empty
                else "",
            }
        )
    return rows


def evaluate(predictions):
    methods = [
        ("Analysis location1", "analysis_location1"),
        ("Analysis location2", "analysis_location2"),
        ("Raw RSSI 5min strongest", "raw_rssi_5min_prediction"),
        ("Raw RSSI 15min strongest", "raw_rssi_prediction"),
        ("Raw RSSI 30min strongest", "raw_rssi_30min_prediction"),
        ("Step-adaptive RSSI threshold10", "step_adaptive_rssi_prediction"),
    ]
    metrics = []
    confusion = []
    recall = []
    for method, column in methods:
        metrics.append(metric_row(predictions, method, column))
        confusion.extend(
            confusion_rows(
                predictions["reference_location"],
                predictions[column],
                method,
            )
        )
        recall.extend(per_location_recall(predictions, method, column))
    return pd.DataFrame(metrics), pd.DataFrame(confusion), pd.DataFrame(recall)


def plot_metrics(metrics):
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(metrics))
    width = 0.36
    ax.bar(x - width / 2, metrics["accuracy"], width, label="Accuracy")
    ax.bar(x + width / 2, metrics["balanced_accuracy"], width, label="Balanced accuracy")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics["method"], rotation=18, ha="right")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score against Diary reference")
    ax.set_title("DH Paris: first reference-based location comparison")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    output = RESULTS_DIR / "DH_Paris_reference_accuracy_comparison.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_confusion(confusion, method="Raw RSSI 15min strongest"):
    matrix = confusion.loc[confusion["method"].eq(method)].pivot(
        index="actual",
        columns="predicted",
        values="count",
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    image = ax.imshow(matrix.values, cmap="Blues")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xlabel("Predicted location")
    ax.set_ylabel("Diary reference")
    ax.set_title("DH Paris: Raw RSSI 15min strongest confusion matrix")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix.iloc[i, j])
            if value:
                ax.text(j, i, str(value), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    output = RESULTS_DIR / "DH_Paris_raw_rssi_confusion_matrix.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_timeline(predictions):
    plot_data = predictions.copy()
    location_values = sorted(
        set(plot_data["reference_location"])
        | set(plot_data["raw_rssi_prediction"])
        | set(plot_data["step_adaptive_rssi_prediction"])
        | set(plot_data["analysis_location1"])
    )
    palette = dict(ROOM_COLORS)
    cmap = plt.get_cmap("tab20")
    for value in location_values:
        if value not in palette:
            palette[value] = cmap(len(palette) % 20)
    codes = {value: index for index, value in enumerate(location_values)}

    fig, ax = plt.subplots(figsize=(14, 5.4))
    rows = [
        ("Diary reference", "reference_location", 2),
        ("Raw RSSI 15min strongest", "raw_rssi_prediction", 1),
        ("Step-adaptive RSSI", "step_adaptive_rssi_prediction", 0),
        ("Analysis location1", "analysis_location1", -1),
    ]
    for _, column, y in rows:
        for row in plot_data.itertuples(index=False):
            start = row.from_date
            end = row.to_date
            value = getattr(row, column)
            ax.plot(
                [start, end],
                [y, y],
                color=palette.get(value, "#b5b5b5"),
                linewidth=8,
                solid_capstyle="butt",
            )
    ax.set_yticks([2, 1, 0, -1])
    ax.set_yticklabels([row[0] for row in rows])
    ax.set_title("DH Paris: Diary reference and first location estimates")
    ax.grid(axis="x", alpha=0.22)
    handles = [
        plt.Line2D([0], [0], color=palette[value], linewidth=7, label=value)
        for value in location_values
    ]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title="Location",
    )
    fig.autofmt_xdate()
    fig.tight_layout()
    output = RESULTS_DIR / "DH_Paris_reference_timeline.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    reference = load_reference()
    beacon_mapping = load_beacon_mapping()
    tags = load_raw_tags()
    steps = load_step_count()

    rssi_by_window = {
        window: build_rssi_windows(tags, beacon_mapping, window)
        for window in ["5min", "15min", "30min"]
    }
    step_by_window = {
        window: build_step_windows(steps, window)
        for window in ["5min", "15min", "30min"]
    }
    predictions = attach_predictions(reference, rssi_by_window, step_by_window)
    metrics, confusion, recall = evaluate(predictions)

    predictions.to_csv(RESULTS_DIR / "DH_Paris_reference_predictions.csv", index=False)
    metrics.to_csv(RESULTS_DIR / "DH_Paris_reference_metrics.csv", index=False)
    confusion.to_csv(RESULTS_DIR / "DH_Paris_reference_confusion_matrix.csv", index=False)
    recall.to_csv(RESULTS_DIR / "DH_Paris_reference_per_location_recall.csv", index=False)

    metric_plot = plot_metrics(metrics)
    confusion_plot = plot_confusion(confusion)
    timeline_plot = plot_timeline(predictions)

    print("Reference rows:", len(reference))
    print("Raw RSSI rows:", len(tags))
    print("Beacon mapping:", beacon_mapping)
    print(metrics.to_string(index=False))
    print("Saved:")
    for path in [
        RESULTS_DIR / "DH_Paris_reference_predictions.csv",
        RESULTS_DIR / "DH_Paris_reference_metrics.csv",
        RESULTS_DIR / "DH_Paris_reference_confusion_matrix.csv",
        RESULTS_DIR / "DH_Paris_reference_per_location_recall.csv",
        metric_plot,
        confusion_plot,
        timeline_plot,
    ]:
        print(path)


if __name__ == "__main__":
    main()
