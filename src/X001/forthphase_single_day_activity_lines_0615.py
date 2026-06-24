import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

from forthphase_fixed_rssi_window_comparison import (
    RESULTS_DIR,
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
)


FIGURES_DIR = Path(RESULTS_DIR) / "Figures_0615"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

TARGET_PERIOD_START = pd.Timestamp("2026-01-14 12:00:00")
TARGET_PERIOD_END = TARGET_PERIOD_START + pd.Timedelta(days=1)

FIXED_TIMELINE_PATH = Path(RESULTS_DIR) / (
    "X001_forthphase_fixed_rssi_window_copresence_timeline.csv"
)
ADAPTIVE_TIMELINE_PATH = Path(RESULTS_DIR) / (
    "X001_forthphase_hierarchical_step_adaptive_rssi_timeline.csv"
)
CLUSTER_TIMELINE_PATH = Path(RESULTS_DIR) / (
    "X001_forthphase_low_motion_cluster_timeline.csv"
)

LOCATION_COLORS = {
    "Bathroom": "#4c78a8",
    "Bedroom": "#f58518",
    "Dining": "#54a24b",
    "Kitchen": "#e45756",
    "Living": "#72b7b2",
    "Office": "#b279a2",
    "Other 1": "#ff9da6",
    "Unmapped": "#b5b5b5",
}

METHODS = [
    {
        "key": "4a_fixed5",
        "label": "4a fixed 5min RSSI",
        "duration_minutes": 5,
        "location_output": "X001_0615_single_day_locations_activity_4a_fixed5.png",
        "copresence_output": "X001_0615_single_day_copresence_4a_fixed5.png",
        "combined_output": "X001_0615_single_period_combined_4a_fixed5.png",
    },
    {
        "key": "4a_fixed10",
        "label": "4a fixed 10min RSSI",
        "duration_minutes": 10,
        "location_output": "X001_0615_single_day_locations_activity_4a_fixed10.png",
        "copresence_output": "X001_0615_single_day_copresence_4a_fixed10.png",
        "combined_output": "X001_0615_single_period_combined_4a_fixed10.png",
    },
    {
        "key": "4a_fixed30",
        "label": "4a fixed 30min RSSI",
        "duration_minutes": 30,
        "location_output": "X001_0615_single_day_locations_activity_4a_fixed30.png",
        "copresence_output": "X001_0615_single_day_copresence_4a_fixed30.png",
        "combined_output": "X001_0615_single_period_combined_4a_fixed30.png",
    },
    {
        "key": "4b_adaptive10",
        "label": "4b step-adaptive RSSI, threshold 10",
        "duration_minutes": 1,
        "location_output": "X001_0615_single_day_locations_activity_4b_adaptive10.png",
        "copresence_output": "X001_0615_single_day_copresence_4b_adaptive10.png",
        "combined_output": "X001_0615_single_period_combined_4b_adaptive10.png",
    },
    {
        "key": "4c_clustering",
        "label": "4c low-motion RSSI clustering",
        "duration_minutes": 30,
        "location_output": "X001_0615_single_day_locations_activity_4c_clustering.png",
        "copresence_output": "X001_0615_single_day_copresence_4c_clustering.png",
        "combined_output": "X001_0615_single_period_combined_4c_clustering.png",
    },
]


