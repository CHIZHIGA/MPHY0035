import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "Results" / "FifthPhase"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

X001_PROFILE_PATH = (
    ROOT
    / "Results"
    / "X001"
    / "ForthPhase"
    / "X001_forthphase_combined_low_motion_cluster_profiles.csv"
)
PARIS_PROFILE_PATH = RESULTS_DIR / "DH_Paris_low_motion_cluster_profiles.csv"

OUTPUT_FIG = RESULTS_DIR / "RSSI_evidence_signal_stability_summary.png"
OUTPUT_CSV = RESULTS_DIR / "RSSI_evidence_signal_stability_summary.csv"


def load_profiles(path, dataset):
    frame = pd.read_csv(path)
    output = pd.DataFrame(
        {
            "dataset": dataset,
            "cluster": frame["cluster"].astype(str),
            "dominant_location": frame["dominant_mapped_location"].astype(str),
            "training_windows": frame["training_windows"],
            "predicted_windows": frame["predicted_windows"],
            "mean_rssi_evidence_samples": frame["mean_rssi_evidence_samples"],
            "mean_signal_separation_gap": frame["mean_signal_separation_gap"],
            "mean_training_steps": frame.get(
                "mean_steps_window_training",
                frame.get("mean_steps_training"),
            ),
        }
    )
    output["cluster_label"] = (
        output["dataset"]
        + " C"
        + output["cluster"]
        + " "
        + output["dominant_location"]
    )
    return output


def plot_dataset(axs, frame, title):
    frame = frame.sort_values(["dominant_location", "cluster"]).copy()
    labels = ["C" + row.cluster + " " + row.dominant_location for row in frame.itertuples()]
    y = range(len(frame))
    metrics = [
        ("mean_rssi_evidence_samples", "Mean RSSI samples"),
        ("mean_signal_separation_gap", "Mean strongest-second gap"),
        ("mean_training_steps", "Mean steps in training windows"),
        ("predicted_windows", "Predicted windows"),
    ]
    colors = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]
    for ax, (column, label), color in zip(axs, metrics, colors):
        ax.barh(y, frame[column], color=color, alpha=0.88)
        ax.set_yticks(list(y))
        ax.set_yticklabels(labels)
        ax.set_title(label)
        ax.grid(axis="x", alpha=0.22)
        for idx, value in enumerate(frame[column]):
            ax.text(value, idx, f" {value:.1f}", va="center", fontsize=8)
    axs[0].set_ylabel(title)


def main():
    x001 = load_profiles(X001_PROFILE_PATH, "X001 combined 4c")
    paris = load_profiles(PARIS_PROFILE_PATH, "DH Paris 4c")
    summary = pd.concat([x001, paris], ignore_index=True)
    summary.to_csv(OUTPUT_CSV, index=False)

    fig, axes = plt.subplots(
        2,
        4,
        figsize=(18, 8.4),
        gridspec_kw={"height_ratios": [len(x001), len(paris)]},
    )
    plot_dataset(axes[0], x001, "X001 combined clustering")
    plot_dataset(axes[1], paris, "DH Paris clustering")
    fig.suptitle(
        "RSSI evidence / signal stability summary for low-motion clustering",
        fontsize=15,
    )
    fig.text(
        0.5,
        0.035,
        "This replaces the less intuitive confidence-score heat map with direct evidence measures. "
        "Higher RSSI sample count and larger strongest-second gap suggest more stable RSSI evidence; "
        "low training-window steps confirm that clusters were learned from low-motion periods.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.95])
    fig.savefig(OUTPUT_FIG, dpi=220, bbox_inches="tight")
    plt.close(fig)

    print(OUTPUT_CSV)
    print(OUTPUT_FIG)


if __name__ == "__main__":
    main()
