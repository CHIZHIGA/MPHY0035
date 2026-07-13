"""Cluster EF-002 all-day low-motion episodes and assess RSSI gap support."""

from __future__ import annotations

import csv
import math
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "Results/SeventhPhase/EF-002"
FEATURES_PATH = RESULTS_DIR / "EF-002_acc_rssi_5min_features.csv"
EPISODES_PATH = RESULTS_DIR / "EF-002_main_sleep_episode_summary.csv"
GAPS_PATH = RESULTS_DIR / "EF-002_sleep_episode_rssi_gap_support.csv"
METRICS_PATH = RESULTS_DIR / "EF-002_sleep_episode_rssi_gap_metrics.csv"
CLUSTER_PLOT_PATH = RESULTS_DIR / "EF-002_all_day_low_motion_episode_clusters.png"
SUPPORT_PLOT_PATH = RESULTS_DIR / "EF-002_sleep_episode_rssi_gap_support.png"
CORRECTED_TIMELINE_PATH = RESULTS_DIR / "EF-002_bedroom_supported_corrected_timeline.csv"
CORRECTION_METRICS_PATH = RESULTS_DIR / "EF-002_bedroom_supported_correction_metrics.csv"
COMPARE_PLOT_PATH = RESULTS_DIR / "EF-002_raw_vs_bedroom_supported_corrected_rssi.png"
DAILY_COMPARE_PLOT_PATH = RESULTS_DIR / "EF-002_daily_raw_vs_bedroom_supported_corrected_rssi.png"

WINDOW_MINUTES = 5
MAX_MOTION_INTERRUPTION_MINUTES = 15
MIN_CANDIDATE_MINUTES = 60
N_DURATION_CLUSTERS = 3
CONTEXT_MINUTES = 30
STABLE_ROOM_SHARE = 2 / 3
LOCATION_COLORS = {
    "Living": "#df6483", "Bedroom": "#08c991", "Bathroom": "#e8a0e8",
    "Kitchen": "#6256e8", "Office": "#a65ae5",
}


def load_rows():
    rows = []
    with FEATURES_PATH.open(newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "time": datetime.fromisoformat(raw["time"]),
                    "low_motion": raw["low_motion"] == "True",
                    "rssi_observed": raw["rssi_observed"] == "True",
                    "room": raw["raw_strongest_location"],
                    "beacon": raw["raw_strongest_beacon"],
                }
            )
    return rows


def candidate_episodes(rows):
    lows = [row for row in rows if row["low_motion"]]
    bounds = []
    start = last = None
    maximum_separation = timedelta(
        minutes=MAX_MOTION_INTERRUPTION_MINUTES + WINDOW_MINUTES
    )
    for row in lows:
        if start is None or row["time"] - last > maximum_separation:
            if start is not None:
                bounds.append((start, last + timedelta(minutes=WINDOW_MINUTES)))
            start = row["time"]
        last = row["time"]
    if start is not None:
        bounds.append((start, last + timedelta(minutes=WINDOW_MINUTES)))
    candidates = []
    for start, end in bounds:
        segment = [row for row in rows if start <= row["time"] < end]
        duration = int((end - start).total_seconds() / 60)
        if duration < MIN_CANDIDATE_MINUTES:
            continue
        candidates.append(
            {
                "start": start,
                "end": end,
                "duration_minutes": duration,
                "low_motion_share": sum(row["low_motion"] for row in segment) / len(segment),
                "rows": segment,
            }
        )
    return candidates


def cluster_durations(candidates):
    values = np.log(np.array([item["duration_minutes"] for item in candidates]))
    centers = np.quantile(values, np.linspace(0.1, 0.9, N_DURATION_CLUSTERS))
    for _ in range(200):
        labels = np.argmin(np.abs(values[:, None] - centers), axis=1)
        updated = np.array([values[labels == index].mean() for index in range(N_DURATION_CLUSTERS)])
        if np.max(np.abs(updated - centers)) < 1e-12:
            break
        centers = updated
    order = np.argsort(centers)
    remap = np.empty(N_DURATION_CLUSTERS, dtype=int)
    remap[order] = np.arange(N_DURATION_CLUSTERS)
    labels = remap[labels]
    centers = centers[order]
    boundaries = np.exp((centers[:-1] + centers[1:]) / 2)
    for item, label in zip(candidates, labels):
        item["duration_cluster"] = int(label + 1)
    return np.exp(centers), boundaries


