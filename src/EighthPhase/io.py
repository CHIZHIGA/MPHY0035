"""Input adapters for heterogeneous PDH exports."""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from .core import normalise_location


ROOT = Path(__file__).resolve().parents[2]
STEP_PLATEAU_MAX_GAP = pd.Timedelta(minutes=35)


def epoch_ms(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    # Some combined exports call the millisecond column `time`, while older
    # records occasionally contain seconds. Normalise both without using text time.
    milliseconds = numeric.where(numeric.ge(1e11), numeric * 1000)
    return pd.to_datetime(milliseconds, unit="ms", utc=True, errors="coerce")


def load_manifest(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def _metadata_mapping(path: Path) -> tuple[dict[str, str], str | None]:
    with path.open() as handle:
        data = json.load(handle)
    mapping = {}
    for item in data.get("beacons", []):
        beacon = str(item.get("beacon_id", "")).upper()
        location = normalise_location(item.get("location"))
        if beacon and location != "Unknown":
            mapping[beacon] = location
    return mapping, data.get("timezone")


def _config_mapping(path: Path) -> tuple[dict[str, str], str | None]:
    with path.open() as handle:
        data = json.load(handle)
    whitelist = {str(item).upper() for item in data.get("tagsWhitelist", [])}
    use_whitelist = bool(data.get("isWhitelistEnabled", False))
    mapping = {}
    for beacon, location in data.get("tagsLocation", {}).items():
        beacon = str(beacon).upper()
        if use_whitelist and beacon not in whitelist:
            continue
        room = normalise_location(location)
        if room != "Unknown":
            mapping[beacon] = room
    return mapping, data.get("subjectTimezone")


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _xlsx_column_index(reference: str) -> int:
    letters = re.match(r"([A-Z]+)", str(reference)).group(1)
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def _xlsx_rows(path: Path, sheet_name: str | None = None) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {item.attrib["Id"]: item.attrib["Target"] for item in rels.findall("rel:Relationship", REL_NS)}
        sheets = {}
        for sheet in workbook.findall(".//a:sheet", NS):
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = relmap[rel_id]
            sheets[sheet.attrib["name"]] = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
        selected = sheet_name or next(iter(sheets))
        xml = ET.fromstring(archive.read(sheets[selected]))
        rows = []
        for row in xml.findall(".//a:sheetData/a:row", NS):
            values = []
            for cell in row.findall("a:c", NS):
                position = _xlsx_column_index(cell.attrib.get("r", "A1"))
                while len(values) <= position:
                    values.append("")
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//a:t", NS))
                else:
                    node = cell.find("a:v", NS)
                    value = node.text if node is not None else ""
                    if cell_type == "s" and value:
                        value = shared[int(value)]
                values[position] = value
            rows.append(values)
        return rows


def _workbook_mapping(path: Path) -> tuple[dict[str, str], None]:
    mapping = {}
    for row in _xlsx_rows(path):
        if len(row) < 2:
            continue
        beacon = str(row[1]).strip().upper()
        if re.fullmatch(r"[0-9A-F]{4}", beacon):
            room = normalise_location(row[0])
            if room != "Unknown":
                mapping[beacon] = room
    return mapping, None


def load_beacon_mapping(session: dict) -> dict[str, str]:
    mapping_spec = session.get("mapping", {})
    mapping_type = mapping_spec.get("type", "none")
    path = ROOT / mapping_spec["path"] if mapping_spec.get("path") else None
    if mapping_type == "metadata_subject":
        mapping, _ = _metadata_mapping(path)
    elif mapping_type == "config_annotator":
        mapping, _ = _config_mapping(path)
    elif mapping_type == "workbook":
        mapping, _ = _workbook_mapping(path)
    else:
        mapping = {}
    mapping.update({str(key).upper(): normalise_location(value) for key, value in session.get("mapping_override", {}).items()})
    return mapping


def _combine_grouped(parts: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    if not parts:
        return pd.DataFrame(columns=columns)
    return pd.concat(parts).groupby(level=list(range(pd.concat(parts).index.nlevels)))[columns].sum().sort_index()


def _quality_filter(mean: pd.DataFrame, count: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    expected = count.replace(0, np.nan).median(axis=0).clip(lower=1)
    minimum = np.ceil(expected * 0.20).clip(lower=1)
    valid = count.ge(minimum, axis=1)
    filtered = mean.where(valid)
    total_expected = float(expected.sum())
    coverage = count.sum(axis=1) / total_expected if total_expected else pd.Series(0.0, index=count.index)
    return filtered, count, coverage.clip(upper=1)


def load_combined_tags(path: Path, allowed: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.DataFrame]:
    header = path.open(errors="ignore").readline().strip().split(",")
    time_column = "timestamp" if "timestamp" in header else "time"
    pressure_column = "pressure_hpa" if "pressure_hpa" in header else ("pressure" if "pressure" in header else None)
    usecols = [time_column, "uuid", "rssi"] + ([pressure_column] if pressure_column else [])
    rssi_parts, pressure_parts = [], []
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=250_000, low_memory=False, on_bad_lines="skip"):
        chunk["time"] = epoch_ms(chunk[time_column])
        chunk["beacon"] = chunk["uuid"].astype(str).str.slice(0, 4).str.upper()
        chunk["rssi"] = pd.to_numeric(chunk["rssi"], errors="coerce")
        chunk = chunk.dropna(subset=["time", "rssi"])
        chunk = chunk.loc[chunk["beacon"].str.fullmatch(r"[0-9A-F]{4}", na=False)]
        if allowed:
            chunk = chunk.loc[chunk["beacon"].isin(allowed)]
        chunk["window"] = chunk["time"].dt.floor("5min")
        grouped = chunk.groupby(["window", "beacon"])["rssi"].agg(["sum", "count"])
        rssi_parts.append(grouped)
        if pressure_column:
            chunk["pressure_value"] = pd.to_numeric(chunk[pressure_column], errors="coerce")
            pressure_parts.append(chunk.dropna(subset=["pressure_value"]).groupby(["window", "beacon"])["pressure_value"].agg(["sum", "count"]))
    grouped = _combine_grouped(rssi_parts, ["sum", "count"])
    mean = (grouped["sum"] / grouped["count"]).unstack("beacon")
    count = grouped["count"].unstack("beacon").fillna(0)
    mean, count, coverage = _quality_filter(mean, count)
    pressure = pd.DataFrame(index=mean.index)
    if pressure_parts:
        pgroup = _combine_grouped(pressure_parts, ["sum", "count"])
        pressure = (pgroup["sum"] / pgroup["count"]).unstack("beacon")
    return mean, count, coverage, pressure


def load_separate_rssi(directory: Path, allowed: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    means, counts = {}, {}
    for path in sorted(directory.glob("SAMPLES_TAGS_RSSI_*.csv")):
        beacon = path.stem.rsplit("_", 1)[-1].upper()
        if allowed and beacon not in allowed:
            continue
        parts = []
        for chunk in pd.read_csv(path, header=None, names=["timestamp", "text", "rssi"], chunksize=250_000):
            chunk["time"] = epoch_ms(chunk["timestamp"])
            chunk["rssi"] = pd.to_numeric(chunk["rssi"], errors="coerce")
            chunk = chunk.dropna(subset=["time", "rssi"])
            chunk["window"] = chunk["time"].dt.floor("5min")
            parts.append(chunk.groupby("window")["rssi"].agg(["sum", "count"]))
        if not parts:
            continue
        grouped = pd.concat(parts).groupby(level=0)[["sum", "count"]].sum()
        means[beacon] = grouped["sum"] / grouped["count"]
        counts[beacon] = grouped["count"]
    mean = pd.DataFrame(means).sort_index()
    count = pd.DataFrame(counts).reindex(mean.index).fillna(0)
    return _quality_filter(mean, count)


def load_matrix(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    frame = pd.read_csv(path)
    timestamp_column = frame.columns[0]
    frame["time"] = epoch_ms(frame[timestamp_column])
    frame = frame.dropna(subset=["time"]).drop(columns=[timestamp_column]).set_index("time")
    values = frame.apply(pd.to_numeric, errors="coerce")
    values.columns = [str(column).upper() for column in values.columns]
    values = values.groupby(values.index.floor("5min")).mean()
    count = values.notna().astype(int)
    coverage = count.mean(axis=1)
    return values, count, coverage


def load_rssi(session: dict, mapping: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.DataFrame]:
    spec = session["rssi"]
    allowed = set(mapping) if mapping and spec.get("restrict_to_mapping", True) else None
    if spec["type"] == "combined_tags":
        return load_combined_tags(ROOT / spec["path"], allowed)
    if spec["type"] == "separate":
        mean, count, coverage = load_separate_rssi(ROOT / spec["path"], allowed)
        return mean, count, coverage, pd.DataFrame(index=mean.index)
    mean, count, coverage = load_matrix(ROOT / spec["path"])
    pressure_path = spec.get("environmental_pressure_path")
    pressure = load_matrix(ROOT / pressure_path)[0] if pressure_path else pd.DataFrame(index=mean.index)
    return mean, count, coverage, pressure


def load_acc(path: Path) -> tuple[pd.Series, pd.Series]:
    first = path.open(errors="ignore").readline().strip().split(",")
    has_header = first[0].strip().lower() == "timestamp"
    parts, magnitude_medians = [], []
    reader = pd.read_csv(path, chunksize=500_000) if has_header else pd.read_csv(path, header=None, names=["timestamp", "text", "x", "y", "z"], chunksize=500_000)
    for chunk in reader:
        time_col = "timestamp" if "timestamp" in chunk else chunk.columns[0]
        chunk["time"] = epoch_ms(chunk[time_col])
        if "MAGNITUDE" in chunk:
            magnitude = pd.to_numeric(chunk["MAGNITUDE"], errors="coerce")
        else:
            xyz_names = [name for name in ("HE_ACC_x", "HE_ACC_y", "HE_ACC_z", "x", "y", "z") if name in chunk]
            if len(xyz_names) >= 3:
                numeric = chunk[xyz_names[-3:]].apply(pd.to_numeric, errors="coerce")
                magnitude = np.sqrt((numeric ** 2).sum(axis=1))
            else:
                continue
        valid = pd.DataFrame({"time": chunk["time"], "magnitude": magnitude}).dropna()
        if valid.empty:
            continue
        magnitude_medians.append(float(valid["magnitude"].median()))
        valid["window"] = valid["time"].dt.floor("5min")
        valid["square"] = valid["magnitude"] ** 2
        parts.append(valid.groupby("window").agg(total=("magnitude", "sum"), square=("square", "sum"), count=("magnitude", "count")))
    if not parts:
        return pd.Series(dtype=float), pd.Series(dtype=bool)
    grouped = pd.concat(parts).groupby(level=0)[["total", "square", "count"]].sum().sort_index()
    variance = (grouped["square"] - grouped["total"] ** 2 / grouped["count"]) / (grouped["count"] - 1).clip(lower=1)
    scale = float(np.median(magnitude_medians)) if magnitude_medians else 1.0
    scale = scale if np.isfinite(scale) and scale > 0 else 1.0
    feature = np.sqrt(variance.clip(lower=0)) / scale
    feature = feature.where(grouped["count"].ge(10))
    return feature.rename("acc_magnitude_std"), grouped["count"].gt(0).rename("acc_online")


def load_steps(path: Path) -> tuple[pd.Series, pd.Series]:
    """Load a cumulative step counter and reconstruct bounded zero-step plateaus.

    The exports record the unchanged counter roughly every 30 minutes during
    inactivity.  Treating only the arrival window as observed fragments a real
    zero-step plateau into missing five-minute windows.  Intervening windows are
    therefore set to zero only when consecutive counter values are identical
    and no more than 35 minutes apart.  Increasing or longer gaps remain
    interval-censored and are not filled.
    """
    parts = []
    plateau_windows: list[pd.Timestamp] = []
    previous_count = None
    previous_time = None
    for chunk in pd.read_csv(path, header=None, names=["timestamp", "text", "count"], chunksize=250_000):
        chunk["time"] = epoch_ms(chunk["timestamp"])
        chunk["count"] = pd.to_numeric(chunk["count"], errors="coerce")
        chunk = chunk.dropna(subset=["time", "count"]).sort_values("time")
        if chunk.empty:
            continue
        prior_count = chunk["count"].shift()
        prior_time = chunk["time"].shift()
        if previous_count is not None and previous_time is not None:
            prior_count.iloc[0] = previous_count
            prior_time.iloc[0] = previous_time
        gaps = chunk["time"] - prior_time
        bounded_plateau = chunk["count"].eq(prior_count) & gaps.gt(pd.Timedelta(0)) & gaps.le(STEP_PLATEAU_MAX_GAP)
        for start, end in zip(prior_time.loc[bounded_plateau], chunk.loc[bounded_plateau, "time"]):
            first_window = start.floor("5min") + pd.Timedelta(minutes=5)
            last_window = end.floor("5min")
            if first_window <= last_window:
                plateau_windows.extend(pd.date_range(first_window, last_window, freq="5min"))
        values = chunk["count"]
        diff = values.diff()
        if previous_count is not None:
            diff.iloc[0] = values.iloc[0] - previous_count
        previous_count = values.iloc[-1]
        previous_time = chunk["time"].iloc[-1]
        chunk["increment"] = diff.where(diff.ge(0), 0).fillna(0)
        chunk["window"] = chunk["time"].dt.floor("5min")
        parts.append(chunk.groupby("window").agg(increment=("increment", "sum"), samples=("count", "count")))
    if not parts:
        return pd.Series(dtype=float), pd.Series(dtype=bool)
    grouped = pd.concat(parts).groupby(level=0)[["increment", "samples"]].sum().sort_index()
    feature = grouped["increment"].rename("step_increment")
    online = grouped["samples"].gt(0).rename("step_online")
    if plateau_windows:
        plateau_index = pd.DatetimeIndex(plateau_windows).unique().sort_values()
        combined_index = feature.index.union(plateau_index).sort_values()
        feature = feature.reindex(combined_index)
        online = online.reindex(combined_index, fill_value=False)
        inferred = plateau_index.difference(grouped.index)
        feature.loc[inferred] = 0.0
        online.loc[inferred] = True
        feature.attrs["reconstructed_zero_windows"] = len(inferred)
    else:
        feature.attrs["reconstructed_zero_windows"] = 0
    return feature, online


def load_wearable_pressure(path: Path) -> tuple[pd.Series, pd.Series]:
    first = path.open(errors="ignore").readline().strip().split(",")
    has_header = first[0].strip().lower() == "timestamp"
    parts = []
    reader = pd.read_csv(path, chunksize=500_000) if has_header else pd.read_csv(path, header=None, names=["timestamp", "text", "pressure"], chunksize=500_000)
    for chunk in reader:
        time_col = "timestamp" if "timestamp" in chunk else chunk.columns[0]
        value_col = "PRESSURE" if "PRESSURE" in chunk else ("pressure" if "pressure" in chunk else chunk.columns[-1])
        chunk["time"] = epoch_ms(chunk[time_col])
        chunk["value"] = pd.to_numeric(chunk[value_col], errors="coerce")
        chunk = chunk.dropna(subset=["time", "value"])
        chunk["window"] = chunk["time"].dt.floor("5min")
        parts.append(chunk.groupby("window")["value"].agg(["sum", "count"]))
    if not parts:
        return pd.Series(dtype=float), pd.Series(dtype=bool)
    grouped = pd.concat(parts).groupby(level=0)[["sum", "count"]].sum().sort_index()
    return (grouped["sum"] / grouped["count"]).rename("wearable_pressure"), grouped["count"].gt(0).rename("pressure_online")


def load_session_inputs(session: dict) -> dict[str, object]:
    mapping = load_beacon_mapping(session)
    rssi_mean, rssi_count, coverage, environmental_pressure = load_rssi(session, mapping)
    # Unmapped collections still retain beacon identity and can infer Bedroom.
    for beacon in rssi_mean.columns:
        mapping.setdefault(str(beacon), f"Beacon {beacon}")
    acc = acc_online = pd.Series(dtype=float)
    if session.get("acc_path") and (ROOT / session["acc_path"]).exists() and (ROOT / session["acc_path"]).stat().st_size:
        acc, acc_online = load_acc(ROOT / session["acc_path"])
    steps = step_online = pd.Series(dtype=float)
    step_reconstructed_zero_windows = 0
    if session.get("step_path") and (ROOT / session["step_path"]).exists() and (ROOT / session["step_path"]).stat().st_size:
        steps, step_online = load_steps(ROOT / session["step_path"])
        step_reconstructed_zero_windows = int(steps.attrs.get("reconstructed_zero_windows", 0))
    pressure = pressure_online = pd.Series(dtype=float)
    if session.get("wearable_pressure_path") and (ROOT / session["wearable_pressure_path"]).exists() and (ROOT / session["wearable_pressure_path"]).stat().st_size:
        pressure, pressure_online = load_wearable_pressure(ROOT / session["wearable_pressure_path"])

    indices = [item.index for item in (rssi_mean, acc, steps, pressure) if len(item)]
    start = min(index.min() for index in indices).floor("5min")
    end = max(index.max() for index in indices).ceil("5min")
    grid = pd.date_range(start, end, freq="5min", tz="UTC")
    rssi_mean = rssi_mean.reindex(grid)
    rssi_count = rssi_count.reindex(grid).fillna(0)
    coverage = coverage.reindex(grid).fillna(0)
    online = pd.concat(
        [series.reindex(grid, fill_value=False).astype(bool) for series in (acc_online, step_online, pressure_online) if len(series)],
        axis=1,
    ).any(axis=1) if any(len(series) for series in (acc_online, step_online, pressure_online)) else pd.Series(False, index=grid)
    movement = acc.reindex(grid) if acc.notna().sum() else steps.reindex(grid)
    movement_source = "acc" if acc.notna().sum() else ("step" if steps.notna().sum() else None)
    return {
        "rssi_mean": rssi_mean,
        "rssi_count": rssi_count,
        "rssi_coverage": coverage,
        "environmental_pressure": environmental_pressure.reindex(grid),
        "wearable_pressure": pressure.reindex(grid),
        "movement": movement,
        "movement_source": movement_source,
        "step_reconstructed_zero_windows": step_reconstructed_zero_windows,
        "wearable_online": online,
        "beacon_to_room": mapping,
        "grid": grid,
    }
