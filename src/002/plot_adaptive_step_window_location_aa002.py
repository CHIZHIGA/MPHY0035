import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")

METRICS_PATH = os.path.join(RESULTS_DIR, "AA002_adaptive_step_window_location_metrics.csv")
CONFIDENCE_METRICS_PATH = os.path.join(
    RESULTS_DIR,
    "AA002_rssi_stability_confidence_metrics.csv",
)
OUTPUT_PATH = os.path.join(RESULTS_DIR, "AA002_adaptive_step_window_location_comparison.png")
CONFIDENCE_OUTPUT_PATH = os.path.join(
    RESULTS_DIR,
    "AA002_rssi_stability_confidence_comparison.png",
)

METHOD_LABELS = {
    "pure_rssi_1min_strongest": "Pure RSSI 1min",
    "pure_rssi_5min_strongest": "Pure RSSI 5min",
    "pure_rssi_10min_strongest": "Pure RSSI 10min",
    "adaptive_step_window_strongest": "Adaptive step only",
    "adaptive_step_rssi_stability_strongest": "Adaptive step + RSSI stability",
}


def method_order(method):
    order = {
        "pure_rssi_1min_strongest": 0,
        "pure_rssi_5min_strongest": 1,
        "pure_rssi_10min_strongest": 2,
        "adaptive_step_window_strongest": 3,
        "adaptive_step_rssi_stability_strongest": 4,
    }
    return order.get(method, 99)


def main():
    metrics = pd.read_csv(METRICS_PATH)
    metrics["method_label"] = metrics["method"].map(METHOD_LABELS).fillna(metrics["method"])
    metrics["order"] = metrics["method"].apply(method_order)
    metrics = metrics.sort_values("order")

    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(16, 7))

    ax = axes[0]
    y_positions = range(len(metrics))
    colors = [
        "#2E86AB"
        if row["mode"] == "fixed"
        else "#2A9D8F"
        if row["mode"] == "adaptive"
        else "#6A4C93"
        for _, row in metrics.iterrows()
    ]
    ax.barh(y_positions, metrics["accuracy"], color=colors, alpha=0.9, label="Accuracy")
    ax.scatter(
        metrics["balanced_accuracy"],
        y_positions,
        color="#E76F51",
        marker="D",
        s=55,
        label="Balanced accuracy",
        zorder=4,
    )
    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(metrics["method_label"])
    ax.invert_yaxis()
    ax.set_xlim(0, 0.8)
    ax.set_xlabel("Score")
    ax.set_title("Pure RSSI vs Step-Aware Adaptive Window")
    ax.grid(axis="x", alpha=0.25)

    for pos, value in zip(y_positions, metrics["accuracy"]):
        ax.text(value + 0.01, pos, f"{value:.2f}", va="center", fontsize=9)

    ax.legend(loc="lower right", frameon=False)

    adaptive = metrics.loc[metrics["mode"].isin(["adaptive", "stability_adaptive"])].copy()
    usage_cols = [
        "selected_1min_fraction",
        "selected_5min_fraction",
        "selected_10min_fraction",
    ]
    usage = adaptive.set_index("method_label")[usage_cols]
    usage.columns = ["1min", "5min", "10min"]

    ax_usage = axes[1]
    usage.plot(
        kind="bar",
        stacked=True,
        ax=ax_usage,
        color=["#F4A261", "#E9C46A", "#264653"],
    )
    ax_usage.set_ylim(0, 1.0)
    ax_usage.set_ylabel("Fraction of predictions")
    ax_usage.set_title("Adaptive Window Choices")
    ax_usage.set_xlabel("")
    ax_usage.grid(axis="y", alpha=0.25)
    ax_usage.legend(title="Selected window", frameon=False)
    ax_usage.tick_params(axis="x", rotation=0)

    fig.suptitle(
        "AA002 Adaptive Step and RSSI-Stability Location Algorithm",
        fontsize=16,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        "Step+stability rule: use long windows only when step count is low and the strongest beacon signature is stable.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.94])
    fig.savefig(OUTPUT_PATH, dpi=300)
    print(f"Saved plot: {OUTPUT_PATH}")

    confidence = pd.read_csv(CONFIDENCE_METRICS_PATH)
    confidence_order = ["High", "Medium", "Low"]
    confidence["confidence_label"] = pd.Categorical(
        confidence["confidence_label"],
        categories=confidence_order,
        ordered=True,
    )
    confidence = confidence.sort_values("confidence_label")

    fig_conf, axes_conf = plt.subplots(nrows=1, ncols=2, figsize=(12, 5))

    ax_score = axes_conf[0]
    labels = confidence["confidence_label"].astype(str)
    ax_score.bar(
        labels,
        confidence["accuracy"],
        color="#2A9D8F",
        alpha=0.9,
        label="Accuracy",
    )
    ax_score.scatter(
        labels,
        confidence["balanced_accuracy"],
        color="#E76F51",
        marker="D",
        s=60,
        label="Balanced accuracy",
        zorder=4,
    )
    ax_score.set_ylim(0, 0.9)
    ax_score.set_ylabel("Score")
    ax_score.set_title("10min RSSI Prediction by Confidence")
    ax_score.grid(axis="y", alpha=0.25)
    ax_score.legend(frameon=False)

    for label, value in zip(labels, confidence["accuracy"]):
        ax_score.text(label, value + 0.02, f"{value:.2f}", ha="center", fontsize=9)

    ax_cov = axes_conf[1]
    ax_cov.bar(labels, confidence["coverage"], color="#264653", alpha=0.9)
    ax_cov.set_ylim(0, 1.0)
    ax_cov.set_ylabel("Coverage")
    ax_cov.set_title("Share of Windows by Confidence")
    ax_cov.grid(axis="y", alpha=0.25)

    for label, value in zip(labels, confidence["coverage"]):
        ax_cov.text(label, value + 0.02, f"{value:.2f}", ha="center", fontsize=9)

    fig_conf.suptitle(
        "AA002 RSSI Stability Confidence Score",
        fontsize=15,
        y=0.98,
    )
    fig_conf.text(
        0.5,
        0.02,
        "Confidence uses 10min step count, strongest-beacon stability, and strongest-second RSSI gap.",
        ha="center",
        fontsize=10,
    )
    fig_conf.tight_layout(rect=[0, 0.06, 1, 0.92])
    fig_conf.savefig(CONFIDENCE_OUTPUT_PATH, dpi=300)
    print(f"Saved confidence plot: {CONFIDENCE_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
