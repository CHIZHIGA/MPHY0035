"""Correct EF-001 strongest-RSSI rooms during low motion with a 30-min vote."""

from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "EF-001"
OUTPUT_DIR = ROOT / "Results" / "SeventhPhase" / "EF-001"
TAGS_PATH = DATA_DIR / "SAMPLES_tags.csv"
METADATA_PATH = DATA_DIR / "metadata_subject.json"
ACC_FEATURES_PATH = OUTPUT_DIR / "EF-001_acc_5min_features.csv"
TIMELINE_PATH = OUTPUT_DIR / "EF-001_low_motion_adaptive_rssi_timeline.csv"
METRICS_PATH = OUTPUT_DIR / "EF-001_low_motion_adaptive_rssi_metrics.csv"
PLOT_PATH = OUTPUT_DIR / "EF-001_raw_vs_low_motion_adaptive_rssi.png"
DAILY_PLOT_PATH = OUTPUT_DIR / "EF-001_daily_raw_vs_low_motion_adaptive_rssi.png"
EPISODE_PATH = OUTPUT_DIR / "EF-001_episode_dominant_room_summary.csv"
EPISODE_CLUSTER_PLOT_PATH = OUTPUT_DIR / "EF-001_all_day_low_motion_episode_clusters.png"

WINDOW_MINUTES = 5
VOTE_WINDOW_MINUTES = 60
LOW_MOTION_THRESHOLD = 0.023
# Allow a 15-minute non-low-motion interruption (e.g. turning or briefly
# getting up). On a 5-minute grid this means adjacent low-motion timestamps may
# be up to 20 minutes apart and still belong to one episode.
MAX_MOTION_INTERRUPTION_MINUTES = 15
MIN_CANDIDATE_EPISODE_MINUTES = 60
MIN_EPISODE_LOW_MOTION_SHARE = 0.60
LOCATION_COLORS = {
    "Living": "#df6483",
    "Bedroom": "#68be91",
    "Bathroom": "#dda0e8",
    "Kitchen": "#6654e8",
    "Office": "#a95be6",
}


