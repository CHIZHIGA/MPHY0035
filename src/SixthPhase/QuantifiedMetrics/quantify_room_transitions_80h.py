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

TIMELINE_OUTPUT = OUTPUT_DIR / "new80h_room_transition_acc_support_5min.csv"
EVENTS_OUTPUT = OUTPUT_DIR / "new80h_room_transition_events.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "new80h_room_transition_summary.csv"
DAILY_SUMMARY_OUTPUT = OUTPUT_DIR / "new80h_room_transition_daily_summary.csv"
PLOT_OUTPUT = OUTPUT_DIR / "new80h_room_transition_acc_support_timeline.png"

LOCAL_TZ = "Europe/London"
WINDOW_MINUTES = 5
AWAKE_ACC_STD_THRESHOLD = 0.010
RSSI_BEACON_COL = "pressure_floor_bruteforce_rssi_beacon"
RSSI_FLOOR_COL = "pressure_floor_bruteforce_rssi_floor"
RAW_BEACON_COL = "strongest_beacon"

BEACON_ORDER = ["CA59", "1933", "D7FD", "3E05"]
BEACON_TO_Y = {beacon: index for index, beacon in enumerate(BEACON_ORDER)}
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


def add_room_transition_features(frame):
    updated = frame.copy()
    updated["awake_motion_window"] = updated["acc_magnitude_std_clean"].gt(
        AWAKE_ACC_STD_THRESHOLD
    )
    updated["previous_floor_aware_beacon"] = updated[RSSI_BEACON_COL].shift(1)
    updated["previous_floor_aware_floor"] = updated[RSSI_FLOOR_COL].shift(1)
    updated["rssi_gap_before_minutes"] = (
        updated["time"].diff().dt.total_seconds() / 60
    )
    updated["rssi_window_contiguous"] = updated["time"].diff().eq(
        pd.Timedelta(minutes=WINDOW_MINUTES)
    )
    valid_current = updated[RSSI_BEACON_COL].notna()
    valid_previous = updated["previous_floor_aware_beacon"].notna()
    updated["room_transition"] = (
        valid_current
        & valid_previous
        & updated["rssi_window_contiguous"]
        & updated[RSSI_BEACON_COL].ne(updated["previous_floor_aware_beacon"])
    )
    updated["floor_transition_from_rssi_beacon"] = (
        updated["room_transition"]
        & updated[RSSI_FLOOR_COL].ne(updated["previous_floor_aware_floor"])
    )
    awake_near_transition = (
        updated["awake_motion_window"].shift(1, fill_value=False)
        | updated["awake_motion_window"]
        | updated["awake_motion_window"].shift(-1, fill_value=False)
    )
    updated["room_transition_acc_supported"] = (
        updated["room_transition"] & awake_near_transition
    )
    updated["unsupported_room_transition_candidate"] = (
        updated["room_transition"] & ~updated["room_transition_acc_supported"]
    )
    updated["transition_support_rule"] = pd.NA
    updated.loc[
        updated["room_transition_acc_supported"], "transition_support_rule"
    ] = "awake ACC window within +/-5 min"
    updated.loc[
        updated["unsupported_room_transition_candidate"], "transition_support_rule"
    ] = "no awake ACC window within +/-5 min"
    updated["event_date"] = updated["local_time"].dt.date
    return updated


