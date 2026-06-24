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
        "output": "X001_0617_multiday_aligned_4a_fixed5.png",
    },
    {
        "key": "4a_fixed10",
        "label": "4a fixed 10min RSSI",
        "duration_minutes": 10,
        "output": "X001_0617_multiday_aligned_4a_fixed10.png",
    },
    {
        "key": "4a_fixed30",
        "label": "4a fixed 30min RSSI",
        "duration_minutes": 30,
        "output": "X001_0617_multiday_aligned_4a_fixed30.png",
    },
    {
        "key": "4b_adaptive10",
        "label": "4b step-adaptive RSSI, threshold 10",
        "duration_minutes": 1,
        "output": "X001_0617_multiday_aligned_4b_adaptive10.png",
    },
    {
        "key": "4c_clustering",
        "label": "4c low-motion RSSI clustering",
        "duration_minutes": 30,
        "output": "X001_0617_multiday_aligned_4c_clustering.png",
    },
]


def read_time_csv(path):
    frame = pd.read_csv(path)
    frame["time"] = pd.to_datetime(frame["time"])
    return frame


def state_palette():
    return {STATE_LABELS[state]: STATE_COLORS[state] for state in STATE_ORDER}


def add_midday_period_columns(frame):
    output = frame.copy()
    output["period_start"] = (
        output["time"].sub(pd.Timedelta(hours=12)).dt.floor("D")
        + pd.Timedelta(hours=12)
    )
    output["period_end"] = output["period_start"] + pd.Timedelta(days=1)
    output["period_label"] = output["period_start"].dt.strftime("%Y-%m-%d noon")
    output["period_minute"] = (
        (output["time"] - output["period_start"]) / pd.Timedelta(minutes=1)
    )
    return output.loc[
        output["period_minute"].ge(0) & output["period_minute"].lt(1440)
    ].copy()


def load_activity_source():
    adaptive = read_time_csv(ADAPTIVE_TIMELINE_PATH)
    adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
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
    return pd.merge_asof(
        output,
        activity,
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(minutes=2),
    )


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
        fixed = add_activity(
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
        return add_midday_period_columns(fixed)

    if method_key == "4b_adaptive10":
        adaptive = read_time_csv(ADAPTIVE_TIMELINE_PATH)
        adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
        adaptive = adaptive.rename(
            columns={
                "subject_strongest_location": "subject_location",
                "study_partner_strongest_location": "study_partner_location",
            }
        )
        adaptive = adaptive[
            [
                "time",
                "subject_location",
                "study_partner_location",
                "copresence_label",
                "subject_steps_5min",
                "study_partner_steps_5min",
            ]
        ].copy()
        return add_midday_period_columns(adaptive)

    if method_key == "4c_clustering":
        cluster = read_time_csv(CLUSTER_TIMELINE_PATH)
        cluster = cluster.rename(
            columns={
                "subject_cluster_location": "subject_location",
                "study_partner_cluster_location": "study_partner_location",
            }
        )
        cluster = add_activity(
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
        return add_midday_period_columns(cluster)

    raise ValueError(f"Unknown method key: {method_key}")


def build_location_palette(frames):
    palette = dict(LOCATION_COLORS)
    values = set()
    cmap = plt.get_cmap("tab20")
    for frame in frames:
        values.update(frame["subject_location"].fillna("Unmapped").astype(str).unique())
        values.update(
            frame["study_partner_location"].fillna("Unmapped").astype(str).unique()
        )
    for value in sorted(values):
        if value not in palette:
            palette[value] = cmap(len(palette) % 20)
    return palette


def step_widths(values, upper):
    clean = pd.to_numeric(values, "coerce").fillna(0).clip(lower=0)
    scaled = np.log1p(clean)
    if pd.isna(upper) or upper <= 0:
        return np.full(len(clean), 2.5)
    return 1.8 + 7.8 * (scaled / upper).clip(upper=1)


def global_step_upper(activity):
    values = pd.concat(
        [
            activity["subject_steps_5min"],
            activity["study_partner_steps_5min"],
        ],
        ignore_index=True,
    )
    return np.log1p(pd.to_numeric(values, "coerce").fillna(0).clip(lower=0)).quantile(
        0.98
    )


def line_segments(frame, value_column, y, duration_minutes, palette, width_values):
    segments = []
    colors = []
    widths = []
    for row, width in zip(frame.sort_values("time").itertuples(index=False), width_values):
        start = float(row.period_minute)
        end = min(start + duration_minutes, 1440)
        if end <= start:
            continue
        value = getattr(row, value_column)
        label = "Unmapped" if pd.isna(value) else str(value)
        segments.append([(start, y), (end, y)])
        colors.append(palette.get(label, "#b5b5b5"))
        widths.append(width)
    return segments, colors, widths


def add_line_collection(ax, segments, colors, widths):
    if not segments:
        return
    collection = LineCollection(
        segments,
        colors=colors,
        linewidths=widths,
        capstyle="round",
        joinstyle="round",
    )
    ax.add_collection(collection)


def add_period_lines(
    ax,
    period_frame,
    y_base,
    duration_minutes,
    location_palette,
    copresence_palette,
    step_upper,
):
    copresence_width = np.full(len(period_frame), 8.0)
    segments, colors, widths = line_segments(
        period_frame,
        "copresence_label",
        y_base + 2.0,
        duration_minutes,
        copresence_palette,
        copresence_width,
    )
    add_line_collection(ax, segments, colors, widths)

    subject_widths = step_widths(period_frame["subject_steps_5min"], step_upper)
    segments, colors, widths = line_segments(
        period_frame,
        "subject_location",
        y_base + 1.0,
        duration_minutes,
        location_palette,
        subject_widths,
    )
    add_line_collection(ax, segments, colors, widths)

    partner_widths = step_widths(period_frame["study_partner_steps_5min"], step_upper)
    segments, colors, widths = line_segments(
        period_frame,
        "study_partner_location",
        y_base,
        duration_minutes,
        location_palette,
        partner_widths,
    )
    add_line_collection(ax, segments, colors, widths)


def add_legends(ax, location_palette, copresence_palette):
    location_handles = [
        mpatches.Patch(color=color, label=label)
        for label, color in sorted(location_palette.items())
    ]
    location_legend = ax.legend(
        handles=location_handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.58),
        title="Estimated location",
        frameon=True,
    )
    ax.add_artist(location_legend)

    copresence_order = [STATE_LABELS[state] for state in STATE_ORDER]
    copresence_handles = [
        mpatches.Patch(color=copresence_palette[label], label=label)
        for label in copresence_order
    ]
    ax.legend(
        handles=copresence_handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.18),
        title="Co-presence",
        frameon=True,
    )


