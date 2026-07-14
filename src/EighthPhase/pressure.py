"""Optional pressure-floor audit and conservative same-floor RSSI constraint."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


# A stable offset between beacon pressure sensors is not, by itself, evidence of
# different floors.  About 0.20 hPa can be produced by sensor calibration and
# mounting-height differences within one floor.  Automatic floor inference
# therefore uses a more conservative, storey-scale separation and an explicit
# K=1 (no resolved floor structure) fallback.
PRESSURE_MIN_FLOOR_SEPARATION_HPA = 0.30
PRESSURE_MIN_GROUP_SILHOUETTE = 0.75
PRESSURE_MIN_BEACONS_PER_GROUP = 2
PRESSURE_MIN_OVERLAP_WINDOWS = 100


def _auto_groups(environmental: pd.DataFrame) -> tuple[dict[str, str], dict[str, object]]:
    overlap = environmental.dropna(thresh=2)
    audit: dict[str, object] = {
        "pressure_overlap_windows": len(overlap),
        "pressure_auto_groups_valid": False,
        "pressure_min_floor_separation_hpa": PRESSURE_MIN_FLOOR_SEPARATION_HPA,
        "pressure_min_group_silhouette": PRESSURE_MIN_GROUP_SILHOUETTE,
        "pressure_null_model_selected": True,
    }
    if len(overlap) < PRESSURE_MIN_OVERLAP_WINDOWS or environmental.shape[1] < 4:
        audit["pressure_reason"] = "insufficient_overlap_or_beacons"
        return {}, audit
    relative = overlap.sub(overlap.median(axis=1), axis=0)
    offsets = relative.median(axis=0).dropna().sort_values()
    candidate_models = []
    for k in (2, 3):
        if len(offsets) < PRESSURE_MIN_BEACONS_PER_GROUP * k:
            continue
        model = KMeans(n_clusters=k, n_init=20, random_state=42).fit(offsets.to_numpy().reshape(-1, 1))
        labels = model.labels_
        centers = model.cluster_centers_.ravel()
        order = np.argsort(centers)
        remap = np.empty(k, dtype=int)
        remap[order] = np.arange(k)
        labels = remap[labels]
        centers = centers[order]
        counts = np.bincount(labels, minlength=k)
        separations = np.diff(centers)
        within = []
        for label in range(k):
            cluster = offsets.to_numpy()[labels == label]
            median = np.median(cluster)
            within.append(np.median(np.abs(cluster - median)))
        pooled_mad = max(float(np.median(within)), 1e-6)
        score = float(silhouette_score(offsets.to_numpy().reshape(-1, 1), labels))
        min_separation = float(separations.min()) if len(separations) else np.nan
        valid = bool(
            (counts >= PRESSURE_MIN_BEACONS_PER_GROUP).all()
            and (separations >= PRESSURE_MIN_FLOOR_SEPARATION_HPA).all()
            and (separations >= 3 * pooled_mad).all()
            and score >= PRESSURE_MIN_GROUP_SILHOUETTE
        )
        candidate_models.append(
            {
                "k": k,
                "score": score,
                "labels": labels,
                "centers": centers,
                "counts": counts,
                "min_separation": min_separation,
                "pooled_mad": pooled_mad,
                "valid": valid,
            }
        )
    valid_models = [item for item in candidate_models if item["valid"]]
    if not valid_models:
        if candidate_models:
            best = max(candidate_models, key=lambda item: item["score"])
            audit.update(
                {
                    "pressure_floor_k": 1,
                    "pressure_candidate_k": best["k"],
                    "pressure_candidate_silhouette": best["score"],
                    "pressure_candidate_centers_hpa": "|".join(f"{item:.5g}" for item in best["centers"]),
                    "pressure_candidate_min_separation_hpa": best["min_separation"],
                    "pressure_candidate_pooled_mad_hpa": best["pooled_mad"],
                }
            )
            failures = []
            if best["score"] < PRESSURE_MIN_GROUP_SILHOUETTE:
                failures.append("silhouette")
            if best["min_separation"] < PRESSURE_MIN_FLOOR_SEPARATION_HPA:
                failures.append("floor_scale_separation")
            if (best["counts"] < PRESSURE_MIN_BEACONS_PER_GROUP).any():
                failures.append("group_size")
            if best["min_separation"] < 3 * best["pooled_mad"]:
                failures.append("within_group_dispersion")
            audit["pressure_reason"] = "k1_null_selected_" + "_and_".join(failures or ["acceptance_failed"])
        else:
            audit["pressure_floor_k"] = 1
            audit["pressure_reason"] = "k1_null_selected_no_valid_candidate"
        return {}, audit
    valid_models.sort(key=lambda item: item["score"], reverse=True)
    selected = valid_models[0]
    k2 = next((item for item in valid_models if item["k"] == 2), None)
    if selected["k"] == 3 and k2 is not None and selected["score"] < k2["score"] + 0.05:
        selected = k2
    k = selected["k"]
    score = selected["score"]
    labels = selected["labels"]
    centers = selected["centers"]
    groups = {str(beacon): f"pressure_floor_{int(label) + 1}" for beacon, label in zip(offsets.index, labels)}
    audit.update(
        {
            "pressure_auto_groups_valid": True,
            "pressure_null_model_selected": False,
            "pressure_group_source": "automatic",
            "pressure_floor_k": k,
            "pressure_group_silhouette": score,
            "pressure_group_centers_hpa": "|".join(f"{item:.5g}" for item in centers),
            "pressure_group_min_separation_hpa": selected["min_separation"],
            "pressure_group_pooled_mad_hpa": selected["pooled_mad"],
            "pressure_reason": "stable_multifloor_grouping",
        }
    )
    return groups, audit


def constrain_rssi_with_pressure(
    rssi_mean: pd.DataFrame,
    environmental_pressure: pd.DataFrame,
    wearable_pressure: pd.Series,
    movement_state: pd.Series | None = None,
    floor_override: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    info = pd.DataFrame(index=rssi_mean.index)
    info["pressure_floor_group"] = pd.NA
    info["pressure_floor_confidence"] = np.nan
    info["pressure_floor_trusted"] = False
    info["pressure_status"] = "inactive"
    if environmental_pressure.empty or wearable_pressure.dropna().empty:
        return rssi_mean.copy(), info, {"pressure_enabled": False, "pressure_reason": "missing_dual_pressure"}
    if floor_override:
        groups = {str(key): str(value) for key, value in floor_override.items() if key in environmental_pressure.columns}
        audit = {
            "pressure_overlap_windows": int(environmental_pressure.notna().any(axis=1).sum()),
            "pressure_auto_groups_valid": False,
            "pressure_group_source": "manual_override",
            "pressure_floor_k": len(set(groups.values())),
            "pressure_reason": "configured_floor_override",
        }
    else:
        groups, audit = _auto_groups(environmental_pressure)
    if len(set(groups.values())) < 2:
        return rssi_mean.copy(), info, {**audit, "pressure_enabled": False}

    group_pressure = pd.DataFrame(index=rssi_mean.index)
    for group in sorted(set(groups.values())):
        beacons = [beacon for beacon, label in groups.items() if label == group]
        group_pressure[group] = environmental_pressure.reindex(index=rssi_mean.index, columns=beacons).median(axis=1)
    raw_winner = rssi_mean.apply(lambda row: row.idxmax() if row.notna().any() else pd.NA, axis=1)
    raw_group = raw_winner.map(groups)
    calibration = []
    for timestamp in rssi_mean.index:
        group = raw_group.get(timestamp)
        if pd.notna(group) and pd.notna(wearable_pressure.get(timestamp)) and pd.notna(group_pressure.at[timestamp, group]):
            calibration.append(wearable_pressure.get(timestamp) - group_pressure.at[timestamp, group])
    if len(calibration) < 20:
        return rssi_mean.copy(), info, {**audit, "pressure_enabled": False, "pressure_reason": "insufficient_wearable_calibration"}
    offset = float(np.median(calibration))
    adjusted = wearable_pressure.reindex(rssi_mean.index) - offset
    distances = group_pressure.sub(adjusted, axis=0).abs()
    inferred = distances.apply(
        lambda row: row.idxmin() if row.notna().any() else np.nan,
        axis=1,
    )
    ordered = np.sort(distances.to_numpy(dtype=float), axis=1)
    closest = distances.min(axis=1)
    second = pd.Series(np.nan, index=distances.index)
    for position, row in enumerate(distances.to_numpy(dtype=float)):
        finite = np.sort(row[np.isfinite(row)])
        if len(finite) >= 2:
            second.iloc[position] = finite[1]
    margin = second - closest
    confidence = (margin / (margin + closest + 0.05)).clip(0, 1)
    transition = inferred.ne(inferred.shift()) & inferred.notna() & inferred.shift().notna()
    if movement_state is None:
        movement_supported = pd.Series(False, index=rssi_mean.index)
    else:
        moving = movement_state.reindex(rssi_mean.index).fillna(1).gt(1)
        movement_supported = moving | moving.shift(fill_value=False) | moving.shift(-1, fill_value=False)
    trusted = confidence.ge(0.75) & (~transition | movement_supported)

    constrained = rssi_mean.copy()
    for timestamp in rssi_mean.index[trusted.fillna(False)]:
        group = inferred.at[timestamp]
        allowed = [beacon for beacon, label in groups.items() if label == group and beacon in constrained.columns]
        if allowed and constrained.loc[timestamp, allowed].notna().any():
            constrained.loc[timestamp, [column for column in constrained.columns if column not in allowed]] = np.nan
    info["pressure_floor_group"] = inferred
    info["pressure_floor_confidence"] = confidence
    info["pressure_floor_trusted"] = trusted.fillna(False)
    info["pressure_status"] = np.select(
        [info["pressure_floor_trusted"], confidence.notna(), environmental_pressure.notna().any(axis=1)],
        ["trusted_same_floor_constraint", "low_confidence_kept_raw", "environmental_pressure_only"],
        default="inactive",
    )
    audit.update(
        {
            "pressure_enabled": True,
            "pressure_calibration_offset_hpa": offset,
            "pressure_trusted_windows": int(trusted.sum()),
            "pressure_groups": "|".join(f"{key}:{value}" for key, value in sorted(groups.items())),
        }
    )
    return constrained, info, audit
