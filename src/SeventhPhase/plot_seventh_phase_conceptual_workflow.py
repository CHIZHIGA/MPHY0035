"""Draw the conceptual workflow used for EF-001 and EF-002."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "Results" / "SeventhPhase"
PNG_PATH = OUTPUT_DIR / "SeventhPhase_movement_supported_rssi_workflow.png"
SVG_PATH = OUTPUT_DIR / "SeventhPhase_movement_supported_rssi_workflow.svg"

COLORS = {
    "acc": "#e8f2fb",
    "acc_edge": "#3d78a8",
    "rssi": "#fff0e5",
    "rssi_edge": "#c87532",
    "fusion": "#eee8f7",
    "fusion_edge": "#76539a",
    "output": "#e8f5ec",
    "output_edge": "#3f8458",
    "guard": "#f2f2f2",
    "guard_edge": "#707070",
    "arrow": "#4a4a4a",
}


def add_box(ax, x, y, width, height, text, face, edge, fontsize=9.2, lw=1.5):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.035,rounding_size=0.10",
        linewidth=lw,
        edgecolor=edge,
        facecolor=face,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color="#222222",
        linespacing=1.28,
        zorder=3,
    )
    return patch


def arrow(ax, start, end, color=None, connectionstyle="arc3,rad=0", lw=1.55):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=lw,
            color=color or COLORS["arrow"],
            connectionstyle=connectionstyle,
            shrinkA=2,
            shrinkB=2,
            zorder=1,
        )
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(16, 8.8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(
        8,
        8.62,
        "Movement-supported RSSI room correction: conceptual workflow",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color="#202020",
    )
    ax.text(
        8,
        8.27,
        "RSSI proposes where the participant is; ACC tests whether rapid changes are physically plausible",
        ha="center",
        va="center",
        fontsize=10.5,
        color="#555555",
    )

    # ACC branch.
    ax.text(0.25, 7.47, "MOVEMENT EVIDENCE", fontsize=10, fontweight="bold", color=COLORS["acc_edge"])
    acc_boxes = [
        (0.35, 6.05, 2.15, 1.15, "Tri-axial ACC\nx, y, z"),
        (2.85, 6.05, 2.15, 1.15, "Orientation-independent\nmagnitude m(t)"),
        (5.35, 6.05, 2.15, 1.15, "Fixed, non-overlapping\n5-min magnitude SD"),
        (7.85, 6.05, 2.15, 1.15, "Log-space motion-state\nclustering"),
        (10.35, 6.05, 2.15, 1.15, "Low-motion windows\n(dataset-specific threshold)"),
        (12.85, 6.05, 2.80, 1.15, "Continuity + duration\n→ long low-motion episode"),
    ]
    for item in acc_boxes:
        add_box(ax, *item, COLORS["acc"], COLORS["acc_edge"])
    for left, right in zip(acc_boxes, acc_boxes[1:]):
        arrow(ax, (left[0] + left[2], left[1] + left[3] / 2), (right[0], right[1] + right[3] / 2), COLORS["acc_edge"])

    # RSSI branch.
    ax.text(0.25, 4.92, "SPATIAL EVIDENCE", fontsize=10, fontweight="bold", color=COLORS["rssi_edge"])
    rssi_boxes = [
        (0.35, 3.60, 2.15, 1.15, "Beacon RSSI\nobservations"),
        (3.10, 3.60, 2.45, 1.15, "Fixed, non-overlapping\n5-min mean per beacon"),
        (6.15, 3.60, 2.45, 1.15, "Strongest beacon\narg max of mean RSSI"),
        (9.20, 3.60, 2.45, 1.15, "Raw categorical\nroom timeline"),
    ]
    for item in rssi_boxes:
        add_box(ax, *item, COLORS["rssi"], COLORS["rssi_edge"])
    for left, right in zip(rssi_boxes, rssi_boxes[1:]):
        arrow(ax, (left[0] + left[2], left[1] + left[3] / 2), (right[0], right[1] + right[3] / 2), COLORS["rssi_edge"])

    # Cross-signal interpretation.
    add_box(
        ax,
        12.35,
        3.35,
        3.30,
        1.65,
        "Cross-signal interpretation\n\nDo room-label changes agree\nwith the movement context?",
        COLORS["fusion"],
        COLORS["fusion_edge"],
        fontsize=9.6,
        lw=1.8,
    )
    arrow(ax, (11.65, 4.18), (12.35, 4.18), COLORS["rssi_edge"])
    arrow(
        ax,
        (14.25, 6.05),
        (14.05, 5.00),
        COLORS["acc_edge"],
        connectionstyle="arc3,rad=0.08",
    )

    # Dataset-specific outputs.
    ax.text(0.25, 2.62, "CONSERVATIVE CORRECTION", fontsize=10, fontweight="bold", color=COLORS["output_edge"])
    add_box(
        ax,
        0.35,
        1.10,
        4.60,
        1.25,
        "EF-001: long low-motion episode\nAssign the dominant observed room across the episode",
        COLORS["output"],
        COLORS["output_edge"],
        fontsize=9.6,
    )
    add_box(
        ax,
        5.30,
        1.10,
        4.60,
        1.25,
        "Outside EF-001 sleep episodes\nHigh motion: keep raw room  |  Low motion: 60-min vote",
        COLORS["output"],
        COLORS["output_edge"],
        fontsize=9.2,
    )
    add_box(
        ax,
        10.25,
        1.10,
        5.40,
        1.25,
        "EF-002: RSSI gap inside a main-sleep episode\nFill Bedroom only when both 30-min contexts support Bedroom",
        COLORS["output"],
        COLORS["output_edge"],
        fontsize=9.4,
    )
    for x in (2.65, 7.60, 12.95):
        arrow(
            ax,
            (14.00, 3.35),
            (x, 2.35),
            COLORS["fusion_edge"],
            connectionstyle=f"arc3,rad={0.10 if x < 10 else -0.08}",
        )

    add_box(
        ax,
        2.20,
        0.18,
        11.60,
        0.55,
        "Guardrails: never infer a room from ACC alone  |  do not cross data gaps  |  keep unsupported RSSI missing  |  preserve uncertainty",
        COLORS["guard"],
        COLORS["guard_edge"],
        fontsize=9.0,
        lw=1.2,
    )

    fig.tight_layout(pad=0.5)
    fig.savefig(PNG_PATH, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(SVG_PATH, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(PNG_PATH)
    print(SVG_PATH)


if __name__ == "__main__":
    main()
