"""Post-hoc reference agreement and two-person co-presence analyses."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

from .core import normalise_location
from .io import ROOT, _xlsx_rows


def _parse_excel_datetime(value: object) -> pd.Timestamp:
    text = str(value).strip()
    if not text:
        return pd.NaT
    if re.fullmatch(r"\d+(\.\d+)?", text):
        number = float(text)
        if number > 20000:
            return pd.Timestamp("1899-12-30", tz="UTC") + pd.to_timedelta(number, unit="D")
    return pd.to_datetime(text, utc=True, errors="coerce")


def load_reference(spec: dict) -> pd.DataFrame:
    rows = _xlsx_rows(ROOT / spec["path"], spec.get("sheet"))
    header_index = None
    for index, row in enumerate(rows):
        lowered = [str(value).strip().lower() for value in row]
        if "from_date" in lowered and "to_date" in lowered and "diary" in lowered:
            header_index = index
            break
    if header_index is None:
        raise ValueError(f"Reference header not found in {spec['path']}")
    header = [str(value).strip() or f"unnamed_{index}" for index, value in enumerate(rows[header_index])]
    width = len(header)
    body = [row[:width] + [""] * max(0, width - len(row)) for row in rows[header_index + 1 :]]
    frame = pd.DataFrame(body, columns=header)
    diary = next(column for column in frame if column.strip().lower() == "diary")
    frame["start"] = frame["from_date"].map(_parse_excel_datetime)
    frame["end"] = frame["to_date"].map(_parse_excel_datetime)
    frame["reference_room"] = frame[diary].map(normalise_location)
    return frame.dropna(subset=["start", "end"]).loc[lambda x: x["reference_room"].ne("Unknown"), ["start", "end", "reference_room"]]


def align_reference(reference: pd.DataFrame, timeline: pd.DataFrame) -> pd.Series:
    result = pd.Series(pd.NA, index=timeline.index, dtype="object")
    for row in reference.itertuples(index=False):
        overlap = (result.index >= row.start) & (result.index < row.end)
        result.loc[overlap] = row.reference_room
    return result


def _method_metrics(reference: pd.Series, prediction: pd.Series, method: str) -> dict[str, object]:
    valid_reference = reference.notna()
    evaluable = valid_reference & prediction.notna() & prediction.ne("Unknown")
    coverage = float(evaluable.sum() / valid_reference.sum()) if valid_reference.sum() else np.nan
    if evaluable.any():
        conditional = float(accuracy_score(reference[evaluable], prediction[evaluable]))
        balanced = float(balanced_accuracy_score(reference[evaluable], prediction[evaluable]))
        macro_f1 = float(f1_score(reference[evaluable], prediction[evaluable], average="macro", zero_division=0))
    else:
        conditional = balanced = macro_f1 = np.nan
    end_prediction = prediction.where(prediction.notna(), "Unknown")
    end_to_end = float(accuracy_score(reference[valid_reference], end_prediction[valid_reference])) if valid_reference.any() else np.nan
    return {
        "method": method,
        "reference_windows": int(valid_reference.sum()),
        "evaluable_windows": int(evaluable.sum()),
        "coverage": coverage,
        "conditional_accuracy": conditional,
        "balanced_accuracy": balanced,
        "macro_f1": macro_f1,
        "end_to_end_accuracy": end_to_end,
    }


def evaluate_reference(timeline: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reference = align_reference(load_reference(spec), timeline)
    raw = timeline["raw_room"].copy()
    corrected = timeline["corrected_room"].copy()
    corrected = corrected.mask(timeline["occupancy_state"].isin(["probable_away", "confirmed_away"]), "Out")
    metrics = pd.DataFrame([_method_metrics(reference, raw, "raw_5min_strongest_rssi"), _method_metrics(reference, corrected, "movement_supported_corrected")])
    aligned = pd.DataFrame({"reference_room": reference, "raw_room": raw, "corrected_room": corrected})
    confusion_rows = []
    for method, prediction in (("raw_5min_strongest_rssi", raw), ("movement_supported_corrected", corrected)):
        mask = reference.notna() & prediction.notna() & prediction.ne("Unknown")
        labels = sorted(set(reference[mask]) | set(prediction[mask]))
        if not labels:
            continue
        matrix = confusion_matrix(reference[mask], prediction[mask], labels=labels)
        for actual_index, actual in enumerate(labels):
            for predicted_index, predicted in enumerate(labels):
                confusion_rows.append({"method": method, "reference_room": actual, "predicted_room": predicted, "window_count": int(matrix[actual_index, predicted_index])})
    return metrics, aligned, pd.DataFrame(confusion_rows)


def analyse_copresence(left: pd.DataFrame, right: pd.DataFrame, left_id: str, right_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = ["raw_room", "corrected_room", "occupancy_state", "behaviour_state"]
    merged = left[columns].add_prefix("left_").join(right[columns].add_prefix("right_"), how="inner")
    merged["raw_copresent"] = (
        merged["left_raw_room"].notna()
        & merged["right_raw_room"].notna()
        & merged["left_raw_room"].fillna("__MISSING_LEFT__").eq(merged["right_raw_room"].fillna("__MISSING_RIGHT__"))
    )
    corrected_known = merged["left_corrected_room"].notna() & merged["right_corrected_room"].notna()
    both_indoor = merged["left_occupancy_state"].str.startswith("indoor") & merged["right_occupancy_state"].str.startswith("indoor")
    merged["corrected_copresent"] = (
        corrected_known
        & both_indoor
        & merged["left_corrected_room"].fillna("__MISSING_LEFT__").eq(merged["right_corrected_room"].fillna("__MISSING_RIGHT__"))
    )
    merged["stratum"] = "awake"
    unknown = merged[["left_occupancy_state", "right_occupancy_state"]].isin(["unknown"]).any(axis=1)
    away = merged[["left_occupancy_state", "right_occupancy_state"]].isin(["probable_away", "confirmed_away"]).any(axis=1)
    sleep = merged[["left_behaviour_state", "right_behaviour_state"]].eq("main_sleep").any(axis=1)
    merged.loc[sleep, "stratum"] = "sleep"
    merged.loc[away, "stratum"] = "away"
    merged.loc[unknown, "stratum"] = "unknown"
    rows = []
    for stratum, group in [("all", merged), *list(merged.groupby("stratum"))]:
        rows.append(
            {
                "participant_left": left_id,
                "participant_right": right_id,
                "stratum": stratum,
                "overlap_windows": len(group),
                "raw_copresent_windows": int(group["raw_copresent"].sum()),
                "corrected_copresent_windows": int(group["corrected_copresent"].sum()),
                "added_copresent_windows": int((~group["raw_copresent"] & group["corrected_copresent"]).sum()),
                "removed_copresent_windows": int((group["raw_copresent"] & ~group["corrected_copresent"]).sum()),
                "raw_copresent_hours": float(group["raw_copresent"].sum() * 5 / 60),
                "corrected_copresent_hours": float(group["corrected_copresent"].sum() * 5 / 60),
            }
        )
    return merged, pd.DataFrame(rows)
