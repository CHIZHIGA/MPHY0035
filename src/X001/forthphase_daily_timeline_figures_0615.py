import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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

DISAGREEMENT_ORDER = [
    "all agree",
    "4a vs 4b differ",
    "4a vs 4c differ",
    "4b vs 4c differ",
    "all differ",
]

DISAGREEMENT_COLORS = {
    "all agree": "#2ca02c",
    "4a vs 4b differ": "#1f77b4",
    "4a vs 4c differ": "#ff7f0e",
    "4b vs 4c differ": "#9467bd",
    "all differ": "#d62728",
}

METHODS = {
    "4a_fixed30": {
        "label": "4a fixed 30min RSSI",
        "duration_minutes": 30,
        "copresence_file": "X001_0615_daily_copresence_4a_fixed30.png",
        "location_file": "X001_0615_daily_locations_4a_fixed30.png",
    },
    "4b_adaptive10": {
        "label": "4b step-adaptive RSSI, threshold 10",
        "duration_minutes": 1,
        "copresence_file": "X001_0615_daily_copresence_4b_adaptive10.png",
        "location_file": "X001_0615_daily_locations_4b_adaptive10.png",
    },
    "4c_clustering": {
        "label": "4c low-motion RSSI clustering",
        "duration_minutes": 30,
        "copresence_file": "X001_0615_daily_copresence_4c_clustering.png",
        "location_file": "X001_0615_daily_locations_4c_clustering.png",
    },
}


