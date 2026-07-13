"""Derive an EF-001 long-low-motion threshold from log ACC variability."""

import csv
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "Results/SeventhPhase/EF-001/EF-001_acc_5min_features.csv"
OUTPUT = ROOT / "Results/SeventhPhase/EF-001/EF-001_acc_threshold_clusters.png"
SUMMARY = ROOT / "Results/SeventhPhase/EF-001/EF-001_acc_threshold_clusters.csv"
N_CLUSTERS = 4


def load_values():
    with INPUT.open() as handle:
        rows = list(csv.DictReader(handle))
    values = np.array([float(row["acc_magnitude_std_clean"]) for row in rows])
    return values[np.isfinite(values) & (values > 0)]


def kmeans_1d(values, k):
    centers = np.quantile(values, np.linspace(0.05, 0.95, k))
    for _ in range(200):
        labels = np.argmin(np.abs(values[:, None] - centers), axis=1)
        updated = np.array([values[labels == index].mean() for index in range(k)])
        if np.max(np.abs(updated - centers)) < 1e-12:
            break
        centers = updated
    order = np.argsort(centers)
    centers = centers[order]
    relabel = np.empty(k, dtype=int)
    relabel[order] = np.arange(k)
    return centers, relabel[labels]


def main():
    acc_std = load_values()
    log_std = np.log10(acc_std)
    log_centers, labels = kmeans_1d(log_std, N_CLUSTERS)
    centers = 10 ** log_centers
    boundaries = 10 ** ((log_centers[:-1] + log_centers[1:]) / 2)
    selected = boundaries[1]

    with SUMMARY.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["cluster", "window_count", "center_acc_std", "next_boundary_acc_std"])
        for index, center in enumerate(centers):
            writer.writerow([index + 1, int(np.sum(labels == index)), center, boundaries[index] if index < len(boundaries) else ""])

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    bins = np.linspace(log_std.min(), log_std.max(), 90)
    colors = ["#24478f", "#67a9cf", "#fdae61", "#d73027"]
    for index in range(N_CLUSTERS):
        ax.hist(log_std[labels == index], bins=bins, color=colors[index], alpha=0.72, label=f"State {index + 1}: centre={centers[index]:.4f}")
    ax.axvline(np.log10(selected), color="#7a1fa2", ls="--", lw=2, label=f"Selected cluster boundary={selected:.5f} (~0.023)")
    ticks = np.array([0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2])
    ax.set_xticks(np.log10(ticks), [f"{value:g}" for value in ticks])
    ax.set_xlabel("5-min clean ACC magnitude std (log scale)")
    ax.set_ylabel("Window count")
    ax.set_title("EF-001 unsupervised ACC motion-state structure")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=220)
    plt.close(fig)
    print("centers:", ", ".join(f"{value:.5f}" for value in centers))
    print("boundaries:", ", ".join(f"{value:.5f}" for value in boundaries))
    print(f"selected long-low-motion threshold: {selected:.5f} (reported as 0.023)")
    print(OUTPUT)
    print(SUMMARY)


if __name__ == "__main__":
    main()