def dominant_room(observed):
    counts = Counter(row["room"] for row in observed if row["room"])
    if not counts:
        return "", 0, math.nan
    room, count = counts.most_common(1)[0]
    return room, count, count / sum(counts.values())


def build_main_episodes(candidates):
    selected = []
    for candidate in candidates:
        if candidate["duration_cluster"] != N_DURATION_CLUSTERS:
            continue
        observed = [row for row in candidate["rows"] if row["rssi_observed"]]
        room, count, share = dominant_room(observed)
        candidate.update(
            {
                "episode_id": len(selected) + 1,
                "observed_windows": len(observed),
                "missing_windows": len(candidate["rows"]) - len(observed),
                "dominant_room": room,
                "dominant_room_count": count,
                "dominant_room_share": share,
            }
        )
        selected.append(candidate)
    return selected


def context_summary(context):
    observed = [row for row in context if row["rssi_observed"]]
    counts = Counter(row["room"] for row in observed)
    room, count = counts.most_common(1)[0] if counts else ("", 0)
    return {
        "observed": len(observed),
        "dominant_room": room,
        "dominant_share": count / len(observed) if observed else math.nan,
        "bedroom_share": counts.get("Bedroom", 0) / len(observed) if observed else math.nan,
    }


def analyse_gaps(episodes, all_rows):
    gaps = []
    for episode in episodes:
        missing = [row for row in episode["rows"] if not row["rssi_observed"]]
        runs = []
        start = last = None
        for row in missing:
            if start is None or row["time"] - last != timedelta(minutes=WINDOW_MINUTES):
                if start is not None:
                    runs.append((start, last + timedelta(minutes=WINDOW_MINUTES)))
                start = row["time"]
            last = row["time"]
        if start is not None:
            runs.append((start, last + timedelta(minutes=WINDOW_MINUTES)))
        for start, end in runs:
            before = context_summary(
                [row for row in all_rows if start - timedelta(minutes=CONTEXT_MINUTES) <= row["time"] < start]
            )
            after = context_summary(
                [row for row in all_rows if end <= row["time"] < end + timedelta(minutes=CONTEXT_MINUTES)]
            )
            if (
                before["observed"] >= 1
                and after["observed"] >= 1
                and before["dominant_room"] == "Bedroom"
                and after["dominant_room"] == "Bedroom"
                and before["bedroom_share"] >= STABLE_ROOM_SHARE
                and after["bedroom_share"] >= STABLE_ROOM_SHARE
            ):
                support = "bedroom_supported"
            else:
                support = "unsupported_or_conflicting"
            gaps.append(
                {
                    "gap_id": len(gaps) + 1,
                    "episode_id": episode["episode_id"],
                    "start": start,
                    "end": end,
                    "duration_minutes": int((end - start).total_seconds() / 60),
                    "support_class": support,
                    "before_observed_windows": before["observed"],
                    "before_dominant_room": before["dominant_room"],
                    "before_dominant_share": before["dominant_share"],
                    "before_bedroom_share": before["bedroom_share"],
                    "after_observed_windows": after["observed"],
                    "after_dominant_room": after["dominant_room"],
                    "after_dominant_share": after["dominant_share"],
                    "after_bedroom_share": after["bedroom_share"],
                }
            )
    return gaps