def floor_time(value: datetime) -> datetime:
    return value.replace(
        minute=(value.minute // WINDOW_MINUTES) * WINDOW_MINUTES,
        second=0,
        microsecond=0,
    )


def load_metadata():
    with METADATA_PATH.open() as handle:
        metadata = json.load(handle)
    offset = int(metadata.get("timezone", "GMT-7").replace("GMT", ""))
    local_tz = timezone(timedelta(hours=offset))
    beacon_to_location = {
        item["beacon_id"]: item["location"] for item in metadata["beacons"]
    }
    return local_tz, beacon_to_location


def load_acc_features():
    features = {}
    with ACC_FEATURES_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            timestamp = datetime.fromisoformat(row["local_time"])
            acc_std = float(row["acc_magnitude_std_clean"])
            features[timestamp] = {
                "acc_std": acc_std,
                "low_motion": math.isfinite(acc_std)
                and acc_std <= LOW_MOTION_THRESHOLD,
                "night_window": row["night_window"].lower() == "true",
                "sleep_episode_id": row.get("sleep_episode_id", ""),
            }
    return features


def aggregate_rssi(local_tz, valid_beacons):
    totals = defaultdict(lambda: [0.0, 0])
    with TAGS_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                beacon = row["uuid"].strip()
                if beacon not in valid_beacons:
                    continue
                timestamp = datetime.fromtimestamp(
                    int(row["timestamp"]) / 1000, timezone.utc
                ).astimezone(local_tz)
                rssi = float(row["rssi"])
            except (KeyError, TypeError, ValueError):
                continue
            cell = totals[(floor_time(timestamp), beacon)]
            cell[0] += rssi
            cell[1] += 1
    return {
        key: {"mean": total / count, "count": count}
        for key, (total, count) in totals.items()
    }


def build_base_timeline(acc_features, rssi, beacon_to_location):
    rssi_times = sorted({timestamp for timestamp, _ in rssi})
    rows = []
    segment_id = 0
    previous_observed = None
    for timestamp in sorted(set(acc_features) | set(rssi_times)):
        values = [
            (beacon, data["mean"], data["count"])
            for (time, beacon), data in rssi.items()
            if time == timestamp
        ]
        values.sort(key=lambda item: (-item[1], item[0]))
        observed = bool(values)
        if observed and (
            previous_observed is None
            or timestamp - previous_observed != timedelta(minutes=WINDOW_MINUTES)
        ):
            segment_id += 1
        if observed:
            previous_observed = timestamp
        strongest = values[0] if values else ("", float("nan"), 0)
        second = values[1] if len(values) > 1 else ("", float("nan"), 0)
        feature = acc_features.get(timestamp, {})
        rows.append(
            {
                "time": timestamp,
                "segment_id": segment_id if observed else None,
                "observed": observed,
                "raw_beacon": strongest[0],
                "raw_location": beacon_to_location.get(strongest[0], ""),
                "raw_strongest_mean_rssi": strongest[1],
                "raw_second_beacon": second[0],
                "raw_second_mean_rssi": second[1],
                "raw_strongest_second_gap_db": strongest[1] - second[1]
                if len(values) > 1
                else float("nan"),
                "rssi_sample_count": sum(value[2] for value in values),
                "acc_magnitude_std_clean": feature.get("acc_std", float("nan")),
                "low_motion": feature.get("low_motion", False),
                "night_window": feature.get("night_window", False),
                "sleep_episode_id": feature.get("sleep_episode_id", ""),
            }
        )
    return rows


def choose_vote_winner(current_row, candidates, rssi):
    """Return winner and diagnostics for a centred majority vote.

    Candidates must already be restricted to one continuous observed segment.
    Ties in label count use the candidate beacon's mean RSSI across candidate
    window timestamps. A remaining tie falls back to the current raw beacon.
    """
    labels = [row["raw_beacon"] for row in candidates if row["raw_beacon"]]
    counts = Counter(labels)
    if not counts:
        return current_row["raw_beacon"], 0, 0.0, "no_vote_fallback_raw"
    top_count = max(counts.values())
    tied = sorted(beacon for beacon, count in counts.items() if count == top_count)
    if len(tied) == 1:
        winner = tied[0]
        reason = f"low_motion_{VOTE_WINDOW_MINUTES}min_majority"
    else:
        scores = {}
        candidate_times = {row["time"] for row in candidates}
        for beacon in tied:
            values = [
                data["mean"]
                for (timestamp, key), data in rssi.items()
                if timestamp in candidate_times and key == beacon
            ]
            scores[beacon] = sum(values) / len(values) if values else -math.inf
        best_score = max(scores.values())
        rssi_tied = [beacon for beacon in tied if scores[beacon] == best_score]
        if len(rssi_tied) == 1:
            winner = rssi_tied[0]
            reason = f"low_motion_{VOTE_WINDOW_MINUTES}min_vote_tie_rssi"
        else:
            winner = current_row["raw_beacon"]
            reason = f"low_motion_{VOTE_WINDOW_MINUTES}min_full_tie_fallback_raw"
    return winner, top_count, top_count / len(labels), reason


def apply_low_motion_vote(rows, rssi, beacon_to_location):
    half_window = timedelta(minutes=VOTE_WINDOW_MINUTES // 2)
    by_segment = defaultdict(list)
    for row in rows:
        if row["observed"]:
            by_segment[row["segment_id"]].append(row)
    for row in rows:
        row["corrected_beacon"] = row["raw_beacon"]
        row["corrected_location"] = row["raw_location"]
        row["vote_count"] = 0
        row["vote_window_observed_count"] = 0
        row["dominant_vote_share"] = float("nan")
        row["correction_reason"] = "missing_rssi" if not row["observed"] else "high_motion_keep_raw"
        if not row["observed"] or not row["low_motion"]:
            row["was_corrected"] = False
            continue
        candidates = [
            candidate
            for candidate in by_segment[row["segment_id"]]
            if row["time"] - half_window
            <= candidate["time"]
            < row["time"] + half_window
        ]
        winner, count, share, reason = choose_vote_winner(row, candidates, rssi)
        row["corrected_beacon"] = winner
        row["corrected_location"] = beacon_to_location.get(winner, "")
        row["vote_count"] = count
        row["vote_window_observed_count"] = len(candidates)
        row["dominant_vote_share"] = share
        row["correction_reason"] = reason
        row["was_corrected"] = winner != row["raw_beacon"]
    return rows


def detect_long_low_motion_episodes(rows):
    """Cluster all-day low-motion bouts and return the long-duration cluster."""
    all_low_motion = [row for row in rows if row["low_motion"]]
    candidate_bounds = []
    start = last = None
    for row in all_low_motion:
        timestamp = row["time"]
        if (
            start is None
            or timestamp - last
            > timedelta(
                minutes=MAX_MOTION_INTERRUPTION_MINUTES + WINDOW_MINUTES
            )
        ):
            if start is not None:
                candidate_bounds.append(
                    (start, last + timedelta(minutes=WINDOW_MINUTES))
                )
            start = timestamp
        last = timestamp
    if start is not None:
        candidate_bounds.append((start, last + timedelta(minutes=WINDOW_MINUTES)))

    candidates = []
    for start, end in candidate_bounds:
        segment = [row for row in rows if start <= row["time"] < end]
        duration_minutes = int((end - start).total_seconds() / 60)
        low_motion_share = (
            sum(row["low_motion"] for row in segment) / len(segment)
            if segment
            else 0.0
        )
        if duration_minutes >= MIN_CANDIDATE_EPISODE_MINUTES:
            candidates.append(
                {
                    "start": start,
                    "end": end,
                    "duration_minutes": duration_minutes,
                    "low_motion_share": low_motion_share,
                    "rows": segment,
                }
            )
    if not candidates:
        return [], {"short_center": math.nan, "sleep_center": math.nan, "boundary": math.nan}

    log_duration = np.log(
        np.array([candidate["duration_minutes"] for candidate in candidates], dtype=float)
    )
    if len(candidates) == 1:
        labels = np.ones(1, dtype=int)
        centers = np.array([log_duration[0], log_duration[0]])
    else:
        centers = np.quantile(log_duration, [0.25, 0.75])
        for _ in range(100):
            labels = np.argmin(np.abs(log_duration[:, None] - centers), axis=1)
            updated = np.array(
                [
                    log_duration[labels == index].mean()
                    if np.any(labels == index)
                    else centers[index]
                    for index in range(2)
                ]
            )
            if np.max(np.abs(updated - centers)) < 1e-12:
                break
            centers = updated
        order = np.argsort(centers)
        remap = np.empty(2, dtype=int)
        remap[order] = np.arange(2)
        labels = remap[labels]
        centers = centers[order]
    boundary = math.exp(float(centers.mean()))
    episodes = []
    for candidate, label in zip(candidates, labels):
        candidate["duration_cluster"] = "main_sleep" if label == 1 else "short_rest"
        candidate["duration_cluster_boundary_minutes"] = boundary
        if label == 1 and candidate["low_motion_share"] >= MIN_EPISODE_LOW_MOTION_SHARE:
            candidate["episode_id"] = len(episodes) + 1
            episodes.append(candidate)
    model = {
        "short_center": math.exp(float(centers[0])),
        "sleep_center": math.exp(float(centers[1])),
        "boundary": boundary,
        "candidates": candidates,
    }
    return episodes, model


def padded_episode_clock_boundary(episodes, padding_minutes=60):
    """Describe episode timing on a noon-anchored continuous 24-hour axis."""
    if not episodes:
        return "", ""
    def noon_minutes(value):
        return ((value.hour * 60 + value.minute) - 12 * 60) % (24 * 60)

    starts = np.array([noon_minutes(item["start"]) for item in episodes])
    ends = np.array([noon_minutes(item["end"]) for item in episodes])
    lower = float(np.percentile(starts, 5)) - padding_minutes
    upper = float(np.percentile(ends, 95)) + padding_minutes

    def clock_label(noon_axis_minutes):
        minute = int(round(noon_axis_minutes + 12 * 60)) % (24 * 60)
        return f"{minute // 60:02d}:{minute % 60:02d}"

    return clock_label(lower), clock_label(upper)


def plot_episode_clusters(model):
    candidates = model["candidates"]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    for cluster, color, label in [
        ("short_rest", "#a6a6a6", "Short-rest cluster"),
        ("main_sleep", "#244b9b", "Main-sleep cluster"),
    ]:
        subset = [item for item in candidates if item["duration_cluster"] == cluster]
        ax.scatter(
            [item["start"] for item in subset],
            [item["duration_minutes"] / 60 for item in subset],
            color=color,
            s=48,
            label=label,
        )
    ax.axhline(
        model["boundary"] / 60,
        color="#8b1a8b",
        linestyle="--",
        label=f"Log-space boundary = {model['boundary']:.0f} min",
    )
    ax.set_ylabel("Low-motion bout duration (hours)")
    ax.set_xlabel("All-day candidate start time (local)")
    ax.set_title("EF-001 all-day low-motion episode duration clustering")
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(EPISODE_CLUSTER_PLOT_PATH, dpi=220)
    plt.close(fig)


def apply_episode_dominant_room(rows, episodes, rssi, beacon_to_location):
    for row in rows:
        row["long_sleep_episode_id"] = ""
        row["episode_low_motion_share"] = float("nan")
        row["episode_dominant_beacon"] = ""
        row["episode_dominant_location"] = ""
        row["episode_dominant_vote_share"] = float("nan")
    for episode in episodes:
        observed = [row for row in episode["rows"] if row["observed"]]
        if not observed:
            continue
        winner, count, share, _ = choose_vote_winner(observed[0], observed, rssi)
        for row in episode["rows"]:
            row["long_sleep_episode_id"] = episode["episode_id"]
            row["episode_low_motion_share"] = episode["low_motion_share"]
            row["episode_dominant_beacon"] = winner
            row["episode_dominant_location"] = beacon_to_location.get(winner, "")
            row["episode_dominant_vote_share"] = share
            if row["observed"]:
                row["corrected_beacon"] = winner
                row["corrected_location"] = beacon_to_location.get(winner, "")
                row["was_corrected"] = winner != row["raw_beacon"]
                row["correction_reason"] = "long_sleep_episode_dominant_room"
        episode["dominant_beacon"] = winner
        episode["dominant_location"] = beacon_to_location.get(winner, "")
        episode["dominant_vote_count"] = count
        episode["dominant_vote_share"] = share
        episode["observed_windows"] = len(observed)
    return rows


def transition_count(rows, location_key, low_motion_only=False):
    count = 0
    previous = None
    for row in rows:
        if not row["observed"] or (low_motion_only and not row["low_motion"]):
            previous = None
            continue
        current = (row["segment_id"], row[location_key])
        if previous is not None and current[0] == previous[0] and current[1] != previous[1]:
            count += 1
        previous = current
    return count


def write_timeline(rows):
    fields = [
        "time", "segment_id", "observed", "raw_beacon", "raw_location",
        "raw_strongest_mean_rssi", "raw_second_beacon", "raw_second_mean_rssi",
        "raw_strongest_second_gap_db", "rssi_sample_count",
        "acc_magnitude_std_clean", "low_motion", "night_window", "sleep_episode_id",
        "corrected_beacon", "corrected_location", "vote_count",
        "vote_window_observed_count", "dominant_vote_share", "was_corrected",
        "correction_reason",
        "long_sleep_episode_id", "episode_low_motion_share",
        "episode_dominant_beacon", "episode_dominant_location",
        "episode_dominant_vote_share",
    ]
    with TIMELINE_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_episodes(episodes):
    fields = [
        "episode_id", "start", "end", "duration_minutes", "low_motion_share",
        "observed_windows", "dominant_beacon", "dominant_location",
        "dominant_vote_count", "dominant_vote_share",
        "duration_cluster", "duration_cluster_boundary_minutes",
    ]
    with EPISODE_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(episodes)


def write_metrics(rows, locations, episodes, cluster_model):
    boundary_start, boundary_end = padded_episode_clock_boundary(episodes)
    observed = [row for row in rows if row["observed"]]
    low = [row for row in observed if row["low_motion"]]
    metrics = [
        ("overall", "observed_5min_windows", "", len(observed)),
        ("overall", "low_motion_observed_windows", "", len(low)),
        ("overall", "corrected_windows", "", sum(row["was_corrected"] for row in rows)),
        ("overall", "raw_transition_count", "", transition_count(rows, "raw_location")),
        ("overall", "corrected_transition_count", "", transition_count(rows, "corrected_location")),
        ("sleep_episode", "episode_count", "", len(episodes)),
        ("sleep_episode", "allowed_motion_interruption_minutes", "", MAX_MOTION_INTERRUPTION_MINUTES),
        ("sleep_episode", "short_rest_cluster_center_minutes", "", cluster_model["short_center"]),
        ("sleep_episode", "main_sleep_cluster_center_minutes", "", cluster_model["sleep_center"]),
        ("sleep_episode", "duration_cluster_boundary_minutes", "", cluster_model["boundary"]),
        ("sleep_episode", "padded_clock_boundary_start", "", boundary_start),
        ("sleep_episode", "padded_clock_boundary_end", "", boundary_end),
        ("low_motion", "raw_transition_count", "", transition_count(rows, "raw_location", True)),
        ("low_motion", "corrected_transition_count", "", transition_count(rows, "corrected_location", True)),
    ]
    for location in locations:
        metrics.extend(
            [
                ("low_motion", "raw_hours", location, sum(row["raw_location"] == location for row in low) * WINDOW_MINUTES / 60),
                ("low_motion", "corrected_hours", location, sum(row["corrected_location"] == location for row in low) * WINDOW_MINUTES / 60),
            ]
        )
    sleep = [row for row in observed if row["long_sleep_episode_id"] != ""]
    for key in ("raw_location", "corrected_location"):
        metrics.append(("night_low_motion", f"{key}_bedroom_fraction", "Bedroom", sum(row[key] == "Bedroom" for row in sleep) / len(sleep) if sleep else float("nan")))
    with METRICS_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scope", "metric", "location", "value"])
        writer.writerows(metrics)
    return metrics


def contiguous_runs(rows, key):
    runs = []
    start = previous_time = None
    value = None
    for row in rows:
        current = row[key] if row["observed"] else ""
        contiguous = previous_time is not None and row["time"] - previous_time == timedelta(minutes=WINDOW_MINUTES)
        if current != value or not contiguous:
            if start is not None and value:
                runs.append((start, previous_time + timedelta(minutes=WINDOW_MINUTES), value))
            start = row["time"] if current else None
            value = current
        previous_time = row["time"]
    if start is not None and value:
        runs.append((start, previous_time + timedelta(minutes=WINDOW_MINUTES), value))
    return runs


def plot_timeline(rows):
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(16, 6.0),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1, 0.22]},
    )
    for ax, key, title in [
        (axes[0], "raw_location", "Raw 5-min strongest-RSSI room"),
        (
            axes[1],
            "corrected_location",
            "Episode-dominant room (60-min vote outside sleep episodes)",
        ),
    ]:
        for start, end, location in contiguous_runs(rows, key):
            ax.axvspan(start, end, color=LOCATION_COLORS[location], alpha=0.98, linewidth=0)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_ylabel(title, rotation=0, ha="right", va="center", labelpad=10)
        ax.grid(axis="x", alpha=0.2)
    handles = [mpatches.Patch(color=color, label=location) for location, color in LOCATION_COLORS.items()]
    axes[0].legend(handles=handles, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.42), fontsize=8)

    for row in rows:
        if row["long_sleep_episode_id"] != "":
            color = "#244b9b"
        elif row["low_motion"]:
            color = "#8ab6f0"
        else:
            color = "#e6e6e6"
        axes[2].axvspan(
            row["time"],
            row["time"] + timedelta(minutes=WINDOW_MINUTES),
            color=color,
            alpha=1.0,
            linewidth=0,
        )
    axes[2].set_ylim(0, 1)
    axes[2].set_yticks([])
    axes[2].set_ylabel("Motion", rotation=0, ha="right", va="center", labelpad=10)
    axes[2].legend(
        handles=[
            mpatches.Patch(color="#8ab6f0", label="Low motion (ACC std ≤ 0.023)"),
            mpatches.Patch(color="#244b9b", label="Long low-motion sleep episode"),
            mpatches.Patch(color="#e6e6e6", label="Other / missing ACC"),
        ],
        ncol=3,
        loc="upper right",
        fontsize=8,
    )
    axes[2].set_xlabel("Local time (GMT-7)")
    axes[2].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[2].xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(axes[2].xaxis.get_major_locator())
    )
    fig.suptitle("EF-001 raw strongest RSSI vs movement-supported room correction", y=1.02)
    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_daily_comparison(rows):
    """Show every local calendar day at a readable, common 24-hour scale."""
    days = sorted({row["time"].date() for row in rows})
    fig, axes = plt.subplots(
        len(days),
        1,
        figsize=(13.5, max(9.0, 1.18 * len(days))),
        squeeze=False,
    )
    raw_runs = contiguous_runs(rows, "raw_location")
    corrected_runs = contiguous_runs(rows, "corrected_location")
    sleep_runs = []
    start = previous = None
    for row in rows:
        is_sleep = row["long_sleep_episode_id"] != ""
        contiguous = (
            previous is not None
            and row["time"] - previous == timedelta(minutes=WINDOW_MINUTES)
        )
        if is_sleep and start is None:
            start = row["time"]
        elif start is not None and (not is_sleep or not contiguous):
            sleep_runs.append((start, previous + timedelta(minutes=WINDOW_MINUTES)))
            start = row["time"] if is_sleep else None
        previous = row["time"]
    if start is not None:
        sleep_runs.append((start, previous + timedelta(minutes=WINDOW_MINUTES)))

    def draw_runs(ax, runs, day_start, day_end, y, height):
        for start, end, location in runs:
            left, right = max(start, day_start), min(end, day_end)
            if left < right:
                ax.broken_barh(
                    [(mdates.date2num(left), (right - left).total_seconds() / 86400)],
                    (y, height),
                    facecolors=LOCATION_COLORS[location],
                    linewidth=0,
                )

    for ax, day in zip(axes[:, 0], days):
        day_start = rows[0]["time"].replace(
            year=day.year, month=day.month, day=day.day,
            hour=0, minute=0, second=0, microsecond=0,
        )
        day_end = day_start + timedelta(days=1)
        draw_runs(ax, raw_runs, day_start, day_end, 0.58, 0.34)
        draw_runs(ax, corrected_runs, day_start, day_end, 0.14, 0.34)
        for start, end in sleep_runs:
            left, right = max(start, day_start), min(end, day_end)
            if left < right:
                ax.broken_barh(
                    [(mdates.date2num(left), (right - left).total_seconds() / 86400)],
                    (0.03, 0.045), facecolors="#244b9b", linewidth=0,
                )
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

    handles = [
        mpatches.Patch(color=color, label=location)
        for location, color in LOCATION_COLORS.items()
    ]
    handles.append(mpatches.Patch(color="#244b9b", label="Main-sleep episode"))
    axes[0, 0].legend(
        handles=handles, ncol=6, fontsize=8, loc="lower center",
        bbox_to_anchor=(0.5, 1.03),
    )
    axes[-1, 0].set_xlabel("Local clock time (GMT-7); each row is one calendar day")
    fig.suptitle(
        "EF-001 daily comparison: raw strongest RSSI and movement-supported correction",
        y=0.995,
    )
    fig.tight_layout(rect=(0.04, 0.02, 1, 0.975))
    fig.savefig(DAILY_PLOT_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_tz, beacon_to_location = load_metadata()
    acc_features = load_acc_features()
    rssi = aggregate_rssi(local_tz, set(beacon_to_location))
    rows = build_base_timeline(acc_features, rssi, beacon_to_location)
    rows = apply_low_motion_vote(rows, rssi, beacon_to_location)
    episodes, cluster_model = detect_long_low_motion_episodes(rows)
    rows = apply_episode_dominant_room(rows, episodes, rssi, beacon_to_location)
    write_timeline(rows)
    write_episodes(episodes)
    metrics = write_metrics(rows, list(LOCATION_COLORS), episodes, cluster_model)
    plot_episode_clusters(cluster_model)
    plot_timeline(rows)
    plot_daily_comparison(rows)
    print("EF-001 low-motion adaptive RSSI correction complete")
    for _, metric, location, value in metrics[:7]:
        print(f"{metric}{' ' + location if location else ''}: {value}")
    for path in (
        TIMELINE_PATH,
        EPISODE_PATH,
        METRICS_PATH,
        EPISODE_CLUSTER_PLOT_PATH,
        PLOT_PATH,
        DAILY_PLOT_PATH,
    ):
        print(path)


if __name__ == "__main__":
    main()
