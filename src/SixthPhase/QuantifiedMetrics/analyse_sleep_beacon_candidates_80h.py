import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE_RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"
OUTPUT_DIR = ROOT / "Results" / "SixthPhase" / "QuantifiedMetrics"

FLOOR_AWARE_RSSI_PATH = (
    SOURCE_RESULTS_DIR / "new80h_floor_aware_rssi_location_5min.csv"
)

EPISODES_OUTPUT = OUTPUT_DIR / "new80h_sleep_candidate_episodes.csv"
NIGHT_SUMMARY_OUTPUT = OUTPUT_DIR / "new80h_sleep_candidate_nightly_summary.csv"
BEACON_SUMMARY_OUTPUT = OUTPUT_DIR / "new80h_sleep_candidate_beacon_summary.csv"
PLOT_OUTPUT = OUTPUT_DIR / "new80h_sleep_candidate_timeline.png"

LOCAL_TZ = "Europe/London"
WINDOW_MINUTES = 5
LOW_MOTION_STD_THRESHOLD = 0.010
MIN_EPISODE_MINUTES = 60
DOMINANT_BEACON_SHARE_THRESHOLD = 0.60
NIGHT_START_HOUR = 18
NIGHT_END_HOUR = 10
RSSI_BEACON_COL = "pressure_floor_bruteforce_rssi_beacon"
BEACON_ORDER = ["CA59", "1933", "D7FD", "3E05"]
BEACON_COLORS = {
    "CA59": "#2ca02c",
    "1933": "#1f77b4",
    "D7FD": "#d62728",
    "3E05": "#ff7f0e",
}


def load_timeline():
    frame = pd.read_csv(FLOOR_AWARE_RSSI_PATH, parse_dates=["time"])
    frame = frame.sort_values("time").reset_index(drop=True)
    frame["local_time"] = frame["time"].dt.tz_convert(LOCAL_TZ)
    return frame


def assign_sleep_night(local_times):
    dates = local_times.dt.date
    previous_dates = (local_times - pd.Timedelta(days=1)).dt.date
    return dates.where(local_times.dt.hour >= NIGHT_START_HOUR, previous_dates)


def is_in_night_window(local_times):
    hours = local_times.dt.hour
    return (hours >= NIGHT_START_HOUR) | (hours < NIGHT_END_HOUR)


def add_sleep_features(frame):
    updated = frame.copy()
    updated["sleep_night"] = assign_sleep_night(updated["local_time"])
    updated["in_sleep_search_window"] = is_in_night_window(updated["local_time"])
    updated["low_motion_window"] = (
        updated["acc_magnitude_std_clean"].fillna(999).le(LOW_MOTION_STD_THRESHOLD)
        & updated["acc_spike_count_gt_1p2"].fillna(0).eq(0)
    )
    updated["sleep_candidate_window"] = (
        updated["in_sleep_search_window"]
        & updated["low_motion_window"]
        & updated[RSSI_BEACON_COL].notna()
    )
    return updated


def build_runs(frame):
    runs = []
    start_index = None
    previous_index = None
    for index, row in frame.iterrows():
        is_candidate = bool(row["sleep_candidate_window"])
        contiguous_with_previous = (
            previous_index is not None
            and row["time"] - frame.loc[previous_index, "time"]
            == pd.Timedelta(minutes=WINDOW_MINUTES)
        )
        if is_candidate and start_index is None:
            start_index = index
        elif (
            start_index is not None
            and (
                not is_candidate
                or row["sleep_night"] != frame.loc[previous_index, "sleep_night"]
                or not contiguous_with_previous
            )
        ):
            runs.append((start_index, previous_index))
            start_index = index if is_candidate else None
        previous_index = index
    if start_index is not None:
        runs.append((start_index, previous_index))
    return runs


def summarize_episode(segment, episode_id):
    beacon_counts = segment[RSSI_BEACON_COL].value_counts(dropna=True)
    dominant_beacon = beacon_counts.index[0] if not beacon_counts.empty else pd.NA
    dominant_windows = int(beacon_counts.iloc[0]) if not beacon_counts.empty else 0
    total_windows = len(segment)
    dominant_share = dominant_windows / total_windows if total_windows else 0
    start_time = segment["time"].iloc[0]
    end_time = segment["time"].iloc[-1] + pd.Timedelta(minutes=WINDOW_MINUTES)
    duration_minutes = total_windows * WINDOW_MINUTES
    return {
        "episode_id": episode_id,
        "sleep_night": segment["sleep_night"].iloc[0],
        "start_time": start_time,
        "end_time": end_time,
        "start_local_time": segment["local_time"].iloc[0],
        "end_local_time": segment["local_time"].iloc[-1]
        + pd.Timedelta(minutes=WINDOW_MINUTES),
        "duration_minutes": duration_minutes,
        "window_count": total_windows,
        "dominant_beacon": dominant_beacon,
        "dominant_beacon_windows": dominant_windows,
        "dominant_beacon_share": dominant_share,
        "mean_acc_motion_score": segment["acc_motion_score"].mean(),
        "median_acc_motion_score": segment["acc_motion_score"].median(),
        "mean_rssi_gap_db": segment["strongest_second_gap"].mean(),
        "floor_mode": segment["pressure_inferred_floor_smoothed_label"].mode().iloc[0]
        if not segment["pressure_inferred_floor_smoothed_label"].mode().empty
        else pd.NA,
    }