def write_outputs(episodes, gaps, centers, boundaries):
    episode_fields = [
        "episode_id", "start", "end", "duration_minutes", "low_motion_share",
        "observed_windows", "missing_windows", "dominant_room",
        "dominant_room_count", "dominant_room_share", "duration_cluster",
    ]
    with EPISODES_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=episode_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(episodes)
    gap_fields = [key for key in gaps[0]] if gaps else ["gap_id"]
    with GAPS_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=gap_fields)
        writer.writeheader(); writer.writerows(gaps)
    class_counts = Counter(gap["support_class"] for gap in gaps)
    with METRICS_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerow(["candidate_episode_count", sum(1 for _ in candidates_global)])
        writer.writerow(["main_sleep_episode_count", len(episodes)])
        for index, center in enumerate(centers, 1): writer.writerow([f"duration_cluster_{index}_center_minutes", center])
        for index, boundary in enumerate(boundaries, 1): writer.writerow([f"duration_boundary_{index}_minutes", boundary])
        writer.writerow(["missing_runs_in_main_sleep", len(gaps)])
        writer.writerow(["missing_minutes_in_main_sleep", sum(gap["duration_minutes"] for gap in gaps)])
        for name, count in sorted(class_counts.items()): writer.writerow([f"gap_runs_{name}", count])
        for name in class_counts:
            writer.writerow([f"gap_minutes_{name}", sum(g["duration_minutes"] for g in gaps if g["support_class"] == name)])


def plot_clusters(candidates, centers, boundaries):
    colors = ["#aaaaaa", "#e59a42", "#244b9b"]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    for cluster in range(1, 4):
        subset = [item for item in candidates if item["duration_cluster"] == cluster]
        ax.scatter([item["start"] for item in subset], [item["duration_minutes"] / 60 for item in subset], s=45, color=colors[cluster - 1], label=f"Cluster {cluster}: centre {centers[cluster - 1]:.0f} min")
    ax.axhline(boundaries[-1] / 60, color="#8b1a8b", ls="--", label=f"Main-sleep boundary {boundaries[-1]:.0f} min")
    ax.set(title="EF-002 all-day low-motion episode duration clustering", xlabel="Candidate start time (GMT-5)", ylabel="Duration (hours)")
    ax.xaxis.set_major_locator(mdates.DayLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(alpha=.2); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(CLUSTER_PLOT_PATH, dpi=220); plt.close(fig)


def plot_gap_support(rows, episodes, gaps):
    fig, axes = plt.subplots(3, 1, figsize=(15, 5.5), sharex=True, gridspec_kw={"height_ratios": [1, .24, .24]})
    for row in rows:
        if row["rssi_observed"]:
            axes[0].axvspan(row["time"], row["time"] + timedelta(minutes=5), color=LOCATION_COLORS[row["room"]], lw=0)
    missing_runs = []
    start = last = None
    for row in [item for item in rows if not item["rssi_observed"]]:
        if start is None or row["time"] - last != timedelta(minutes=WINDOW_MINUTES):
            if start is not None:
                missing_runs.append((start, last + timedelta(minutes=WINDOW_MINUTES)))
            start = row["time"]
        last = row["time"]
    if start is not None:
        missing_runs.append((start, last + timedelta(minutes=WINDOW_MINUTES)))
    for start, end in missing_runs:
        axes[0].axvspan(start, end, color="#4d4d4d", lw=0)
        if (end - start).total_seconds() / 60 <= 10:
            axes[0].axvline(
                start + (end - start) / 2,
                color="#4d4d4d",
                linewidth=1.6,
            )
    axes[0].set_ylim(0,1); axes[0].set_yticks([]); axes[0].set_ylabel("Raw room", rotation=0, ha="right")
    for episode in episodes:
        axes[1].axvspan(episode["start"], episode["end"], color="#244b9b", lw=0)
    axes[1].set_ylim(0,1); axes[1].set_yticks([]); axes[1].set_ylabel("Main sleep", rotation=0, ha="right")
    support_colors = {
        "bedroom_supported": "#1b9e77",
        "unsupported_or_conflicting": "#d95f02",
    }
    for gap in gaps:
        axes[2].axvspan(gap["start"], gap["end"], color=support_colors[gap["support_class"]], lw=0)
        # A 5-minute span is sub-pixel in the full 12-day figure. Add a
        # minimum-width centre marker for short events without changing their
        # stored start/end time or plotted temporal position.
        if gap["duration_minutes"] <= 10:
            midpoint = gap["start"] + (gap["end"] - gap["start"]) / 2
            axes[2].axvline(
                midpoint,
                color=support_colors[gap["support_class"]],
                linewidth=1.6,
                alpha=1.0,
            )
    axes[2].set_ylim(0,1); axes[2].set_yticks([]); axes[2].set_ylabel("Main-sleep\nRSSI gaps", rotation=0, ha="right", va="center")
    axes[2].set_xlabel("Local time (GMT-5)"); axes[2].xaxis.set_major_locator(mdates.AutoDateLocator()); axes[2].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[2].xaxis.get_major_locator()))
    handles=[mpatches.Patch(color=c,label=k.replace('_',' ')) for k,c in support_colors.items()]
    handles.append(mpatches.Patch(color="#4d4d4d", label="raw RSSI missing (top row)"))
    axes[2].legend(handles=handles,ncol=5,fontsize=7,loc="upper center",bbox_to_anchor=(.5,-.5))
    fig.suptitle("EF-002 main-sleep episodes and RSSI-gap context support"); fig.tight_layout(); fig.savefig(SUPPORT_PLOT_PATH,dpi=220,bbox_inches="tight"); plt.close(fig)


