"""Create an initial, EF-002-specific RSSI and ACC preview."""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data/EF-002"
OUTPUT_DIR = ROOT / "Results/SeventhPhase/EF-002"
ACC_PATH = DATA_DIR / "SAMPLES_HE_ACC.csv"
TAGS_PATH = DATA_DIR / "SAMPLES_tags.csv"
METADATA_PATH = DATA_DIR / "metadata_subject.json"
FEATURES_PATH = OUTPUT_DIR / "EF-002_acc_rssi_5min_features.csv"
THRESHOLD_PATH = OUTPUT_DIR / "EF-002_acc_threshold_clusters.csv"
PREVIEW_PATH = OUTPUT_DIR / "EF-002_rssi_acc_preview.png"
STATE_PATH = OUTPUT_DIR / "EF-002_raw_strongest_rssi_motion.png"

WINDOW_MINUTES = 5
LOCATION_COLORS = {
    "Living": "#df6483",
    "Bedroom": "#08c991",
    "Bathroom": "#e8a0e8",
    "Kitchen": "#6256e8",
    "Office": "#a65ae5",
}


@dataclass
class RunningStats:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0
    raw_max: float = float("nan")
    spikes: int = 0

    def add(self, raw):
        value = min(raw, 1.2)
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.raw_max = raw if math.isnan(self.raw_max) else max(self.raw_max, raw)
        self.spikes += int(raw > 1.2)

    @property
    def std(self):
        return math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else float("nan")


def floor_time(value):
    return value.replace(
        minute=value.minute // WINDOW_MINUTES * WINDOW_MINUTES,
        second=0,
        microsecond=0,
    )


def load_metadata():
    with METADATA_PATH.open() as handle:
        metadata = json.load(handle)
    offset = int(metadata["timezone"].replace("GMT", ""))
    local_tz = timezone(timedelta(hours=offset))
    mapping = {item["beacon_id"]: item["location"] for item in metadata["beacons"]}
    return metadata, local_tz, mapping


def aggregate_acc(local_tz):
    result = defaultdict(RunningStats)
    with ACC_PATH.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 5:
                continue
            timestamp = datetime.fromtimestamp(
                int(row[0]) / 1000, timezone.utc
            ).astimezone(local_tz)
            magnitude = math.sqrt(sum(float(value) ** 2 for value in row[2:5]))
            result[floor_time(timestamp)].add(magnitude)
    return result


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
    return {key: total / count for key, (total, count) in totals.items()}


def cluster_acc_threshold(acc):
    values = np.array(
        [stats.std for stats in acc.values() if math.isfinite(stats.std) and stats.std > 0]
    )
    log_values = np.log10(values)
    centers = np.quantile(log_values, np.linspace(0.05, 0.95, 4))
    for _ in range(200):
        labels = np.argmin(np.abs(log_values[:, None] - centers), axis=1)
        updated = np.array([log_values[labels == index].mean() for index in range(4)])
        if np.max(np.abs(updated - centers)) < 1e-12:
            break
        centers = updated
    centers = np.sort(centers)
    raw_centers = 10 ** centers
    boundaries = 10 ** ((centers[:-1] + centers[1:]) / 2)
    return raw_centers, boundaries, boundaries[1]


def build_rows(acc, rssi, mapping, threshold):
    rssi_by_time = defaultdict(dict)
    for (timestamp, beacon), value in rssi.items():
        rssi_by_time[timestamp][beacon] = value
    rows = []
    for timestamp in sorted(set(acc) | set(rssi_by_time)):
        ordered = sorted(
            rssi_by_time.get(timestamp, {}).items(), key=lambda item: (-item[1], item[0])
        )
        stats = acc.get(timestamp)
        strongest = ordered[0] if ordered else ("", float("nan"))
        rows.append(
            {
                "time": timestamp,
                "acc_sample_count": stats.n if stats else 0,
                "acc_magnitude_mean_clean": stats.mean if stats else float("nan"),
                "acc_magnitude_std_clean": stats.std if stats else float("nan"),
                "acc_magnitude_max_raw": stats.raw_max if stats else float("nan"),
                "acc_spike_count_gt_1p2": stats.spikes if stats else 0,
                "low_motion": bool(stats and stats.std <= threshold),
                "rssi_observed": bool(ordered),
                "raw_strongest_beacon": strongest[0],
                "raw_strongest_location": mapping.get(strongest[0], ""),
                "raw_strongest_mean_rssi": strongest[1],
                "observed_beacon_count": len(ordered),
            }
        )
    return rows


def write_outputs(rows, centers, boundaries):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with FEATURES_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with THRESHOLD_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["state", "center_acc_std", "next_boundary_acc_std"])
        for index, center in enumerate(centers):
            writer.writerow([index + 1, center, boundaries[index] if index < 3 else ""])


