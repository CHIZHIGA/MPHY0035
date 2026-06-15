import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")

METRICS_PATH = os.path.join(RESULTS_DIR, "AA002_rssi_representation_metrics.csv")
OUTPUT_PATH = os.path.join(RESULTS_DIR, "AA002_rssi_representation_metrics_comparison.png")

METHOD_LABELS = {
    "strongest_beacon_majority": "Strongest beacon",
    "summary_signature_match": "Summary RSSI signature",
    "summary_plus_step_signature_match": "Summary RSSI + step",
    "summary_plus_acc_signature_match": "Summary RSSI + acc",
    "summary_plus_step_acc_signature_match": "Summary RSSI + step + acc",
    "full_rssi_vector_signature_match": "RSSI vector signature",
    "full_rssi_vector_plus_step_signature_match": "RSSI vector + step",
    "full_rssi_vector_plus_acc_signature_match": "RSSI vector + acc",
    "full_rssi_vector_plus_step_acc_signature_match": "RSSI vector + step + acc",
}

WINDOW_ORDER = ["1min", "5min", "10min"]


def main():
    metrics = pd.read_csv(METRICS_PATH)
    metrics["method_label"] = metrics["method"].map(METHOD_LABELS).fillna(metrics["method"])

    fig, axes = plt.subplots(
        nrows=1,
        ncols=len(WINDOW_ORDER),
        figsize=(18, 8),
        sharex=True,
    )

    for ax, window in zip(axes, WINDOW_ORDER):
        subset = metrics.loc[metrics["window"] == window].copy()
        subset = subset.sort_values("accuracy", ascending=True)

        y_positions = range(len(subset))
        ax.barh(
            [pos - 0.18 for pos in y_positions],
            subset["accuracy"],
            height=0.34,
            label="Overall accuracy",
            color="#3E7CB1",
        )
        ax.barh(
            [pos + 0.18 for pos in y_positions],
            subset["balanced_accuracy"],
            height=0.34,
            label="Balanced accuracy",
            color="#E09F3E",
        )

        ax.set_yticks(list(y_positions))
        ax.set_yticklabels(subset["method_label"], fontsize=9)
        ax.set_title(f"{window} windows")
        ax.set_xlim(0, 0.75)
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Score")

        for pos, accuracy in zip(y_positions, subset["accuracy"]):
            ax.text(
                accuracy + 0.01,
                pos - 0.18,
                f"{accuracy:.2f}",
                va="center",
                fontsize=8,
                color="#1F2D3D",
            )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.suptitle(
        "AA002 RSSI Location Estimation: Feature Representation Comparison",
        fontsize=16,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        "Overall accuracy shows raw prediction agreement; balanced accuracy gives equal weight to each room label.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    fig.savefig(OUTPUT_PATH, dpi=300)
    print(f"Saved plot: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