def build_sleep_episodes(frame):
    rows = []
    for episode_number, (start, end) in enumerate(build_runs(frame), start=1):
        segment = frame.loc[start:end].copy()
        summary = summarize_episode(segment, episode_number)
        if summary["duration_minutes"] >= MIN_EPISODE_MINUTES:
            summary["sleep_candidate_episode"] = (
                summary["dominant_beacon_share"] >= DOMINANT_BEACON_SHARE_THRESHOLD
            )
            rows.append(summary)
    return pd.DataFrame(rows)


def build_nightly_summary(episodes):
    if episodes.empty:
        return pd.DataFrame()
    grouped = episodes.groupby("sleep_night")
    rows = []
    for night, group in grouped:
        longest = group.sort_values("duration_minutes", ascending=False).iloc[0]
        rows.append(
            {
                "sleep_night": night,
                "candidate_episode_count": len(group),
                "total_candidate_minutes": group["duration_minutes"].sum(),
                "longest_episode_minutes": longest["duration_minutes"],
                "longest_episode_start_local": longest["start_local_time"],
                "longest_episode_end_local": longest["end_local_time"],
                "dominant_beacon_longest_episode": longest["dominant_beacon"],
                "dominant_beacon_share_longest_episode": longest[
                    "dominant_beacon_share"
                ],
                "floor_mode_longest_episode": longest["floor_mode"],
            }
        )
    return pd.DataFrame(rows)


def build_beacon_summary(episodes):
    if episodes.empty:
        return pd.DataFrame()
    summary = (
        episodes.groupby("dominant_beacon")
        .agg(
            episode_count=("episode_id", "count"),
            total_candidate_minutes=("duration_minutes", "sum"),
            mean_dominant_share=("dominant_beacon_share", "mean"),
            nights_present=("sleep_night", "nunique"),
            mean_acc_motion_score=("mean_acc_motion_score", "mean"),
        )
        .reset_index()
        .sort_values(
            ["nights_present", "total_candidate_minutes", "mean_dominant_share"],
            ascending=False,
        )
    )
    total_minutes = summary["total_candidate_minutes"].sum()
    summary["candidate_minutes_fraction"] = (
        summary["total_candidate_minutes"] / total_minutes if total_minutes else 0
    )
    return summary


def plot_sleep_candidates(frame, episodes, beacon_summary):
    fig, axes = plt.subplots(2, 1, figsize=(13, 6.3), sharex=True)
    y_map = {beacon: index for index, beacon in enumerate(BEACON_ORDER)}
    plot_data = frame.loc[frame["in_sleep_search_window"]].copy()

    axes[0].scatter(
        plot_data["time"],
        plot_data[RSSI_BEACON_COL].map(y_map),
        c=plot_data[RSSI_BEACON_COL].map(BEACON_COLORS),
        s=14,
        alpha=0.55,
        label="5-min floor-aware beacon",
    )
    for episode in episodes.itertuples(index=False):
        color = BEACON_COLORS.get(episode.dominant_beacon, "#7f7f7f")
        axes[0].axvspan(
            episode.start_time,
            episode.end_time,
            color=color,
            alpha=0.18,
        )
    axes[0].set_yticks(list(y_map.values()))
    axes[0].set_yticklabels(BEACON_ORDER)
    axes[0].set_ylabel("Beacon")
    axes[0].set_title("Low-motion nightly long-stay candidate episodes")
    axes[0].grid(axis="x", alpha=0.2)

    axes[1].plot(
        frame["time"],
        frame["acc_motion_score"],
        color="#4c4c4c",
        linewidth=0.8,
        label="ACC motion score",
    )
    axes[1].axhline(
        LOW_MOTION_STD_THRESHOLD,
        color="#d62728",
        linestyle="--",
        linewidth=1.0,
        label="Low-motion threshold",
    )
    for episode in episodes.itertuples(index=False):
        axes[1].axvspan(
            episode.start_time,
            episode.end_time,
            color=BEACON_COLORS.get(episode.dominant_beacon, "#7f7f7f"),
            alpha=0.14,
        )
    axes[1].set_ylabel("ACC std")
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.2)
    axes[1].legend(loc="upper left", fontsize=8)

    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            linestyle="None",
            color=BEACON_COLORS[beacon],
            label=beacon,
        )
        for beacon in BEACON_ORDER
    ]
    if not beacon_summary.empty:
        likely = beacon_summary.iloc[0]["dominant_beacon"]
        axes[0].legend(
            handles=handles,
            title=f"Beacon (top candidate: {likely})",
            loc="upper left",
            fontsize=8,
        )
    else:
        axes[0].legend(handles=handles, title="Beacon", loc="upper left", fontsize=8)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return PLOT_OUTPUT


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timeline = add_sleep_features(load_timeline())
    episodes = build_sleep_episodes(timeline)
    nightly_summary = build_nightly_summary(episodes)
    beacon_summary = build_beacon_summary(episodes)

    episodes.to_csv(EPISODES_OUTPUT, index=False)
    nightly_summary.to_csv(NIGHT_SUMMARY_OUTPUT, index=False)
    beacon_summary.to_csv(BEACON_SUMMARY_OUTPUT, index=False)
    plot_output = plot_sleep_candidates(timeline, episodes, beacon_summary)

    print("Sleep beacon candidate analysis complete")
    print("Saved outputs:")
    for output in [
        EPISODES_OUTPUT,
        NIGHT_SUMMARY_OUTPUT,
        BEACON_SUMMARY_OUTPUT,
        plot_output,
    ]:
        print(output)
    print("\nBeacon summary:")
    print(beacon_summary.to_string(index=False))
    print("\nNightly summary:")
    print(nightly_summary.to_string(index=False))


if __name__ == "__main__":
    main()