def build_transition_events(timeline):
    events = timeline.loc[timeline["room_transition"]].copy()
    events["from_beacon"] = events["previous_floor_aware_beacon"]
    events["to_beacon"] = events[RSSI_BEACON_COL]
    events["from_floor"] = events["previous_floor_aware_floor"]
    events["to_floor"] = events[RSSI_FLOOR_COL]
    events["transition_pair"] = events["from_beacon"] + " -> " + events["to_beacon"]
    keep_cols = [
        "time",
        "local_time",
        "event_date",
        "from_beacon",
        "to_beacon",
        "transition_pair",
        "rssi_gap_before_minutes",
        "rssi_window_contiguous",
        "from_floor",
        "to_floor",
        "floor_transition_from_rssi_beacon",
        "room_transition_acc_supported",
        "unsupported_room_transition_candidate",
        "transition_support_rule",
        "acc_magnitude_std_clean",
        "acc_motion_score",
        "acc_spike_count_gt_1p2",
        "strongest_second_gap",
        "pressure_inferred_floor_smoothed_label",
        "pressure_floor_confidence",
        RAW_BEACON_COL,
        RSSI_BEACON_COL,
    ]
    return events[keep_cols].copy()


def safe_rate(count, hours):
    if hours <= 0:
        return 0.0
    return count / hours


def summarize_counts(timeline, events):
    total_windows = len(timeline)
    awake_windows = int(timeline["awake_motion_window"].sum())
    awake_hours = awake_windows * WINDOW_MINUTES / 60
    observed_hours = total_windows * WINDOW_MINUTES / 60
    transition_count = len(events)
    supported_count = int(events["room_transition_acc_supported"].sum())
    unsupported_count = int(events["unsupported_room_transition_candidate"].sum())
    floor_switch_count = int(events["floor_transition_from_rssi_beacon"].sum())
    return pd.DataFrame(
        [
            {
                "observed_windows": total_windows,
                "observed_hours": observed_hours,
                "awake_motion_windows": awake_windows,
                "awake_motion_hours": awake_hours,
                "awake_motion_fraction": awake_windows / total_windows
                if total_windows
                else 0,
                "room_transition_count": transition_count,
                "acc_supported_room_transition_count": supported_count,
                "unsupported_room_transition_count": unsupported_count,
                "floor_switch_transition_count": floor_switch_count,
                "acc_supported_transition_fraction": supported_count
                / transition_count
                if transition_count
                else 0,
                "room_transition_rate_per_observed_hour": safe_rate(
                    transition_count, observed_hours
                ),
                "room_transition_rate_per_awake_hour": safe_rate(
                    transition_count, awake_hours
                ),
                "acc_supported_transition_rate_per_awake_hour": safe_rate(
                    supported_count, awake_hours
                ),
                "unsupported_transition_rate_per_awake_hour": safe_rate(
                    unsupported_count, awake_hours
                ),
                "awake_acc_std_threshold": AWAKE_ACC_STD_THRESHOLD,
                "transition_location_source": RSSI_BEACON_COL,
            }
        ]
    )


def build_daily_summary(timeline, events):
    observed = (
        timeline.groupby("event_date")
        .agg(
            observed_windows=("time", "count"),
            awake_motion_windows=("awake_motion_window", "sum"),
        )
        .reset_index()
    )
    observed["observed_hours"] = observed["observed_windows"] * WINDOW_MINUTES / 60
    observed["awake_motion_hours"] = (
        observed["awake_motion_windows"] * WINDOW_MINUTES / 60
    )
    if events.empty:
        counts = pd.DataFrame(columns=["event_date"])
    else:
        counts = (
            events.groupby("event_date")
            .agg(
                room_transition_count=("time", "count"),
                acc_supported_room_transition_count=(
                    "room_transition_acc_supported",
                    "sum",
                ),
                unsupported_room_transition_count=(
                    "unsupported_room_transition_candidate",
                    "sum",
                ),
                floor_switch_transition_count=(
                    "floor_transition_from_rssi_beacon",
                    "sum",
                ),
            )
            .reset_index()
        )
    summary = observed.merge(counts, on="event_date", how="left")
    count_cols = [
        "room_transition_count",
        "acc_supported_room_transition_count",
        "unsupported_room_transition_count",
        "floor_switch_transition_count",
    ]
    for column in count_cols:
        summary[column] = summary[column].fillna(0).astype(int)
    summary["room_transition_rate_per_awake_hour"] = summary.apply(
        lambda row: safe_rate(
            row["room_transition_count"], row["awake_motion_hours"]
        ),
        axis=1,
    )
    summary["acc_supported_transition_rate_per_awake_hour"] = summary.apply(
        lambda row: safe_rate(
            row["acc_supported_room_transition_count"],
            row["awake_motion_hours"],
        ),
        axis=1,
    )
    return summary