def read_time_csv(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    return df


def add_day_columns(df):
    output = df.copy()
    output["date"] = output["time"].dt.date
    output["date_label"] = output["time"].dt.strftime("%Y-%m-%d")
    output["time_of_day_minutes"] = (
        output["time"].dt.hour * 60
        + output["time"].dt.minute
        + output["time"].dt.second / 60
    )
    return output


def load_4a_fixed30():
    df = read_time_csv(FIXED_TIMELINE_PATH)
    df = df.loc[df["window"].eq("30min")].copy()
    df = df.rename(
        columns={
            "subject_strongest_location": "subject_location",
            "study_partner_strongest_location": "study_partner_location",
        }
    )
    return add_day_columns(df)


def load_4b_adaptive10():
    df = read_time_csv(ADAPTIVE_TIMELINE_PATH)
    df = df.loc[df["threshold_steps"].eq(10)].copy()
    df = df.rename(
        columns={
            "subject_strongest_location": "subject_location",
            "study_partner_strongest_location": "study_partner_location",
        }
    )
    return add_day_columns(df)


def load_4c_clustering():
    df = read_time_csv(CLUSTER_TIMELINE_PATH)
    df = df.rename(
        columns={
            "subject_cluster_location": "subject_location",
            "study_partner_cluster_location": "study_partner_location",
        }
    )
    return add_day_columns(df)


def state_color_map():
    return {STATE_LABELS[state]: STATE_COLORS[state] for state in STATE_ORDER}


def build_location_palette(frames):
    palette = dict(LOCATION_COLORS)
    cmap = plt.get_cmap("tab20")
    values = set()
    for frame in frames:
        for column in ["subject_location", "study_partner_location"]:
            values.update(frame[column].fillna("Unmapped").astype(str).unique())
    for value in sorted(values):
        if value not in palette:
            palette[value] = cmap(len(palette) % 20)
    return palette


def add_timeline_segments(ax, df, value_column, y, height, duration_minutes, palette):
    size = 14 if duration_minutes <= 1 else 34 if duration_minutes <= 5 else 72
    for value, group in df.groupby(value_column, dropna=False):
        label = "Unmapped" if pd.isna(value) else str(value)
        ax.scatter(
            group["time_of_day_minutes"],
            np.full(len(group), y),
            s=size,
            marker="s",
            color=palette.get(label, "#b5b5b5"),
            linewidths=0,
            alpha=0.92,
        )


def format_daily_axis(ax):
    ax.set_xlim(0, 1440)
    ticks = np.arange(0, 1441, 240)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{int(tick // 60):02d}:00" for tick in ticks])
    ax.grid(axis="x", alpha=0.18)
    ax.set_xlabel("Time of day")


def legend_from_palette(ax, palette, order=None, title=None, ncol=1):
    labels = order if order is not None else sorted(palette)
    handles = [
        mpatches.Patch(color=palette[label], label=label)
        for label in labels
        if label in palette
    ]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title=title,
        ncol=ncol,
        frameon=True,
    )


def plot_daily_copresence(df, method_key):
    method = METHODS[method_key]
    dates = sorted(df["date_label"].unique())
    fig_height = max(4.2, 0.48 * len(dates) + 1.8)
    fig, ax = plt.subplots(figsize=(15, fig_height))
    palette = state_color_map()

    y_positions = {}
    for idx, date_label in enumerate(dates):
        y = len(dates) - idx
        y_positions[date_label] = y
        day = df.loc[df["date_label"].eq(date_label)]
        add_timeline_segments(
            ax,
            day,
            "copresence_label",
            y,
            0.72,
            method["duration_minutes"],
            palette,
        )

    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(y_positions.keys()))
    ax.set_title(
        f"Daily co-presence timeline: {method['label']}",
        loc="left",
    )
    format_daily_axis(ax)
    legend_from_palette(
        ax,
        palette,
        order=[STATE_LABELS[state] for state in STATE_ORDER],
        title="Co-presence",
    )
    fig.tight_layout()
    output = FIGURES_DIR / method["copresence_file"]
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_daily_locations(df, method_key, location_palette):
    method = METHODS[method_key]
    dates = sorted(df["date_label"].unique())
    fig_height = max(5.2, 0.84 * len(dates) + 1.8)
    fig, ax = plt.subplots(figsize=(15, fig_height))

    y_ticks = []
    y_labels = []
    for idx, date_label in enumerate(dates):
        base_y = (len(dates) - idx) * 2
        day = df.loc[df["date_label"].eq(date_label)]
        add_timeline_segments(
            ax,
            day,
            "subject_location",
            base_y + 0.25,
            0.45,
            method["duration_minutes"],
            location_palette,
        )
        add_timeline_segments(
            ax,
            day,
            "study_partner_location",
            base_y - 0.25,
            0.45,
            method["duration_minutes"],
            location_palette,
        )
        y_ticks.extend([base_y + 0.25, base_y - 0.25])
        y_labels.extend([f"{date_label} SUBJECT", f"{date_label} STUDY_PARTNER"])

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_title(
        f"Daily estimated location timeline: {method['label']}",
        loc="left",
    )
    format_daily_axis(ax)
    legend_from_palette(ax, location_palette, title="Estimated location", ncol=1)
    fig.tight_layout()
    output = FIGURES_DIR / method["location_file"]
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def activity_size(values):
    clean = pd.to_numeric(values, "coerce").fillna(0).clip(lower=0)
    scaled = np.log1p(clean)
    if scaled.max() <= 0:
        return np.full(len(clean), 10.0)
    return 8 + 34 * (scaled / scaled.quantile(0.98)).clip(upper=1)


def plot_daily_location_activity(df, location_palette):
    dates = sorted(df["date_label"].unique())
    fig_height = max(5.2, 0.84 * len(dates) + 2.0)
    fig, ax = plt.subplots(figsize=(15, fig_height))

    y_ticks = []
    y_labels = []
    for idx, date_label in enumerate(dates):
        base_y = (len(dates) - idx) * 2
        day = df.loc[df["date_label"].eq(date_label)].copy()
        for role_prefix, y_offset, label in [
            ("subject", 0.25, "SUBJECT"),
            ("study_partner", -0.25, "STUDY_PARTNER"),
        ]:
            location_column = f"{role_prefix}_location"
            step_column = f"{role_prefix}_steps_5min"
            colors = [
                location_palette.get(
                    "Unmapped" if pd.isna(value) else str(value),
                    "#b5b5b5",
                )
                for value in day[location_column]
            ]
            ax.scatter(
                day["time_of_day_minutes"],
                np.full(len(day), base_y + y_offset),
                c=colors,
                s=activity_size(day[step_column]),
                marker="s",
                linewidths=0,
                alpha=0.86,
            )
            y_ticks.append(base_y + y_offset)
            y_labels.append(f"{date_label} {label}")

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_title(
        "Daily estimated location with activity intensity: 4b step-adaptive RSSI",
        loc="left",
    )
    ax.text(
        0,
        0.99,
        "Marker size is log-scaled 5min step count.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
    )
    format_daily_axis(ax)
    legend_from_palette(ax, location_palette, title="Estimated location", ncol=1)
    fig.tight_layout()
    output = FIGURES_DIR / "X001_0615_daily_locations_activity_4b_adaptive10.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def coerce_location(value):
    if pd.isna(value):
        return "Unmapped"
    return str(value)


def disagreement_label(loc_4a, loc_4b, loc_4c):
    values = {
        "4a": coerce_location(loc_4a),
        "4b": coerce_location(loc_4b),
        "4c": coerce_location(loc_4c),
    }
    ab = values["4a"] == values["4b"]
    ac = values["4a"] == values["4c"]
    bc = values["4b"] == values["4c"]
    if ab and ac:
        return "all agree"
    if not ab and not ac and not bc:
        return "all differ"
    if not ab:
        return "4a vs 4b differ"
    if not ac:
        return "4a vs 4c differ"
    return "4b vs 4c differ"


def build_algorithm_alignment(fixed, adaptive, cluster):
    common_index = pd.date_range(
        max(
            fixed["time"].min().floor("30min"),
            adaptive["time"].min().floor("30min"),
            cluster["time"].min().floor("30min"),
        ),
        min(
            fixed["time"].max().floor("30min"),
            adaptive["time"].max().floor("30min"),
            cluster["time"].max().floor("30min"),
        ),
        freq="30min",
    )

    def align(frame, method, role):
        column = f"{role}_location"
        aligned = (
            frame[["time", column]]
            .drop_duplicates("time")
            .sort_values("time")
            .set_index("time")
        )
        aligned = aligned.reindex(common_index.floor("30min"))
        aligned.index = common_index
        return aligned[column].rename(f"{method}_{role}_location")

    rows = pd.DataFrame({"time": common_index})
    for role in ["subject", "study_partner"]:
        rows[f"4a_{role}_location"] = align(fixed, "4a", role).values
        rows[f"4b_{role}_location"] = align(adaptive, "4b", role).values
        rows[f"4c_{role}_location"] = align(cluster, "4c", role).values
        rows[f"{role}_disagreement_label"] = rows.apply(
            lambda row: disagreement_label(
                row[f"4a_{role}_location"],
                row[f"4b_{role}_location"],
                row[f"4c_{role}_location"],
            ),
            axis=1,
        )
    return add_day_columns(rows)


def plot_daily_disagreement(alignment, role):
    label_column = f"{role}_disagreement_label"
    dates = sorted(alignment["date_label"].unique())
    fig_height = max(4.2, 0.48 * len(dates) + 1.8)
    fig, ax = plt.subplots(figsize=(15, fig_height))

    y_positions = {}
    for idx, date_label in enumerate(dates):
        y = len(dates) - idx
        y_positions[date_label] = y
        day = alignment.loc[alignment["date_label"].eq(date_label)]
        add_timeline_segments(
            ax,
            day,
            label_column,
            y,
            0.72,
            30,
            DISAGREEMENT_COLORS,
        )

    role_label = "SUBJECT" if role == "subject" else "STUDY_PARTNER"
    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(y_positions.keys()))
    ax.set_title(
        f"Daily algorithm agreement/difference timeline: {role_label}",
        loc="left",
    )
    format_daily_axis(ax)
    legend_from_palette(
        ax,
        DISAGREEMENT_COLORS,
        order=DISAGREEMENT_ORDER,
        title="Algorithm relation",
    )
    fig.tight_layout()
    output = FIGURES_DIR / (
        f"X001_0615_daily_algorithm_disagreement_{role}.png"
    )
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_daily_disagreement_combined(alignment):
    dates = sorted(alignment["date_label"].unique())
    fig_height = max(5.2, 0.84 * len(dates) + 1.8)
    fig, ax = plt.subplots(figsize=(15, fig_height))

    y_ticks = []
    y_labels = []
    for idx, date_label in enumerate(dates):
        base_y = (len(dates) - idx) * 2
        day = alignment.loc[alignment["date_label"].eq(date_label)]
        add_timeline_segments(
            ax,
            day,
            "subject_disagreement_label",
            base_y + 0.25,
            0.45,
            30,
            DISAGREEMENT_COLORS,
        )
        add_timeline_segments(
            ax,
            day,
            "study_partner_disagreement_label",
            base_y - 0.25,
            0.45,
            30,
            DISAGREEMENT_COLORS,
        )
        y_ticks.extend([base_y + 0.25, base_y - 0.25])
        y_labels.extend([f"{date_label} SUBJECT", f"{date_label} STUDY_PARTNER"])

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_title(
        "Daily algorithm agreement/difference timeline: SUBJECT and STUDY_PARTNER",
        loc="left",
    )
    format_daily_axis(ax)
    legend_from_palette(
        ax,
        DISAGREEMENT_COLORS,
        order=DISAGREEMENT_ORDER,
        title="Algorithm relation",
    )
    fig.tight_layout()
    output = FIGURES_DIR / "X001_0615_daily_algorithm_disagreement.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def build_difference_summary(alignment):
    rows = []
    total_hours = len(alignment) * 0.5
    for role in ["subject", "study_partner"]:
        role_label = "SUBJECT" if role == "subject" else "STUDY_PARTNER"
        for left, right in [("4a", "4b"), ("4a", "4c"), ("4b", "4c")]:
            left_col = f"{left}_{role}_location"
            right_col = f"{right}_{role}_location"
            agreement = (
                alignment[left_col].map(coerce_location)
                == alignment[right_col].map(coerce_location)
            )
            agree_hours = agreement.sum() * 0.5
            differ_hours = (~agreement).sum() * 0.5
            rows.append(
                {
                    "role": role_label,
                    "method_pair": f"{left} vs {right}",
                    "agree_hours": agree_hours,
                    "differ_hours": differ_hours,
                    "agree_fraction": agree_hours / total_hours,
                    "differ_fraction": differ_hours / total_hours,
                    "total_hours": total_hours,
                }
            )
    return pd.DataFrame(rows)