def read_time_csv(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    return df


def period_minute(series):
    return (series - TARGET_PERIOD_START) / pd.Timedelta(minutes=1)


def target_day(df):
    return df.loc[
        (df["time"] >= TARGET_PERIOD_START) & (df["time"] < TARGET_PERIOD_END)
    ].copy()


def load_activity_source():
    adaptive = read_time_csv(ADAPTIVE_TIMELINE_PATH)
    adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
    adaptive = target_day(adaptive)
    activity = adaptive[
        [
            "time",
            "subject_steps_5min",
            "study_partner_steps_5min",
        ]
    ].sort_values("time")
    return activity


def add_activity(frame, activity):
    output = frame.sort_values("time").copy()
    output = pd.merge_asof(
        output,
        activity,
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(minutes=2),
    )
    return output


def load_method_frame(method_key, activity):
    if method_key.startswith("4a_"):
        window = method_key.replace("4a_fixed", "") + "min"
        fixed = read_time_csv(FIXED_TIMELINE_PATH)
        fixed = fixed.loc[fixed["window"].eq(window)].copy()
        fixed = fixed.rename(
            columns={
                "subject_strongest_location": "subject_location",
                "study_partner_strongest_location": "study_partner_location",
            }
        )
        fixed = target_day(fixed)
        return add_activity(
            fixed[
                [
                    "time",
                    "subject_location",
                    "study_partner_location",
                    "copresence_label",
                ]
            ],
            activity,
        )

    if method_key == "4b_adaptive10":
        adaptive = read_time_csv(ADAPTIVE_TIMELINE_PATH)
        adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
        adaptive = adaptive.rename(
            columns={
                "subject_strongest_location": "subject_location",
                "study_partner_strongest_location": "study_partner_location",
            }
        )
        adaptive = target_day(adaptive)
        return adaptive[
            [
                "time",
                "subject_location",
                "study_partner_location",
                "copresence_label",
                "subject_steps_5min",
                "study_partner_steps_5min",
            ]
        ].copy()

    if method_key == "4c_clustering":
        cluster = read_time_csv(CLUSTER_TIMELINE_PATH)
        cluster = cluster.rename(
            columns={
                "subject_cluster_location": "subject_location",
                "study_partner_cluster_location": "study_partner_location",
            }
        )
        cluster = target_day(cluster)
        return add_activity(
            cluster[
                [
                    "time",
                    "subject_location",
                    "study_partner_location",
                    "copresence_label",
                ]
            ],
            activity,
        )

    raise ValueError(f"Unknown method key: {method_key}")


def build_location_palette(frames):
    palette = dict(LOCATION_COLORS)
    cmap = plt.get_cmap("tab20")
    values = set()
    for frame in frames:
        values.update(frame["subject_location"].fillna("Unmapped").astype(str).unique())
        values.update(
            frame["study_partner_location"].fillna("Unmapped").astype(str).unique()
        )
    for value in sorted(values):
        if value not in palette:
            palette[value] = cmap(len(palette) % 20)
    return palette


def line_widths(steps):
    clean = pd.to_numeric(steps, "coerce").fillna(0).clip(lower=0)
    scaled = np.log1p(clean)
    upper = scaled.quantile(0.98)
    if pd.isna(upper) or upper <= 0:
        return np.full(len(clean), 2.5)
    return 2.0 + 10.0 * (scaled / upper).clip(upper=1)


def role_segments(frame, role, y, duration_minutes, palette):
    location_col = f"{role}_location"
    step_col = f"{role}_steps_5min"
    segments = []
    colors = []
    widths = []
    for row in frame.sort_values("time").itertuples(index=False):
        start = (row.time - TARGET_PERIOD_START) / pd.Timedelta(minutes=1)
        end = min(start + duration_minutes, 1440)
        if end <= start:
            continue
        location = getattr(row, location_col)
        location = "Unmapped" if pd.isna(location) else str(location)
        segments.append([(start, y), (end, y)])
        colors.append(palette.get(location, "#b5b5b5"))
        widths.append(getattr(row, f"{role}_line_width"))
    return segments, colors, widths


def add_role_line(ax, frame, role, y, duration_minutes, palette):
    frame = frame.copy()
    frame[f"{role}_line_width"] = line_widths(frame[f"{role}_steps_5min"])
    segments, colors, widths = role_segments(frame, role, y, duration_minutes, palette)
    collection = LineCollection(
        segments,
        colors=colors,
        linewidths=widths,
        capstyle="round",
        joinstyle="round",
    )
    ax.add_collection(collection)


def add_activity_legend(ax):
    widths = [2.0, 6.0, 12.0]
    labels = ["lower steps", "medium steps", "higher steps"]
    handles = [
        plt.Line2D([0], [0], color="#333333", linewidth=width, label=label)
        for width, label in zip(widths, labels)
    ]
    legend = ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, -0.34),
        ncol=3,
        title="Line width: log-scaled 5min step count",
        frameon=True,
    )
    ax.add_artist(legend)


def add_location_legend(ax, palette):
    handles = [
        mpatches.Patch(color=color, label=label)
        for label, color in sorted(palette.items())
    ]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title="Estimated location",
        frameon=True,
    )


def location_handles(palette):
    return [
        mpatches.Patch(color=color, label=label)
        for label, color in sorted(palette.items())
    ]


def state_palette():
    return {STATE_LABELS[state]: STATE_COLORS[state] for state in STATE_ORDER}


def add_state_legend(ax, palette):
    order = [STATE_LABELS[state] for state in STATE_ORDER]
    handles = [
        mpatches.Patch(color=palette[label], label=label)
        for label in order
        if label in palette
    ]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title="Co-presence",
        frameon=True,
    )


def state_handles(palette):
    order = [STATE_LABELS[state] for state in STATE_ORDER]
    return [
        mpatches.Patch(color=palette[label], label=label)
        for label in order
        if label in palette
    ]