def plot_room_transitions(timeline, events):
    fig, axes = plt.subplots(2, 1, figsize=(13.5, 6.4), sharex=True)

    for beacon in BEACON_ORDER:
        beacon_data = timeline.loc[timeline[RSSI_BEACON_COL].eq(beacon)]
        axes[0].scatter(
            beacon_data["time"],
            beacon_data[RSSI_BEACON_COL].map(BEACON_TO_Y),
            color=BEACON_COLORS[beacon],
            s=12,
            alpha=0.65,
            label=beacon,
        )

    supported = events.loc[events["room_transition_acc_supported"]]
    unsupported = events.loc[events["unsupported_room_transition_candidate"]]
    axes[0].scatter(
        supported["time"],
        supported["to_beacon"].map(BEACON_TO_Y),
        s=42,
        facecolors="none",
        edgecolors="black",
        linewidths=1.2,
        label="ACC-supported transition",
    )
    axes[0].scatter(
        unsupported["time"],
        unsupported["to_beacon"].map(BEACON_TO_Y),
        s=46,
        marker="x",
        color="#d62728",
        linewidths=1.2,
        label="Unsupported transition",
    )
    axes[0].set_yticks(list(BEACON_TO_Y.values()))
    axes[0].set_yticklabels(BEACON_ORDER)
    axes[0].set_ylabel("Beacon")
    axes[0].set_title(
        "Room transitions from pressure-floor-aware RSSI, marked by ACC support"
    )
    axes[0].grid(axis="x", alpha=0.2)
    axes[0].legend(loc="upper left", ncol=3, fontsize=8)

    axes[1].plot(
        timeline["time"],
        timeline["acc_magnitude_std_clean"],
        color="#4c4c4c",
        linewidth=0.9,
        label="ACC magnitude std clean",
    )
    axes[1].axhline(
        AWAKE_ACC_STD_THRESHOLD,
        color="#d62728",
        linestyle="--",
        linewidth=1.0,
        label="Awake/motion threshold",
    )
    axes[1].scatter(
        supported["time"],
        supported["acc_magnitude_std_clean"],
        s=34,
        facecolors="none",
        edgecolors="black",
        linewidths=1.0,
    )
    axes[1].scatter(
        unsupported["time"],
        unsupported["acc_magnitude_std_clean"],
        s=36,
        marker="x",
        color="#d62728",
        linewidths=1.0,
    )
    axes[1].set_ylabel("ACC std")
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.2)
    axes[1].legend(loc="upper left", fontsize=8)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return PLOT_OUTPUT


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timeline = add_room_transition_features(load_timeline())
    events = build_transition_events(timeline)
    summary = summarize_counts(timeline, events)
    daily_summary = build_daily_summary(timeline, events)
    plot_output = plot_room_transitions(timeline, events)

    timeline.to_csv(TIMELINE_OUTPUT, index=False)
    events.to_csv(EVENTS_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    daily_summary.to_csv(DAILY_SUMMARY_OUTPUT, index=False)

    print("Room transition ACC support analysis complete")
    print("Saved outputs:")
    for output in [
        TIMELINE_OUTPUT,
        EVENTS_OUTPUT,
        SUMMARY_OUTPUT,
        DAILY_SUMMARY_OUTPUT,
        plot_output,
    ]:
        print(output)
    print("\nSummary:")
    print(summary.to_string(index=False))
    print("\nDaily summary:")
    print(daily_summary.to_string(index=False))


if __name__ == "__main__":
    main()
