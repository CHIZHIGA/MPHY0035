"""Align EF-001 room-transition events with ACC variability for one sleep episode."""

from __future__ import annotations

import csv
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "Results" / "SeventhPhase" / "EF-001"
TIMELINE_PATH = RESULTS_DIR / "EF-001_low_motion_adaptive_rssi_timeline.csv"
EPISODE_PATH = RESULTS_DIR / "EF-001_episode_dominant_room_summary.csv"
SUMMARY_PATH = RESULTS_DIR / "EF-001_sleep_episode_transition_summary.csv"
PNG_PATH = RESULTS_DIR / "EF-001_acc_std_vs_raw_room_transitions_detail.png"
SVG_PATH = RESULTS_DIR / "EF-001_acc_std_vs_raw_room_transitions_detail.svg"

WINDOW_MINUTES = 5
LOW_MOTION_THRESHOLD = 0.023
PADDING_MINUTES = 30
LOCATION_COLORS = {
    "Living": "#df6483",
    "Bedroom": "#68be91",
    "Bathroom": "#dda0e8",
    "Kitchen": "#6654e8",
    "Office": "#a95be6",
}


def as_bool(value):
    return value.lower() == "true"


def load_timeline():
    rows = []
    with TIMELINE_PATH.open(newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "time": datetime.fromisoformat(raw["time"]),
                    "observed": as_bool(raw["observed"]),
                    "raw_location": raw["raw_location"],
                    "corrected_location": raw["corrected_location"],
                    "acc_std": float(raw["acc_magnitude_std_clean"]),
                    "low_motion": as_bool(raw["low_motion"]),
                }
            )
    return rows


def load_episodes():
    episodes = []
    with EPISODE_PATH.open(newline="") as handle:
        for raw in csv.DictReader(handle):
            episodes.append(
                {
                    "episode_id": int(raw["episode_id"]),
                    "start": datetime.fromisoformat(raw["start"]),
                    "end": datetime.fromisoformat(raw["end"]),
                    "duration_minutes": int(raw["duration_minutes"]),
                    "dominant_location": raw["dominant_location"],
                }
            )
    return episodes


def transition_events(rows, key, start, end):
    events = []
    previous_room = ""
    previous_time = None
    for row in rows:
        if not (start <= row["time"] < end):
            continue
        continuous = (
            previous_time is not None
            and row["time"] - previous_time == timedelta(minutes=WINDOW_MINUTES)
        )
        room = row[key] if row["observed"] else ""
        if continuous and previous_room and room and room != previous_room:
            events.append(
                {
                    "time": row["time"],
                    "from_room": previous_room,
                    "to_room": room,
                    "acc_std": row["acc_std"],
                    "low_motion": math.isfinite(row["acc_std"])
                    and row["acc_std"] <= LOW_MOTION_THRESHOLD,
                }
            )
        previous_room = room
        previous_time = row["time"]
    return events


def build_summary(rows, episodes):
    summaries = []
    for episode in episodes:
        raw_events = transition_events(
            rows, "raw_location", episode["start"], episode["end"]
        )
        corrected_events = transition_events(
            rows, "corrected_location", episode["start"], episode["end"]
        )
        segment = [
            row for row in rows if episode["start"] <= row["time"] < episode["end"]
        ]
        summaries.append(
            {
                **episode,
                "observed_windows": sum(row["observed"] for row in segment),
                "raw_transition_count": len(raw_events),
                "raw_low_motion_transition_count": sum(
                    event["low_motion"] for event in raw_events
                ),
                "raw_higher_motion_transition_count": sum(
                    not event["low_motion"] for event in raw_events
                ),
                "corrected_transition_count": len(corrected_events),
                "raw_events": raw_events,
                "corrected_events": corrected_events,
            }
        )
    return summaries


def write_summary(summaries):
    fields = [
        "episode_id",
        "start",
        "end",
        "duration_minutes",
        "dominant_location",
        "observed_windows",
        "raw_transition_count",
        "raw_low_motion_transition_count",
        "raw_higher_motion_transition_count",
        "corrected_transition_count",
    ]
    with SUMMARY_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)


def state_runs(rows, key):
    runs = []
    start = previous_time = None
    value = ""
    for row in rows:
        current = row[key] if row["observed"] else ""
        continuous = (
            previous_time is not None
            and row["time"] - previous_time == timedelta(minutes=WINDOW_MINUTES)
        )
        if current != value or not continuous:
            if start is not None and value:
                runs.append(
                    (start, previous_time + timedelta(minutes=WINDOW_MINUTES), value)
                )
            start = row["time"] if current else None
            value = current
        previous_time = row["time"]
    if start is not None and value:
        runs.append((start, previous_time + timedelta(minutes=WINDOW_MINUTES), value))
    return runs