def add_activity_width_legend(ax):
    handles = [
        plt.Line2D([0], [0], color="#333333", linewidth=width, label=label)
        for width, label in [
            (1.8, "lower steps"),
            (5.5, "medium steps"),
            (9.6, "higher steps"),
        ]
    ]
    legend = ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, -0.10),
        ncol=3,
        title="Location line width: log-scaled 5min step count",
        frameon=True,
    )
    ax.add_artist(legend)


def format_axis(ax, y_ticks, y_labels, title):
    ticks = np.arange(0, 1441, 120)
    tick_labels = [f"{(12 + int(tick // 60)) % 24:02d}:00" for tick in ticks]
    ax.set_xlim(0, 1440)
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels)
    ax.set_xlabel("Time in 12:00-to-12:00 period")
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_title(title, loc="left", pad=14)
    ax.grid(axis="x", alpha=0.22)
    ax.grid(axis="y", alpha=0.10)


def plot_method(frame, method, location_palette, copresence_palette, step_upper):
    periods = sorted(frame["period_start"].dropna().unique())
    row_gap = 3.7
    fig_height = max(6.0, 1.25 * len(periods) + 2.0)
    fig, ax = plt.subplots(figsize=(18, fig_height))
    y_ticks = []
    y_labels = []

    for idx, period_start in enumerate(periods):
        period = frame.loc[frame["period_start"].eq(period_start)].copy()
        y_base = (len(periods) - 1 - idx) * row_gap
        add_period_lines(
            ax,
            period,
            y_base,
            method["duration_minutes"],
            location_palette,
            copresence_palette,
            step_upper,
        )
        label = pd.Timestamp(period_start).strftime("%Y-%m-%d")
        y_ticks.extend([y_base + 2.0, y_base + 1.0, y_base])
        y_labels.extend(
            [
                f"{label} co-presence",
                f"{label} SUBJECT",
                f"{label} STUDY_PARTNER",
            ]
        )
        ax.axhline(y_base - 0.58, color="#dddddd", linewidth=0.8)

    ax.set_ylim(-0.85, (len(periods) - 1) * row_gap + 2.8)
    format_axis(
        ax,
        y_ticks,
        y_labels,
        f"Multi-day aligned timeline, 12:00-to-12:00 periods - {method['label']}",
    )
    add_legends(ax, location_palette, copresence_palette)
    add_activity_width_legend(ax)
    fig.tight_layout()
    output = FIGURES_DIR / method["output"]
    fig.savefig(output, dpi=230, bbox_inches="tight")
    plt.close(fig)
    return output


def grey_to_blue_diagnostic():
    adaptive = read_time_csv(ADAPTIVE_TIMELINE_PATH)
    adaptive = adaptive.loc[adaptive["threshold_steps"].eq(10)].copy()
    cluster = read_time_csv(CLUSTER_TIMELINE_PATH)

    adaptive_30 = (
        adaptive.set_index("time")
        .resample("30min")
        .agg(
            study_partner_strongest_location=(
                "study_partner_strongest_location",
                lambda values: values.mode().iat[0]
                if not values.mode().empty
                else "Unmapped",
            ),
            study_partner_total_rssi_samples=("study_partner_total_rssi_samples", "sum"),
        )
    )
    cluster_30 = cluster.set_index("time")[
        [
            "study_partner_cluster_location",
            "study_partner_has_rssi",
            "study_partner_rssi_strongest_location",
        ]
    ]
    merged = adaptive_30.join(cluster_30, how="inner")
    mask = (
        merged["study_partner_strongest_location"].isna()
        | merged["study_partner_strongest_location"].eq("Unmapped")
    ) & merged["study_partner_cluster_location"].eq("Bathroom")
    diagnostic = merged.loc[mask].reset_index()
    output = FIGURES_DIR / "X001_0617_grey_to_blue_diagnostic.csv"
    diagnostic.to_csv(output, index=False)
    return output, len(diagnostic)


def main():
    activity = load_activity_source()
    frames = {
        method["key"]: load_method_frame(method["key"], activity)
        for method in METHODS
    }
    location_palette = build_location_palette(frames.values())
    copresence_palette = state_palette()
    step_upper = global_step_upper(activity)

    outputs = []
    for method in METHODS:
        outputs.append(
            plot_method(
                frames[method["key"]],
                method,
                location_palette,
                copresence_palette,
                step_upper,
            )
        )

    diagnostic_path, diagnostic_count = grey_to_blue_diagnostic()

    print("Saved 0617 multi-day aligned figures:")
    for output in outputs:
        print(output)
    print(diagnostic_path)
    print(f"grey_to_blue_diagnostic_rows={diagnostic_count}")


if __name__ == "__main__":
    main()