def plot_difference_summary(summary):
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    labels = [
        f"{row.role}\n{row.method_pair}"
        for row in summary.itertuples(index=False)
    ]
    x = np.arange(len(summary))
    ax.bar(
        x,
        summary["agree_fraction"],
        label="Agreement",
        color="#2ca02c",
    )
    ax.bar(
        x,
        summary["differ_fraction"],
        bottom=summary["agree_fraction"],
        label="Difference",
        color="#d62728",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction of comparable 30min windows")
    ax.set_title("Algorithm agreement/difference summary", loc="left")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    output = FIGURES_DIR / "X001_0615_algorithm_difference_summary.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output


def write_readme(outputs, summary_path):
    readme = FIGURES_DIR / "README_0615_Figures.md"
    lines = [
        "# Figures 0615",
        "",
        "These figures respond to Derek's 2026-06-15 suggestion to inspect the Home_X001 timeline one day at a time.",
        "",
        "The figures are descriptive visualisations of RSSI-derived estimates. X001 has no independent reference labels, so these figures use agreement/difference language rather than reference-based performance language.",
        "",
        "## Outputs",
        "",
    ]
    for output in outputs:
        lines.append(f"* `{output.name}`")
    lines.extend(
        [
            f"* `{summary_path.name}`",
            "",
            "## Figure Groups",
            "",
            "* Daily co-presence timelines: one line per day showing together/apart states.",
            "* Daily location timelines: two lines per day, one for SUBJECT and one for STUDY_PARTNER.",
            "* Daily location + activity timeline: 4b location estimates with marker size modulated by 5-minute step count.",
            "* Algorithm disagreement timelines: one line per day showing where 4a, 4b, and 4c give the same or different estimated locations.",
            "* Algorithm difference summary: pairwise agreement/difference between 4a, 4b, and 4c.",
        ]
    )
    readme.write_text("\n".join(lines) + "\n")
    return readme


def main():
    fixed = load_4a_fixed30()
    adaptive = load_4b_adaptive10()
    cluster = load_4c_clustering()
    location_palette = build_location_palette([fixed, adaptive, cluster])

    outputs = []
    for key, frame in [
        ("4a_fixed30", fixed),
        ("4b_adaptive10", adaptive),
        ("4c_clustering", cluster),
    ]:
        outputs.append(plot_daily_copresence(frame, key))
        outputs.append(plot_daily_locations(frame, key, location_palette))

    outputs.append(plot_daily_location_activity(adaptive, location_palette))

    alignment = build_algorithm_alignment(fixed, adaptive, cluster)
    outputs.append(plot_daily_disagreement(alignment, "subject"))
    outputs.append(plot_daily_disagreement(alignment, "study_partner"))
    outputs.append(plot_daily_disagreement_combined(alignment))

    summary = build_difference_summary(alignment)
    summary_path = FIGURES_DIR / "X001_0615_algorithm_difference_summary.csv"
    summary.to_csv(summary_path, index=False)
    outputs.append(plot_difference_summary(summary))
    readme = write_readme(outputs, summary_path)

    print("Saved 0615 figures:")
    for output in outputs:
        print(output)
    print(summary_path)
    print(readme)


if __name__ == "__main__":
    main()
