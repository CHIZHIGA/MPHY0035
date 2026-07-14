"""Compact report-facing plots for unified pipeline outputs."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap


ROOM_COLORS = {
    "Living": "#df6483",
    "Bedroom": "#68be91",
    "Bathroom": "#d794e8",
    "Kitchen": "#6256e8",
    "Office": "#a65ae5",
    "Dining": "#e8a66a",
    "Toilet": "#9c755f",
    "Stairs": "#56b4e9",
    "Out": "#8c8c8c",
    "Unknown": "#d9d9d9",
    "Missing": "#ffffff",
}


def _stable_color(label: str) -> str:
    if label in ROOM_COLORS:
        return ROOM_COLORS[label]
    palette = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#b279a2", "#ff9da6", "#9d755d"]
    return palette[sum(ord(char) for char in label) % len(palette)]


def _categorical_bar(ax, times: pd.DatetimeIndex, values: pd.Series, color_map: dict[str, str], label: str):
    labels = ["Missing" if pd.isna(value) else str(value) for value in values]
    categories = list(dict.fromkeys(labels))
    code = {item: index for index, item in enumerate(categories)}
    data = np.array([[code[item] for item in labels]])
    cmap = ListedColormap([color_map.get(item, _stable_color(item)) for item in categories])
    start = mdates.date2num(times[0].to_pydatetime())
    end = mdates.date2num((times[-1] + pd.Timedelta(minutes=5)).to_pydatetime())
    ax.imshow(data, aspect="auto", interpolation="nearest", extent=[start, end, 0, 1], cmap=cmap, vmin=-0.5, vmax=len(categories) - 0.5)
    ax.set_yticks([0.5])
    ax.set_yticklabels([label])
    ax.set_ylim(0, 1)
    return categories


def plot_timeline(timeline: pd.DataFrame, timezone: str, title: str, output: Path) -> None:
    if timeline.empty:
        return
    local = timeline.index.tz_convert(timezone)
    fig, axes = plt.subplots(5, 1, figsize=(16, 7.4), sharex=True, gridspec_kw={"height_ratios": [1, 1, 0.34, 0.34, 0.34], "hspace": 0.14})
    raw_categories = _categorical_bar(axes[0], local, timeline["raw_room"], ROOM_COLORS, "Raw room")
    corrected_categories = _categorical_bar(axes[1], local, timeline["corrected_room"], ROOM_COLORS, "Corrected room")
    occupancy_colors = {"indoor_observed": "#78c6a3", "indoor_inferred_sleep": "#2a9d8f", "probable_away": "#d97706", "confirmed_away": "#a64b00", "unknown": "#cfcfcf", "Missing": "#ffffff"}
    occupancy_categories = _categorical_bar(axes[2], local, timeline["occupancy_state"], occupancy_colors, "Occupancy")
    state_colors = {"main_sleep": "#2f5aa5", "awake": "#efefef", "away": "#d97706", "sleep_unresolved": "#8eb6e9", "movement_unresolved": "#bdbdbd", "Missing": "#ffffff"}
    behaviour_categories = _categorical_bar(axes[3], local, timeline["behaviour_state"], state_colors, "Behaviour")
    movement_colors = {"Missing": "#ffffff"}
    movement_values = timeline["movement_state"].map(lambda value: f"State {int(value)}" if pd.notna(value) else "Missing")
    movement_states = sorted(state for state in movement_values.unique() if state != "Missing")
    for state, color in zip(movement_states, ["#d6e9ff", "#8bbcf0", "#4f87d7", "#1f4f99"]):
        movement_colors[state] = color
    movement_categories = _categorical_bar(axes[4], local, movement_values, movement_colors, "Movement")
    axes[-1].xaxis_date()
    locator = mdates.AutoDateLocator(minticks=5, maxticks=14)
    axes[-1].xaxis.set_major_locator(locator)
    axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axes[-1].set_xlabel(f"Local time ({timezone})")
    for ax in axes:
        ax.grid(axis="x", alpha=0.18)
    rooms = list(dict.fromkeys(raw_categories + corrected_categories))
    handles = [mpatches.Patch(color=ROOM_COLORS.get(room, _stable_color(room)), label=room) for room in rooms]
    axes[0].legend(handles=handles, ncol=min(7, len(handles)), loc="upper center", bbox_to_anchor=(0.5, 1.42), fontsize=8)
    axes[2].legend(
        handles=[mpatches.Patch(color=occupancy_colors.get(item, _stable_color(item)), label=item.replace("_", " ")) for item in occupancy_categories],
        ncol=min(5, len(occupancy_categories)), loc="upper right", fontsize=7,
    )
    axes[3].legend(
        handles=[mpatches.Patch(color=state_colors.get(item, _stable_color(item)), label=item.replace("_", " ")) for item in behaviour_categories],
        ncol=min(5, len(behaviour_categories)), loc="upper right", fontsize=7,
    )
    axes[4].legend(
        handles=[mpatches.Patch(color=movement_colors.get(item, _stable_color(item)), label=item) for item in movement_categories],
        ncol=min(5, len(movement_categories)), loc="upper right", fontsize=7,
    )
    fig.suptitle(title, y=1.01)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_clustering(timeline: pd.DataFrame, episodes: pd.DataFrame, timezone: str, title: str, output: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 7), gridspec_kw={"height_ratios": [1.4, 1]})
    local = timeline.index.tz_convert(timezone)
    axes[0].plot(local, timeline["movement_value"], color="#3f3f3f", linewidth=0.65)
    low = timeline["low_motion"].fillna(False)
    axes[0].scatter(local[low], timeline.loc[low, "movement_value"], s=4, color="#4f87d7", label="Lowest movement cluster")
    if timeline["low_motion_threshold"].notna().any():
        axes[0].axhline(timeline["low_motion_threshold"].dropna().iloc[0], color="#d62728", linestyle="--", label="Low-motion boundary")
    axes[0].set_ylabel("Movement feature")
    axes[0].legend(loc="upper right")
    if not episodes.empty:
        starts = episodes["start"].dt.tz_convert(timezone)
        colors = np.where(episodes["main_sleep"], "#2f5aa5", "#aaaaaa")
        axes[1].scatter(starts, episodes["duration_minutes"] / 60, c=colors, s=42)
        axes[1].legend(
            handles=[
                mpatches.Patch(color="#2f5aa5", label="Selected main-sleep cluster"),
                mpatches.Patch(color="#aaaaaa", label="Other low-motion episode"),
            ],
            loc="upper right",
        )
    axes[1].set_ylabel("Episode duration (hours)")
    axes[1].set_xlabel(f"Candidate start ({timezone})")
    axes[1].grid(alpha=0.2)
    axes[0].grid(alpha=0.2)
    fig.suptitle(title)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_confusion(confusion: pd.DataFrame, output: Path) -> None:
    if confusion.empty:
        return
    methods = list(confusion["method"].unique())
    fig, axes = plt.subplots(1, len(methods), figsize=(6 * len(methods), 5), squeeze=False)
    for ax, method in zip(axes[0], methods):
        data = confusion.loc[confusion["method"].eq(method)]
        matrix = data.pivot(index="reference_room", columns="predicted_room", values="window_count").fillna(0)
        image = ax.imshow(matrix, cmap="Blues")
        ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(matrix.index)), matrix.index)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Reference")
        ax.set_title(method)
        fig.colorbar(image, ax=ax, shrink=0.75)
    fig.suptitle("Agreement with existing reference annotations")
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
