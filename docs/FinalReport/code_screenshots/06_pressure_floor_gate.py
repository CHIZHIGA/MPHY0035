# Verbatim excerpt: src/EighthPhase/pressure.py, lines 22-127

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from EighthPhase.pressure import (
    PRESSURE_MIN_BEACONS_PER_GROUP,
    PRESSURE_MIN_FLOOR_SEPARATION_HPA,
    PRESSURE_MIN_GROUP_SILHOUETTE,
    PRESSURE_MIN_OVERLAP_WINDOWS,
)


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
