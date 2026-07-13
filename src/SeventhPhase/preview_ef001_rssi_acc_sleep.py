"""Preview EF-001 RSSI and ACC, with night-time low-motion sleep annotation.

The export currently contains ACC but no RSSI CSV.  The script therefore produces
an ACC/sleep preview with a clearly marked empty RSSI panel, and automatically
uses SAMPLES_TAGS_RSSI_<beacon>.csv files if they are added later.
"""

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
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "EF-001"
OUTPUT_DIR = ROOT / "Results" / "SeventhPhase" / "EF-001"
ACC_PATH = DATA_DIR / "SAMPLES_HE_ACC.csv"
METADATA_PATH = DATA_DIR / "metadata_subject.json"
PLOT_PATH = OUTPUT_DIR / "EF-001_rssi_acc_sleep_preview.png"
FEATURES_PATH = OUTPUT_DIR / "EF-001_acc_5min_features.csv"
EPISODES_PATH = OUTPUT_DIR / "EF-001_low_motion_sleep_episodes.csv"

WINDOW_MINUTES = 5
# EF-001 log-space four-state clustering gives adjacent centres 0.01379 and
# 0.03830; their log-space midpoint is 0.02298, reported as 0.023.
LOW_MOTION_STD_THRESHOLD = 0.023
MIN_SLEEP_MINUTES = 60
NIGHT_START_HOUR = 18
NIGHT_END_HOUR = 10

# Colours copied from Derek's EF-001 legend screenshot.
LOCATION_COLORS = {
    "Living": "#ff5a8d",
    "Bedroom": "#08cc92",
    "Bathroom": "#e99ae8",
    "Kitchen": "#6256ff",
    "Office": "#a95be6",
}


@dataclass
class RunningStats:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    raw_max: float = float("nan")
    spike_count: int = 0

    def add(self, raw_value: float) -> None:
        # Reuse the SixthPhase spike-cleaning convention.
        value = min(raw_value, 1.2)
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)
        self.raw_max = raw_value if math.isnan(self.raw_max) else max(self.raw_max, raw_value)
        self.spike_count += int(raw_value > 1.2)

    @property
    def std(self) -> float:
        return math.sqrt(self.m2 / (self.count - 1)) if self.count > 1 else float("nan")


def floor_time(value: datetime) -> datetime:
    return value.replace(
        minute=(value.minute // WINDOW_MINUTES) * WINDOW_MINUTES,
        second=0,
        microsecond=0,
    )


def load_metadata():
    with METADATA_PATH.open() as handle:
        metadata = json.load(handle)
    offset_hours = int(metadata.get("timezone", "GMT-7").replace("GMT", ""))
    local_tz = timezone(timedelta(hours=offset_hours))
    beacons = {item["beacon_id"]: item["location"] for item in metadata["beacons"]}
    return metadata, local_tz, beacons


def aggregate_acc(local_tz):
    windows: dict[datetime, RunningStats] = defaultdict(RunningStats)
    with ACC_PATH.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 5:
                continue
            timestamp = datetime.fromtimestamp(int(row[0]) / 1000, timezone.utc).astimezone(local_tz)
            magnitude = math.sqrt(sum(float(value) ** 2 for value in row[2:5]))
            windows[floor_time(timestamp)].add(magnitude)
    return windows


def discover_rssi_files(beacons):
    found = {}
    for path in sorted(DATA_DIR.glob("SAMPLES_TAGS_RSSI*.csv")):
        beacon = next((key for key in beacons if key in path.stem), None)
        if beacon:
            found[beacon] = path
    return found


def aggregate_rssi(local_tz, beacons):
    sums = defaultdict(lambda: [0.0, 0])
    files = discover_rssi_files(beacons)
    for beacon, path in files.items():
        with path.open(newline="") as handle:
            for row in csv.reader(handle):
                if len(row) < 3:
                    continue
                try:
                    timestamp = datetime.fromtimestamp(int(row[0]) / 1000, timezone.utc).astimezone(local_tz)
                    rssi = float(row[-1])
                except ValueError:
                    continue
                cell = sums[(floor_time(timestamp), beacon)]
                cell[0] += rssi
                cell[1] += 1
    combined_path = DATA_DIR / "SAMPLES_tags.csv"
    if combined_path.exists() and combined_path.stat().st_size:
        files["combined_tags"] = combined_path
        with combined_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    timestamp = datetime.fromtimestamp(
                        int(row["timestamp"]) / 1000, timezone.utc
                    ).astimezone(local_tz)
                    beacon = row["uuid"].strip()
                    rssi = float(row["rssi"])
                except (KeyError, TypeError, ValueError):
                    continue
                cell = sums[(floor_time(timestamp), beacon)]
                cell[0] += rssi
                cell[1] += 1
    mean_rssi = {key: total / count for key, (total, count) in sums.items()}
    return mean_rssi, files


def in_night(timestamp):
    return timestamp.hour >= NIGHT_START_HOUR or timestamp.hour < NIGHT_END_HOUR


def detect_sleep(windows):
    times = sorted(windows)
    low_motion = {
        time: in_night(time) and windows[time].std <= LOW_MOTION_STD_THRESHOLD
        for time in times
    }
    episodes = []
    start = previous = None
    for time in times:
        contiguous = previous is not None and time - previous == timedelta(minutes=WINDOW_MINUTES)
        if low_motion[time] and (start is None or not contiguous):
            if start is not None:
                episodes.append((start, previous + timedelta(minutes=WINDOW_MINUTES)))
            start = time
        elif start is not None and (not low_motion[time] or not contiguous):
            episodes.append((start, previous + timedelta(minutes=WINDOW_MINUTES)))
            start = time if low_motion[time] else None
        previous = time
    if start is not None:
        episodes.append((start, previous + timedelta(minutes=WINDOW_MINUTES)))
    return [item for item in episodes if (item[1] - item[0]).total_seconds() / 60 >= MIN_SLEEP_MINUTES]


def write_outputs(windows, episodes):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    episode_lookup = {}
    for number, (start, end) in enumerate(episodes, 1):
        for time in windows:
            if start <= time < end:
                episode_lookup[time] = number
    with FEATURES_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["local_time", "sample_count", "acc_magnitude_mean_clean", "acc_magnitude_std_clean", "acc_magnitude_max_raw", "acc_spike_count_gt_1p2", "night_window", "low_motion", "sleep_episode_id"])
        for time in sorted(windows):
            stats = windows[time]
            writer.writerow([time.isoformat(), stats.count, stats.mean, stats.std, stats.raw_max, stats.spike_count, in_night(time), stats.std <= LOW_MOTION_STD_THRESHOLD, episode_lookup.get(time, "")])
    with EPISODES_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["episode_id", "start_local", "end_local", "duration_minutes", "criterion"])
        for number, (start, end) in enumerate(episodes, 1):
            writer.writerow([number, start.isoformat(), end.isoformat(), int((end - start).total_seconds() / 60), f"night and ACC std <= {LOW_MOTION_STD_THRESHOLD:.3f}"])