def draw_room_bar(ax, rows, key, label):
    for start, end, room in state_runs(rows, key):
        ax.axvspan(start, end, color=LOCATION_COLORS[room], linewidth=0)
    for row in rows:
        if not row["observed"]:
            ax.axvspan(
                row["time"],
                row["time"] + timedelta(minutes=WINDOW_MINUTES),
                color="#4d4d4d",
                linewidth=0,
            )
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_ylabel(label, rotation=0, ha="right", va="center", labelpad=12)
    ax.grid(axis="x", alpha=0.18)


def plot_detail(rows, selected):
    view_start = selected["start"] - timedelta(minutes=PADDING_MINUTES)
    view_end = selected["end"] + timedelta(minutes=PADDING_MINUTES)
    view_rows = [row for row in rows if view_start <= row["time"] < view_end]

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(14, 6.6),
        sharex=True,
        gridspec_kw={"height_ratios": [2.8, 0.48, 0.48]},
    )
    acc_times = [row["time"] for row in view_rows]
    acc_std = [row["acc_std"] for row in view_rows]
    axes[0].plot(acc_times, acc_std, color="#252525", linewidth=0.9, label="5-min ACC magnitude SD")
    axes[0].axhspan(0, LOW_MOTION_THRESHOLD, color="#dbe9fa", alpha=0.75, label="Low-motion range")
    axes[0].axhline(
        LOW_MOTION_THRESHOLD,
        color="#d62728",
        linestyle="--",
        linewidth=1.2,
        label=f"Low-motion threshold = {LOW_MOTION_THRESHOLD:.3f}",
    )
    axes[0].axvspan(
        selected["start"],
        selected["end"],
        color="#244b9b",
        alpha=0.075,
        label="Selected main-sleep episode",
    )
    first_low = first_high = True
    for event in selected["raw_events"]:
        if event["low_motion"]:
            axes[0].axvline(
                event["time"],
                color="#c51b3a",
                linewidth=1.05,
                alpha=0.82,
                label="Raw room transition during low motion" if first_low else None,
            )
            first_low = False
        else:
            axes[0].axvline(
                event["time"],
                color="#e69522",
                linewidth=1.2,
                alpha=0.9,
                label="Raw room transition during higher motion" if first_high else None,
            )
            first_high = False
    axes[0].set_ylabel("ACC magnitude SD")
    axes[0].set_ylim(bottom=0)
    axes[0].grid(alpha=0.18)
    axes[0].legend(loc="upper right", fontsize=8, ncol=2)

    draw_room_bar(axes[1], view_rows, "raw_location", "Raw room")
    draw_room_bar(axes[2], view_rows, "corrected_location", "Corrected room")
    handles = [
        mpatches.Patch(color=color, label=room)
        for room, color in LOCATION_COLORS.items()
    ]
    handles.append(mpatches.Patch(color="#4d4d4d", label="RSSI missing"))
    axes[1].legend(
        handles=handles,
        ncol=6,
        fontsize=8,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.03),
    )
    axes[2].set_xlim(view_start, view_end)
    local_tz = view_start.tzinfo
    axes[2].xaxis.set_major_locator(mdates.HourLocator(interval=1, tz=local_tz))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M", tz=local_tz))
    axes[2].set_xlabel("Local time (GMT-7)")

    title = (
        f"EF-001 episode {selected['episode_id']}: raw room transitions aligned with ACC variability"
    )
    subtitle = (
        f"Objectively selected as the main-sleep episode with most raw transitions: "
        f"{selected['raw_transition_count']} total, "
        f"{selected['raw_low_motion_transition_count']} during low motion; "
        f"corrected transitions = {selected['corrected_transition_count']}"
    )
    fig.suptitle(title, fontsize=15, y=0.985)
    fig.text(0.5, 0.938, subtitle, ha="center", va="center", fontsize=9.5, color="#555555")
    fig.tight_layout(rect=(0.04, 0.03, 1, 0.91))
    fig.savefig(PNG_PATH, dpi=240, bbox_inches="tight")
    fig.savefig(SVG_PATH, bbox_inches="tight")
    plt.close(fig)


def main():
    rows = load_timeline()
    episodes = load_episodes()
    summaries = build_summary(rows, episodes)
    write_summary(summaries)
    selected = max(summaries, key=lambda item: item["raw_transition_count"])
    plot_detail(rows, selected)
    print(
        "selected episode",
        selected["episode_id"],
        "raw transitions",
        selected["raw_transition_count"],
        "low-motion transitions",
        selected["raw_low_motion_transition_count"],
        "corrected transitions",
        selected["corrected_transition_count"],
    )
    print(SUMMARY_PATH)
    print(PNG_PATH)
    print(SVG_PATH)


if __name__ == "__main__":
    main()