def build_corrected_timeline(rows, episodes, gaps):
    episode_by_time = {}
    for episode in episodes:
        for row in episode["rows"]:
            episode_by_time[row["time"]] = episode["episode_id"]
    supported_times = set()
    for gap in gaps:
        if gap["support_class"] != "bedroom_supported":
            continue
        timestamp = gap["start"]
        while timestamp < gap["end"]:
            supported_times.add(timestamp)
            timestamp += timedelta(minutes=WINDOW_MINUTES)
    corrected = []
    for row in rows:
        if row["rssi_observed"]:
            corrected_room = row["room"]
            source = "raw_strongest_rssi"
        elif row["time"] in supported_times:
            corrected_room = "Bedroom"
            source = "bedroom_supported_gap_fill"
        else:
            corrected_room = ""
            source = "rssi_missing_unfilled"
        corrected.append(
            {
                "time": row["time"],
                "raw_rssi_observed": row["rssi_observed"],
                "raw_strongest_room": row["room"],
                "corrected_room": corrected_room,
                "correction_source": source,
                "was_filled": source == "bedroom_supported_gap_fill",
                "low_motion": row["low_motion"],
                "main_sleep_episode_id": episode_by_time.get(row["time"], ""),
            }
        )
    return corrected


def room_transition_count(rows, key):
    count = 0
    previous = None
    previous_time = None
    for row in rows:
        room = row[key]
        continuous = (
            previous_time is not None
            and row["time"] - previous_time == timedelta(minutes=WINDOW_MINUTES)
        )
        if not room:
            previous = None
        elif previous is not None and continuous and room != previous:
            count += 1
        if room:
            previous = room
        previous_time = row["time"]
    return count


def write_corrected_timeline(rows):
    with CORRECTED_TIMELINE_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    raw_missing = sum(not row["raw_rssi_observed"] for row in rows)
    corrected_missing = sum(not row["corrected_room"] for row in rows)
    sleep_rows = [row for row in rows if row["main_sleep_episode_id"] != ""]
    metrics = [
        ("total_5min_windows", len(rows)),
        ("raw_rssi_missing_windows", raw_missing),
        ("corrected_missing_windows", corrected_missing),
        ("bedroom_supported_filled_windows", sum(row["was_filled"] for row in rows)),
        ("bedroom_supported_filled_minutes", sum(row["was_filled"] for row in rows) * WINDOW_MINUTES),
        ("raw_main_sleep_missing_windows", sum(not row["raw_rssi_observed"] for row in sleep_rows)),
        ("corrected_main_sleep_missing_windows", sum(not row["corrected_room"] for row in sleep_rows)),
        ("raw_room_transition_count", room_transition_count(rows, "raw_strongest_room")),
        ("corrected_room_transition_count", room_transition_count(rows, "corrected_room")),
    ]
    with CORRECTION_METRICS_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(metrics)
    return metrics