def contiguous_runs(rows, key):
    runs = []
    start = previous = None
    value = ""
    for row in rows:
        current = row[key]
        continuous = previous is not None and row["time"] - previous == timedelta(minutes=5)
        if current != value or not continuous:
            if start is not None and value:
                runs.append((start, previous + timedelta(minutes=5), value))
            start = row["time"] if current else None
            value = current
        previous = row["time"]
    if start is not None and value:
        runs.append((start, previous + timedelta(minutes=5), value))
    return runs


def plot_preview(rows, rssi, mapping, threshold):
    fig, axes = plt.subplots(2, 1, figsize=(15, 7), sharex=True)
    for beacon, location in mapping.items():
        points = sorted((time, value) for (time, key), value in rssi.items() if key == beacon)
        axes[0].scatter(
            [point[0] for point in points],
            [point[1] for point in points],
            s=5,
            alpha=0.72,
            color=LOCATION_COLORS[location],
            label=f"{beacon} {location}",
        )
    axes[0].set_ylabel("5-min mean RSSI (dBm)")
    axes[0].set_title("EF-002 RSSI and ACC initial preview")
    axes[0].legend(ncol=3, fontsize=8, loc="lower left")
    axes[0].grid(alpha=0.2)

    axes[1].plot(
        [row["time"] for row in rows],
        [row["acc_magnitude_std_clean"] for row in rows],
        color="#333333",
        linewidth=0.7,
        label="5-min clean ACC magnitude std",
    )
    axes[1].axhline(
        threshold,
        color="#d62728",
        linestyle="--",
        label=f"EF-002 exploratory cluster boundary {threshold:.3f}",
    )
    axes[1].set_ylabel("ACC magnitude std")
    axes[1].set_xlabel("Local time (GMT-5)")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.2)
    axes[1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[1].xaxis.get_major_locator()))
    fig.tight_layout()
    fig.savefig(PREVIEW_PATH, dpi=220)
    plt.close(fig)


def plot_state(rows):
    fig, axes = plt.subplots(
        2, 1, figsize=(15, 4.3), sharex=True, gridspec_kw={"height_ratios": [1, 0.22]}
    )
    for start, end, location in contiguous_runs(rows, "raw_strongest_location"):
        axes[0].axvspan(start, end, color=LOCATION_COLORS[location], linewidth=0)
    axes[0].set_ylim(0, 1)
    axes[0].set_yticks([])
    axes[0].set_ylabel("Raw strongest-RSSI room", rotation=0, ha="right", va="center")
    handles = [mpatches.Patch(color=color, label=location) for location, color in LOCATION_COLORS.items()]
    axes[0].legend(handles=handles, ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.35))
    for row in rows:
        color = "#4f86e8" if row["low_motion"] else "#e6e6e6"
        axes[1].axvspan(row["time"], row["time"] + timedelta(minutes=5), color=color, linewidth=0)
    axes[1].set_ylim(0, 1)
    axes[1].set_yticks([])
    axes[1].set_ylabel("Motion", rotation=0, ha="right", va="center")
    axes[1].set_xlabel("Local time (GMT-5)")
    axes[1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[1].xaxis.get_major_locator()))
    fig.suptitle("EF-002 raw strongest RSSI and EF-002-specific low motion")
    fig.tight_layout()
    fig.savefig(STATE_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    metadata, local_tz, mapping = load_metadata()
    acc = aggregate_acc(local_tz)
    rssi = aggregate_rssi(local_tz, set(mapping))
    centers, boundaries, threshold = cluster_acc_threshold(acc)
    rows = build_rows(acc, rssi, mapping, threshold)
    write_outputs(rows, centers, boundaries)
    plot_preview(rows, rssi, mapping, threshold)
    plot_state(rows)
    print("EF-002 initial preview complete")
    print("timezone:", metadata["timezone"])
    print("ACC range:", min(acc), "to", max(acc), "windows", len(acc))
    print("RSSI range:", min(time for time, _ in rssi), "to", max(time for time, _ in rssi))
    print("ACC centres:", ", ".join(f"{value:.5f}" for value in centers))
    print("boundaries:", ", ".join(f"{value:.5f}" for value in boundaries))
    print("exploratory low-motion boundary:", threshold)
    print("RSSI-observed windows:", sum(row["rssi_observed"] for row in rows))
    print("RSSI-missing windows:", sum(not row["rssi_observed"] for row in rows))
    for path in (FEATURES_PATH, THRESHOLD_PATH, PREVIEW_PATH, STATE_PATH):
        print(path)


if __name__ == "__main__":
    main()
