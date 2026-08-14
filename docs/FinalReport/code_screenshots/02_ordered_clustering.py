# Verbatim excerpt: src/EighthPhase/core.py, lines 69-155

from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def _ordered_kmeans(values: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    model = KMeans(n_clusters=k, n_init=20, random_state=42)
    labels = model.fit_predict(values.reshape(-1, 1))
    centers = model.cluster_centers_.ravel()
    order = np.argsort(centers)
    remap = np.empty(k, dtype=int)
    remap[order] = np.arange(k)
    return remap[labels], centers[order]


def choose_ordered_clustering(
    values: pd.Series,
    candidates: Iterable[int],
    min_count: int,
    min_fraction: float,
    silhouette_min: float,
    near_best: float,
    silhouette_borderline_min: float | None = None,
    borderline_min_center_ratio: float | None = None,
) -> tuple[pd.Series, np.ndarray | None, pd.DataFrame]:
    """Choose a small, ordered 1-D KMeans model without using labels."""
    clean = values.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    diagnostics = []
    fits: dict[int, tuple[np.ndarray, np.ndarray, float]] = {}
    for k in candidates:
        if len(clean) <= k:
            continue
        if clean.nunique() < k:
            diagnostics.append(
                {
                    "k": k,
                    "silhouette": np.nan,
                    "minimum_cluster_count": 0,
                    "required_cluster_count": max(min_count, int(np.ceil(len(clean) * min_fraction))),
                    "accepted": False,
                    "centers_transformed": "",
                }
            )
            continue
        labels, centers = _ordered_kmeans(clean.to_numpy(), k)
        counts = np.bincount(labels, minlength=k)
        required = max(min_count, int(np.ceil(len(clean) * min_fraction)))
        valid_size = bool((counts >= required).all())
        score = float(silhouette_score(clean.to_numpy().reshape(-1, 1), labels))
        minimum_center_ratio = (
            float(np.exp(np.diff(centers)).min()) if len(centers) > 1 else np.inf
        )
        strong = score >= silhouette_min
        borderline = bool(
            silhouette_borderline_min is not None
            and borderline_min_center_ratio is not None
            and silhouette_borderline_min <= score < silhouette_min
            and minimum_center_ratio >= borderline_min_center_ratio
        )
        accepted = valid_size and (strong or borderline)
        separation_tier = (
            "strong"
            if valid_size and strong
            else "borderline"
            if valid_size and borderline
            else "rejected"
        )
        diagnostics.append(
            {
                "k": k,
                "silhouette": score,
                "minimum_cluster_count": int(counts.min()),
                "required_cluster_count": required,
                "accepted": accepted,
                "separation_tier": separation_tier,
                "minimum_center_ratio": minimum_center_ratio,
                "centers_transformed": "|".join(f"{item:.8g}" for item in centers),
            }
        )
        if accepted:
            fits[k] = (labels, centers, score)
    diagnostic_frame = pd.DataFrame(diagnostics)
    output = pd.Series(pd.NA, index=values.index, dtype="Int64")
    if not fits:
        return output, None, diagnostic_frame
    best_score = max(item[2] for item in fits.values())
    selected_k = min(k for k, item in fits.items() if item[2] >= best_score - near_best)
    labels, centers, _ = fits[selected_k]
    output.loc[clean.index] = labels + 1
    if not diagnostic_frame.empty:
        diagnostic_frame["selected"] = diagnostic_frame["k"].eq(selected_k)
    return output, centers, diagnostic_frame