def format_axis(ax):
    ticks = np.arange(0, 1441, 120)
    ax.set_xlim(0, 1440)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{(12 + int(tick // 60)) % 24:02d}:00" for tick in ticks])
    ax.set_ylim(-0.8, 1.8)
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["SUBJECT", "STUDY_PARTNER"])
    ax.set_xlabel("Time in 12:00-to-12:00 period")
    ax.grid(axis="x", alpha=0.22)
    ax.grid(axis="y", alpha=0.15)


def format_copresence_axis(ax):
    ticks = np.arange(0, 1441, 120)
    ax.set_xlim(0, 1440)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{(12 + int(tick // 60)) % 24:02d}:00" for tick in ticks])
    ax.set_ylim(-0.8, 0.8)
    ax.set_yticks([0])
    ax.set_yticklabels(["Co-presence"])
    ax.set_xlabel("Time in 12:00-to-12:00 period")
    ax.grid(axis="x", alpha=0.22)
    ax.grid(axis="y", alpha=0.15)


def copresence_segments(frame, duration_minutes, palette):
    segments = []
    colors = []
    widths = []
    for row in frame.sort_values("time").itertuples(index=False):
        start = (row.time - TARGET_PERIOD_START) / pd.Timedelta(minutes=1)
        end = min(start + duration_minutes, 1440)
        if end <= start:
            continue
        label = "Both away/unmapped" if pd.isna(row.copresence_label) else str(row.copresence_label)
        segments.append([(start, 0), (end, 0)])
        colors.append(palette.get(label, "#b5b5b5"))
        widths.append(12.0)
    return segments, colors, widths


def plot_copresence_method(frame, method, palette):
    fig, ax = plt.subplots(figsize=(18, 3.6))
    segments, colors, widths = copresence_segments(
        frame,
        method["duration_minutes"],
        palette,
    )
    collection = LineCollection(
        segments,
        colors=colors,
        linewidths=widths,
        capstyle="round",
        joinstyle="round",
    )
    ax.add_collection(collection)
    format_copresence_axis(ax)
    ax.set_title(
        f"{TARGET_PERIOD_START:%Y-%m-%d %H:%M} to {TARGET_PERIOD_END:%Y-%m-%d %H:%M}: showing co-presence - {method['label']}",
        loc="left",
    )
    ax.text(
        0,
        1.06,
        "Colour shows estimated co-presence state.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
    )
    add_state_legend(ax, palette)
    fig.tight_layout()
    output = FIGURES_DIR / method["copresence_output"]
    fig.savefig(output, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_location_method(frame, method, palette):
    fig, ax = plt.subplots(figsize=(18, 4.8))
    add_role_line(
        ax,
        frame,
        "subject",
        1,
        method["duration_minutes"],
        palette,
    )
    add_role_line(
        ax,
        frame,
        "study_partner",
        0,
        method["duration_minutes"],
        palette,
    )
    format_axis(ax)
    ax.set_title(
        f"{TARGET_PERIOD_START:%Y-%m-%d %H:%M} to {TARGET_PERIOD_END:%Y-%m-%d %H:%M}: showing location calculation - {method['label']}",
        loc="left",
    )
    ax.text(
        0,
        1.04,
        "Colour shows estimated location; line width shows log-scaled 5min step count.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
    )
    add_activity_legend(ax)
    add_location_legend(ax, palette)
    fig.tight_layout()
    output = FIGURES_DIR / method["location_output"]
    fig.savefig(output, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return output


def add_copresence_line_to_axis(ax, frame, method, palette):
    segments, colors, widths = copresence_segments(
        frame,
        method["duration_minutes"],
        palette,
    )
    collection = LineCollection(
        segments,
        colors=colors,
        linewidths=11.0,
        capstyle="round",
        joinstyle="round",
    )
    ax.add_collection(collection)


def add_location_lines_to_axis(ax, frame, method, palette):
    add_role_line(
        ax,
        frame,
        "subject",
        1,
        method["duration_minutes"],
        palette,
    )
    add_role_line(
        ax,
        frame,
        "study_partner",
        0,
        method["duration_minutes"],
        palette,
    )


def format_combined_copresence_axis(ax):
    ticks = np.arange(0, 1441, 120)
    ax.set_xlim(0, 1440)
    ax.set_xticks(ticks)
    ax.tick_params(axis="x", labelbottom=False)
    ax.set_ylim(-0.55, 0.55)
    ax.set_yticks([0])
    ax.set_yticklabels(["Co-presence"])
    ax.grid(axis="x", alpha=0.18)
    ax.grid(axis="y", alpha=0.12)
    ax.set_title("Showing co-presence", loc="left", pad=12, fontsize=10)


def format_combined_location_axis(ax):
    ticks = np.arange(0, 1441, 120)
    ax.set_xlim(0, 1440)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{(12 + int(tick // 60)) % 24:02d}:00" for tick in ticks])
    ax.set_ylim(-0.65, 1.65)
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["SUBJECT", "STUDY_PARTNER"])
    ax.set_xlabel("Time in 12:00-to-12:00 period")
    ax.grid(axis="x", alpha=0.22)
    ax.grid(axis="y", alpha=0.15)
    ax.set_title("Showing location calculation", loc="left", pad=12, fontsize=10)


def add_combined_activity_legend(ax):
    handles = [
        plt.Line2D([0], [0], color="#333333", linewidth=width, label=label)
        for width, label in [
            (2.0, "lower steps"),
            (6.0, "medium steps"),
            (12.0, "higher steps"),
        ]
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=3,
        title="Location line width: log-scaled 5min step count",
        frameon=True,
    )


def plot_combined_method(frame, method, location_palette, copresence_palette):
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(18, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1.8], "hspace": 0.20},
    )
    add_copresence_line_to_axis(axes[0], frame, method, copresence_palette)
    add_location_lines_to_axis(axes[1], frame, method, location_palette)
    format_combined_copresence_axis(axes[0])
    format_combined_location_axis(axes[1])

    fig.suptitle(
        f"{TARGET_PERIOD_START:%Y-%m-%d %H:%M} to {TARGET_PERIOD_END:%Y-%m-%d %H:%M} - {method['label']}",
        fontsize=13,
        y=0.97,
    )
    fig.legend(
        handles=state_handles(copresence_palette),
        loc="upper left",
        bbox_to_anchor=(0.815, 0.80),
        title="Co-presence",
        frameon=True,
    )
    fig.legend(
        handles=location_handles(location_palette),
        loc="upper left",
        bbox_to_anchor=(0.815, 0.52),
        title="Estimated location",
        frameon=True,
    )
    add_combined_activity_legend(axes[1])
    fig.subplots_adjust(
        left=0.08,
        right=0.79,
        top=0.90,
        bottom=0.17,
        hspace=0.34,
    )

    output = FIGURES_DIR / method["combined_output"]
    fig.savefig(output, dpi=260)
    plt.close(fig)
    return output


def write_markdown(copresence_outputs, location_outputs):
    path = FIGURES_DIR / "X001_0615_single_day_location_activity_lines.md"
    lines = [
        "# Single-Period Line Figures",
        "",
        f"Period shown: `{TARGET_PERIOD_START}` to `{TARGET_PERIOD_END}`.",
        "",
        "These figures redraw the selected single-day timelines as continuous line segments rather than square markers.",
        "",
        "There are two groups: one showing co-presence, and one showing location calculation. For the location calculation group, colour shows estimated location and line width shows log-scaled 5-minute step count.",
        "",
        "## Showing co-presence",
        "",
    ]
    for method, output in zip(METHODS, copresence_outputs):
        lines.extend(
            [
                f"### {method['label']}",
                "",
                f"![{method['label']}]({output.name})",
                "",
            ]
        )
    lines.extend(
        [
            "## Showing location calculation",
            "",
            "The same activity signal is used for all five methods so the visual comparison focuses on how the location estimate changes across algorithms.",
            "",
        ]
    )
    for method, output in zip(METHODS, location_outputs):
        lines.extend(
            [
                f"### {method['label']}",
                "",
                f"![{method['label']}]({output.name})",
                "",
            ]
        )
    path.write_text("\n".join(lines))
    return path


def main():
    activity = load_activity_source()
    frames = {
        method["key"]: load_method_frame(method["key"], activity)
        for method in METHODS
    }
    palette = build_location_palette(frames.values())
    copresence_palette = state_palette()

    copresence_outputs = []
    location_outputs = []
    combined_outputs = []
    for method in METHODS:
        copresence_outputs.append(
            plot_copresence_method(
                frames[method["key"]],
                method,
                copresence_palette,
            )
        )
        location_outputs.append(plot_location_method(frames[method["key"]], method, palette))
        combined_outputs.append(
            plot_combined_method(
                frames[method["key"]],
                method,
                palette,
                copresence_palette,
            )
        )
    print("Saved single-day co-presence line figures:")
    for output in copresence_outputs:
        print(output)
    print("Saved single-day location/activity line figures:")
    for output in location_outputs:
        print(output)
    print("Saved combined co-presence/location line figures:")
    for output in combined_outputs:
        print(output)


if __name__ == "__main__":
    main()