def plot_preview(windows, episodes, mean_rssi, rssi_files, beacons):
    times = sorted(windows)
    acc_std = np.array([windows[time].std for time in times])
    fig, axes = plt.subplots(2, 1, figsize=(15, 7), sharex=True, gridspec_kw={"height_ratios": [1.15, 1]})

    if mean_rssi:
        observed_beacons = sorted({beacon for _, beacon in mean_rssi})
        palette = list(LOCATION_COLORS.values())
        for index, beacon in enumerate(observed_beacons):
            location = beacons.get(beacon)
            points = sorted((time, value) for (time, key), value in mean_rssi.items() if key == beacon)
            if points:
                color = LOCATION_COLORS.get(location, palette[index % len(palette)])
                label = f"{beacon} {location}" if location else f"{beacon} (room unknown)"
                axes[0].plot([p[0] for p in points], [p[1] for p in points], ".-", ms=2, lw=0.6, color=color, label=label)
        axes[0].set_ylabel("Mean RSSI (dBm)")
        axes[0].legend(ncol=3, fontsize=8, loc="lower left")
    else:
        axes[0].text(0.5, 0.5, "RSSI data unavailable in EF-001 export", ha="center", va="center", transform=axes[0].transAxes, color="#9b1c31", fontsize=12)
        axes[0].set_ylabel("RSSI")
        handles = [plt.Line2D([0], [0], color=color, lw=5, label=location) for location, color in LOCATION_COLORS.items()]
        axes[0].legend(handles=handles, title="Expected RSSI colours", ncol=3, fontsize=8, loc="lower left")
    axes[0].set_title("EF-001 RSSI and ACC preview with low-motion sleep annotation")

    axes[1].plot(times, acc_std, color="#333333", lw=0.7, label="5-min clean ACC magnitude std")
    axes[1].axhline(LOW_MOTION_STD_THRESHOLD, color="#d62728", ls="--", lw=1, label=f"Low-motion threshold {LOW_MOTION_STD_THRESHOLD:.3f}")
    for index, (start, end) in enumerate(episodes):
        for ax in axes:
            ax.axvspan(start, end, color="#5b8ff9", alpha=0.20, label="Sleep (low motion)" if ax is axes[1] and index == 0 else None)
    axes[1].set_ylabel("ACC magnitude std")
    axes[1].set_xlabel("Local time (GMT-7)")
    axes[1].legend(fontsize=8, loc="upper right")
    axes[1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[1].xaxis.get_major_locator()))
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=220)
    plt.close(fig)


def main():
    _, local_tz, beacons = load_metadata()
    windows = aggregate_acc(local_tz)
    mean_rssi, rssi_files = aggregate_rssi(local_tz, beacons)
    episodes = detect_sleep(windows)
    write_outputs(windows, episodes)
    plot_preview(windows, episodes, mean_rssi, rssi_files, beacons)
    print(f"ACC windows: {len(windows):,}")
    print(f"RSSI sources: {len(rssi_files)}")
    print(f"RSSI UUIDs: {', '.join(sorted({beacon for _, beacon in mean_rssi})) or 'none'}")
    print(f"Sleep episodes >= {MIN_SLEEP_MINUTES} min: {len(episodes)}")
    for output in (PLOT_PATH, FEATURES_PATH, EPISODES_PATH):
        print(output)


if __name__ == "__main__":
    main()
