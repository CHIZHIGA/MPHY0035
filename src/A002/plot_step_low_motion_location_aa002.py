import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")

METRICS_PATH = os.path.join(RESULTS_DIR, "AA002_step_low_motion_location_metrics.csv")
OUTPUT_PATH = os.path.join(RESULTS_DIR, "AA002_step_low_motion_threshold_comparison.png")

METHOD_LABELS = {
    "strongest_beacon_low_motion": "Strongest beacon",
    "rssi_vector_signature_low_motion": "RSSI vector signature",
}

WINDOW_ORDER = ["1min", "5min", "10min"]


def main():
    metrics = pd.read_csv(METRICS_PATH)
    metrics["method_label"] = metrics["method"].map(METHOD_LABELS).fillna(metrics["method"])

    fig, axes = plt.subplots(
        nrows=len(WINDOW_ORDER),
        ncols=2,
        figsize=(14, 13),
        sharex=False,
    )

    for row_idx, window in enumerate(WINDOW_ORDER):
        subset = metrics.loc[metrics["window"] == window].copy()

        ax_score = axes[row_idx, 0]
        ax_coverage = axes[row_idx, 1]

        for method_label, method_group in subset.groupby("method_label"):
            method_group = method_group.sort_values("step_threshold")
            ax_score.plot(
                method_group["step_threshold"],
                method_group["accuracy"],
                marker="o",
                linewidth=2,
                label=f"{method_label} accuracy",
            )
            ax_score.plot(
                method_group["step_threshold"],
                method_group["balanced_accuracy"],
                marker="s",
                linestyle="--",
                linewidth=2,
                label=f"{method_label} balanced",
            )

            ax_coverage.plot(
                method_group["step_threshold"],
                method_group["coverage"],
                marker="o",
                linewidth=2,
                label=method_label,
            )

        ax_score.set_title(f"{window} windows: location accuracy")
        ax_score.set_xlabel("Step threshold n")
        ax_score.set_ylabel("Score")
        ax_score.set_ylim(0, 0.8)
        ax_score.grid(alpha=0.25)

        ax_coverage.set_title(f"{window} windows: low-motion coverage")
        ax_coverage.set_xlabel("Step threshold n")
        ax_coverage.set_ylabel("Coverage")
        ax_coverage.set_ylim(0, 1.05)
        ax_coverage.grid(alpha=0.25)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.suptitle(
        "AA002 Step-Count Low-Motion RSSI Location Algorithm",
        fontsize=16,
        y=0.985,
    )
    fig.text(
        0.5,
        0.02,
        "Lower step thresholds keep only more stationary windows; coverage shows how much annotated data remains.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    fig.savefig(OUTPUT_PATH, dpi=300)
    print(f"Saved plot: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

