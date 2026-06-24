import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

from forthphase_multiday_aligned_timelines_0617 import (
    FIGURES_DIR,
    METHODS,
    add_midday_period_columns,
    build_location_palette,
    global_step_upper,
    load_activity_source,
    load_method_frame,
    state_palette,
    step_widths,
)
from forthphase_fixed_rssi_window_comparison import STATE_LABELS, STATE_ORDER


OUTPUTS = {
    "copresence": "X001_0623_algorithm_comparison_copresence.png",
    "subject": "X001_0623_algorithm_comparison_subject_location.png",
    "study_partner": "X001_0623_algorithm_comparison_study_partner_location.png",
}


def time_ticks():
    ticks = np.arange(0, 1441, 120)
    labels = [f"{(12 + int(tick // 60)) % 24:02d}:00" for tick in ticks]
    return ticks, labels


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


def segments_for_metric(frame, value_column, y, duration_minutes, palette, widths):
    segments = []
    colors = []
    line_widths = []
    for row, width in zip(frame.sort_values("time").itertuples(index=False), widths):
        start = float(row.period_minute)
        end = min(start + duration_minutes, 1440)
        if end <= start:
            continue
        value = getattr(row, value_column)
        label = "Unmapped" if pd.isna(value) else str(value)
        segments.append([(start, y), (end, y)])
        colors.append(palette.get(label, "#b5b5b5"))
        line_widths.append(width)
    return segments, colors, line_widths


def method_duration(method_key):
    for method in METHODS:
        if method["key"] == method_key:
            return method["duration_minutes"]
    raise ValueError(f"Unknown method key: {method_key}")


def method_label(method_key):
    for method in METHODS:
        if method["key"] == method_key:
            return method["label"]
    raise ValueError(f"Unknown method key: {method_key}")


def add_legend(ax, palette, title, handles_order=None):
    if handles_order is None:
        items = sorted(palette.items())
    else:
        items = [(label, palette[label]) for label in handles_order if label in palette]
    handles = [mpatches.Patch(color=color, label=label) for label, color in items]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title=title,
        frameon=True,
    )


def plot_comparison(frames, metric, palette, step_upper=None):
    periods = sorted(
        pd.concat([frame["period_start"] for frame in frames.values()])
        .dropna()
        .unique()
    )
    method_keys = [method["key"] for method in METHODS]
    row_gap = len(method_keys) + 1.3
    fig_height = max(8.0, len(periods) * 1.65 + 2.4)
    fig, ax = plt.subplots(figsize=(19, fig_height))

    y_ticks = []
    y_labels = []

    for period_idx, period_start in enumerate(periods):
        y_group_base = (len(periods) - 1 - period_idx) * row_gap
        for method_idx, method_key in enumerate(method_keys):
            y = y_group_base + (len(method_keys) - 1 - method_idx)
            period_frame = frames[method_key].loc[
                frames[method_key]["period_start"].eq(period_start)
            ].copy()
            if period_frame.empty:
                continue

            if metric == "copresence":
                widths = np.full(len(period_frame), 8.0)
                value_column = "copresence_label"
            elif metric == "subject":
                widths = step_widths(period_frame["subject_steps_5min"], step_upper)
                value_column = "subject_location"
            elif metric == "study_partner":
                widths = step_widths(
                    period_frame["study_partner_steps_5min"], step_upper
                )
                value_column = "study_partner_location"
            else:
                raise ValueError(f"Unknown metric: {metric}")

            segments, colors, line_widths = segments_for_metric(
                period_frame,
                value_column,
                y,
                method_duration(method_key),
                palette,
                widths,
            )
            add_line_collection(ax, segments, colors, line_widths)

            date_label = pd.Timestamp(period_start).strftime("%Y-%m-%d")
            y_ticks.append(y)
            y_labels.append(f"{date_label} {method_label(method_key)}")

        ax.axhline(y_group_base - 0.75, color="#dddddd", linewidth=0.8)

    ticks, tick_labels = time_ticks()
    ax.set_xlim(0, 1440)
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels)
    ax.set_xlabel("Time in 12:00-to-12:00 period")
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=8)
    ax.set_ylim(-1.1, (len(periods) - 1) * row_gap + len(method_keys) - 0.25)
    ax.grid(axis="x", alpha=0.22)
    ax.grid(axis="y", alpha=0.08)

    if metric == "copresence":
        title = "Algorithm comparison: estimated co-presence"
        legend_title = "Co-presence"
        order = [STATE_LABELS[state] for state in STATE_ORDER]
    elif metric == "subject":
        title = "Algorithm comparison: SUBJECT estimated location"
        legend_title = "Estimated location"
        order = None
    else:
        title = "Algorithm comparison: STUDY_PARTNER estimated location"
        legend_title = "Estimated location"
        order = None

    ax.set_title(title, loc="left", pad=16)
    add_legend(ax, palette, legend_title, order)

    fig.tight_layout()
    output = FIGURES_DIR / OUTPUTS[metric]
    fig.savefig(output, dpi=230, bbox_inches="tight")
    plt.close(fig)
    return output


def write_markdown(outputs):
    path = FIGURES_DIR / "X001_0623_algorithm_comparison_lines.md"
    lines = [
        "# Algorithm Comparison Line Figures",
        "",
        "## Showing co-presence",
        "",
        f"![Showing co-presence]({outputs['copresence'].name})",
        "",
        "## Showing location calculation: SUBJECT",
        "",
        f"![Showing location calculation: SUBJECT]({outputs['subject'].name})",
        "",
        "## Showing location calculation: STUDY_PARTNER",
        "",
        f"![Showing location calculation: STUDY_PARTNER]({outputs['study_partner'].name})",
        "",
    ]
    path.write_text("\n".join(lines))
    return path


def main():
    activity = load_activity_source()
    frames = {
        method["key"]: load_method_frame(method["key"], activity)
        for method in METHODS
    }
    location_palette = build_location_palette(frames.values())
    copresence_palette = state_palette()
    step_upper = global_step_upper(activity)

    outputs = {
        "copresence": plot_comparison(frames, "copresence", copresence_palette),
        "subject": plot_comparison(frames, "subject", location_palette, step_upper),
        "study_partner": plot_comparison(
            frames,
            "study_partner",
            location_palette,
            step_upper,
        ),
    }
    markdown = write_markdown(outputs)

    print("Saved algorithm comparison line figures:")
    for output in outputs.values():
        print(output)
    print(markdown)


if __name__ == "__main__":
    main()