def state_runs(rows, key):
    runs = []
    start = previous_time = None
    value = ""
    for row in rows:
        current = row[key]
        continuous = (
            previous_time is not None
            and row["time"] - previous_time == timedelta(minutes=WINDOW_MINUTES)
        )
        if current != value or not continuous:
            if start is not None and value:
                runs.append((start, previous_time + timedelta(minutes=WINDOW_MINUTES), value))
            start = row["time"] if current else None
            value = current
        previous_time = row["time"]
    if start is not None and value:
        runs.append((start, previous_time + timedelta(minutes=WINDOW_MINUTES), value))
    return runs


def plot_raw_vs_corrected(rows):
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(16, 6),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1, 0.22]},
    )
    for ax, key, label in [
        (axes[0], "raw_strongest_room", "Raw 5-min strongest-RSSI room"),
        (axes[1], "corrected_room", "Bedroom-supported gap correction"),
    ]:
        for start, end, room in state_runs(rows, key):
            ax.axvspan(start, end, color=LOCATION_COLORS[room], lw=0)
        for row in rows:
            if not row[key]:
                ax.axvspan(
                    row["time"],
                    row["time"] + timedelta(minutes=WINDOW_MINUTES),
                    color="#4d4d4d",
                    lw=0,
                )
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_ylabel(label, rotation=0, ha="right", va="center", labelpad=10)
    for row in rows:
        if row["main_sleep_episode_id"] != "":
            color = "#244b9b"
        elif row["low_motion"]:
            color = "#8ab6f0"
        else:
            color = "#e6e6e6"
        axes[2].axvspan(
            row["time"],
            row["time"] + timedelta(minutes=WINDOW_MINUTES),
            color=color,
            lw=0,
        )
    axes[2].set_ylim(0, 1)
    axes[2].set_yticks([])
    axes[2].set_ylabel("Motion", rotation=0, ha="right", va="center")
    axes[2].set_xlabel("Local time (GMT-5)")
    axes[2].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[2].xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(axes[2].xaxis.get_major_locator())
    )
    handles = [
        mpatches.Patch(color=color, label=room)
        for room, color in LOCATION_COLORS.items()
    ]
    handles.append(mpatches.Patch(color="#4d4d4d", label="RSSI missing"))
    axes[0].legend(
        handles=handles,
        ncol=6,
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.42),
    )
    axes[2].legend(
        handles=[
            mpatches.Patch(color="#8ab6f0", label="Low motion"),
            mpatches.Patch(color="#244b9b", label="Main-sleep episode"),
            mpatches.Patch(color="#e6e6e6", label="Other / missing ACC"),
        ],
        ncol=3,
        fontsize=8,
        loc="upper right",
    )
    fig.suptitle("EF-002 raw RSSI room vs Bedroom-supported gap correction")
    fig.tight_layout()
    fig.savefig(COMPARE_PLOT_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_daily_raw_vs_corrected(rows):
    """Plot raw and corrected states as aligned 24-hour daily panels."""
    days = sorted({row["time"].date() for row in rows})
    fig, axes = plt.subplots(
        len(days), 1, figsize=(13.5, max(9.0, 1.18 * len(days))), squeeze=False
    )
    raw_runs = state_runs(rows, "raw_strongest_room")
    corrected_runs = state_runs(rows, "corrected_room")

    def draw_state(ax, runs, day_start, day_end, y, height):
        for start, end, room in runs:
            left, right = max(start, day_start), min(end, day_end)
            if left < right:
                ax.broken_barh(
                    [(mdates.date2num(left), (right - left).total_seconds() / 86400)],
                    (y, height), facecolors=LOCATION_COLORS[room], linewidth=0,
                )

    for ax, day in zip(axes[:, 0], days):
        day_start = rows[0]["time"].replace(
            year=day.year, month=day.month, day=day.day,
            hour=0, minute=0, second=0, microsecond=0,
        )
        day_end = day_start + timedelta(days=1)
        draw_state(ax, raw_runs, day_start, day_end, 0.58, 0.34)
        draw_state(ax, corrected_runs, day_start, day_end, 0.14, 0.34)
        for row in rows:
            if day_start <= row["time"] < day_end and not row["raw_strongest_room"]:
                left = mdates.date2num(row["time"])
                width = WINDOW_MINUTES / (24 * 60)
                ax.broken_barh([(left, width)], (0.58, 0.34), facecolors="#4d4d4d", linewidth=0)
                if not row["corrected_room"]:
                    ax.broken_barh([(left, width)], (0.14, 0.34), facecolors="#4d4d4d", linewidth=0)
            if day_start <= row["time"] < day_end and row["main_sleep_episode_id"] != "":
                ax.broken_barh(
                    [(mdates.date2num(row["time"]), WINDOW_MINUTES / (24 * 60))],
                    (0.03, 0.045), facecolors="#244b9b", linewidth=0,
                )
            if day_start <= row["time"] < day_end and row["was_filled"]:
                midpoint = row["time"] + timedelta(minutes=WINDOW_MINUTES / 2)
                ax.axvline(midpoint, ymin=0.11, ymax=0.51, color="#f2b701", linewidth=1.2)
        ax.set_xlim(day_start, day_end)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.75, 0.31])
        ax.set_yticklabels(["Raw", "Corrected"], fontsize=7)
        ax.set_ylabel(day.strftime("%d %b"), rotation=0, ha="right", va="center", labelpad=28)
        ax.xaxis.set_major_locator(
            mdates.HourLocator(byhour=[0, 6, 12, 18], tz=day_start.tzinfo)
        )
        ax.xaxis.set_major_formatter(
            mdates.DateFormatter("%H:%M", tz=day_start.tzinfo)
        )
        ax.grid(axis="x", alpha=0.22)
        ax.tick_params(axis="x", labelsize=7)

    handles = [mpatches.Patch(color=color, label=room) for room, color in LOCATION_COLORS.items()]
    handles.extend([
        mpatches.Patch(color="#4d4d4d", label="RSSI missing"),
        mpatches.Patch(color="#244b9b", label="Main-sleep episode"),
        plt.Line2D([0], [0], color="#f2b701", lw=2, label="Bedroom-supported fill"),
    ])
    axes[0, 0].legend(
        handles=handles, ncol=8, fontsize=7.5, loc="lower center",
        bbox_to_anchor=(0.5, 1.03),
    )
    axes[-1, 0].set_xlabel("Local clock time (GMT-5); each row is one calendar day")
    fig.suptitle(
        "EF-002 daily comparison: raw RSSI and Bedroom-supported gap correction",
        y=0.995,
    )
    fig.tight_layout(rect=(0.04, 0.02, 1, 0.975))
    fig.savefig(DAILY_COMPARE_PLOT_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    global candidates_global
    rows = load_rows()
    candidates_global = candidate_episodes(rows)
    centers, boundaries = cluster_durations(candidates_global)
    episodes = build_main_episodes(candidates_global)
    gaps = analyse_gaps(episodes, rows)
    corrected = build_corrected_timeline(rows, episodes, gaps)
    write_outputs(episodes, gaps, centers, boundaries)
    correction_metrics = write_corrected_timeline(corrected)
    plot_clusters(candidates_global, centers, boundaries)
    plot_gap_support(rows, episodes, gaps)
    plot_raw_vs_corrected(corrected)
    plot_daily_raw_vs_corrected(corrected)
    print("EF-002 sleep episode and RSSI-gap analysis complete")
    print("duration centres:", ", ".join(f"{v:.1f}" for v in centers))
    print("boundaries:", ", ".join(f"{v:.1f}" for v in boundaries))
    print("main sleep episodes:", len(episodes))
    print("RSSI gap runs:", len(gaps), Counter(g["support_class"] for g in gaps))
    print("correction metrics:", correction_metrics)
    for path in (
        EPISODES_PATH, GAPS_PATH, METRICS_PATH, CLUSTER_PLOT_PATH,
        SUPPORT_PLOT_PATH, CORRECTED_TIMELINE_PATH, CORRECTION_METRICS_PATH,
        COMPARE_PLOT_PATH,
        DAILY_COMPARE_PLOT_PATH,
    ): print(path)


if __name__ == "__main__":
    main()
