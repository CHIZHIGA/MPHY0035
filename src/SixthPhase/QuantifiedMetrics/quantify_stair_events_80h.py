import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE_RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"
OUTPUT_DIR = ROOT / "Results" / "SixthPhase" / "QuantifiedMetrics"

FLOOR_TIMELINE_PATH = (
    SOURCE_RESULTS_DIR / "new80h_pressure_inferred_floor_timeline_5min.csv"
)
SHIFT_SUPPORT_PATH = (
    SOURCE_RESULTS_DIR / "new80h_pressure_floor_shift_acc_support.csv"
)
ACC_FEATURES_PATH = SOURCE_RESULTS_DIR / "new80h_acc_5min_features.csv"

EVENTS_OUTPUT = OUTPUT_DIR / "new80h_stair_events_5min.csv"
DURATION_DETAILS_OUTPUT = OUTPUT_DIR / "new80h_stair_event_duration_details.csv"
DAILY_SUMMARY_OUTPUT = OUTPUT_DIR / "new80h_stair_events_daily_summary.csv"
PLOT_OUTPUT = OUTPUT_DIR / "new80h_stair_events_timeline.png"

LOCAL_TZ = "Europe/London"
WINDOW_MINUTES = 5
MAX_PLAUSIBLE_STAIR_DURATION_MIN = 20
MAX_EXPECTED_SUPPORT_WINDOW_MIN = 15


def load_inputs():
    floor_timeline = pd.read_csv(FLOOR_TIMELINE_PATH, parse_dates=["time"])
    shift_support = pd.read_csv(
        SHIFT_SUPPORT_PATH,
        parse_dates=["shift_time", "support_window_start", "support_window_end"],
    )
    acc_features = pd.read_csv(ACC_FEATURES_PATH, parse_dates=["time"])
    return floor_timeline, shift_support, acc_features


def local_date(series):
    return series.dt.tz_convert(LOCAL_TZ).dt.date


def classify_stair_direction(previous_floor, current_floor):
    if previous_floor == "1F" and current_floor == "2F":
        return "ascent"
    if previous_floor == "2F" and current_floor == "1F":
        return "descent"
    return "unknown"


def estimate_event_duration(row, acc_features):
    local_window_start = max(
        row["support_window_start"], row["shift_time"] - pd.Timedelta(minutes=5)
    )
    local_window_end = min(
        row["support_window_end"], row["shift_time"] + pd.Timedelta(minutes=5)
    )
    support_mask = acc_features["time"].between(
        local_window_start, local_window_end
    )
    support_acc = acc_features.loc[support_mask].copy()
    high_motion = support_acc.loc[
        support_acc["acc_high_motion_window"].fillna(False)
        | support_acc["acc_spike_count_gt_1p2"].fillna(0).gt(0)
    ]

    if high_motion.empty:
        start = row["shift_time"] - pd.Timedelta(minutes=WINDOW_MINUTES)
        end = row["shift_time"]
        method = "floor_shift_window_no_acc_support"
    else:
        start = high_motion["time"].min()
        end = high_motion["time"].max() + pd.Timedelta(minutes=WINDOW_MINUTES)
        method = "contiguous_high_acc_windows_near_shift"

    duration_min = max((end - start).total_seconds() / 60, WINDOW_MINUTES)
    return pd.Series(
        {
            "estimated_event_start": start,
            "estimated_event_end": end,
            "estimated_duration_min": duration_min,
            "duration_estimation_method": method,
            "acc_high_motion_window_count": int(len(high_motion)),
            "acc_support_window_count": int(len(support_acc)),
            "duration_window_start": local_window_start,
            "duration_window_end": local_window_end,
        }
    )


def build_stair_events(shift_support, acc_features):
    events = shift_support.copy()
    events["stair_direction"] = events.apply(
        lambda row: classify_stair_direction(row["previous_floor"], row["current_floor"]),
        axis=1,
    )
    events["event_date"] = local_date(events["shift_time"])
    duration_features = events.apply(
        lambda row: estimate_event_duration(row, acc_features), axis=1
    )
    events = pd.concat([events, duration_features], axis=1)
    events["event_label"] = events["stair_direction"].map(
        {"ascent": "1F to 2F", "descent": "2F to 1F"}
    )
    events = add_event_quality_fields(events)
    keep_cols = [
        "shift_time",
        "event_date",
        "previous_floor",
        "current_floor",
        "stair_direction",
        "event_label",
        "estimated_event_start",
        "estimated_event_end",
        "estimated_duration_min",
        "duration_too_long_anomaly",
        "support_window_duration_min",
        "support_window_too_long_anomaly",
        "any_duration_or_window_anomaly",
        "duration_anomaly_explanation",
        "duration_estimation_method",
        "floor_shift_acc_supported",
        "unsupported_floor_shift_candidate",
        "support_reason",
        "acc_support_explanation",
        "max_acc_motion_score",
        "max_acc_magnitude_raw",
        "total_acc_spike_count_gt_1p2",
        "acc_high_motion_window_count",
        "acc_support_window_count",
        "duration_window_start",
        "duration_window_end",
        "support_window_start",
        "support_window_end",
    ]
    return events[keep_cols].copy()


def add_event_quality_fields(events):
    events = events.copy()
    events["support_window_duration_min"] = (
        events["support_window_end"] - events["support_window_start"]
    ).dt.total_seconds() / 60
    events["duration_too_long_anomaly"] = events["estimated_duration_min"].gt(
        MAX_PLAUSIBLE_STAIR_DURATION_MIN
    )
    events["support_window_too_long_anomaly"] = events[
        "support_window_duration_min"
    ].gt(MAX_EXPECTED_SUPPORT_WINDOW_MIN)
    events["any_duration_or_window_anomaly"] = (
        events["duration_too_long_anomaly"]
        | events["support_window_too_long_anomaly"]
    )
    events["duration_anomaly_explanation"] = events.apply(
        describe_duration_anomaly, axis=1
    )
    events["acc_support_explanation"] = events.apply(
        describe_acc_support, axis=1
    )
    return events


def describe_duration_anomaly(row):
    if row["duration_too_long_anomaly"]:
        return (
            f"Estimated stair duration is >{MAX_PLAUSIBLE_STAIR_DURATION_MIN} min; "
            "treat as a duration anomaly rather than a plausible stair event."
        )
    if row["support_window_too_long_anomaly"]:
        return (
            f"Original ACC support window is {row['support_window_duration_min']:.1f} "
            "min, longer than expected for one stair event. This usually happens when "
            "the floor timeline has irregular spacing or a data gap around the shift. "
            "The reported stair duration is therefore clipped to the local +/-5 min "
            "window around the floor shift."
        )
    return "No long-duration anomaly detected."


def describe_acc_support(row):
    if bool(row["floor_shift_acc_supported"]):
        if row["support_window_too_long_anomaly"]:
            return (
                "ACC-supported: at least one local high-motion ACC window or raw "
                ">1.2 ACC spike was found near the pressure floor shift. The original "
                "support window is unusually long, so it is not used directly as the "
                "stair duration."
            )
        return (
            "ACC-supported: local ACC evidence near the pressure floor shift includes "
            "a high-motion ACC window or a raw >1.2 ACC spike."
        )
    return (
        "ACC-unsupported: no high-motion ACC window and no raw >1.2 ACC spike were "
        "found in the local shift-support window."
    )


def build_duration_details(events):
    columns = [
        "shift_time",
        "event_date",
        "stair_direction",
        "event_label",
        "estimated_event_start",
        "estimated_event_end",
        "estimated_duration_min",
        "duration_too_long_anomaly",
        "support_window_duration_min",
        "support_window_too_long_anomaly",
        "any_duration_or_window_anomaly",
        "duration_anomaly_explanation",
        "floor_shift_acc_supported",
        "unsupported_floor_shift_candidate",
        "acc_support_explanation",
        "max_acc_motion_score",
        "max_acc_magnitude_raw",
        "total_acc_spike_count_gt_1p2",
        "acc_high_motion_window_count",
        "acc_support_window_count",
        "duration_window_start",
        "duration_window_end",
        "support_window_start",
        "support_window_end",
    ]
    return events[columns].copy()


def build_daily_summary(events, floor_timeline):
    floor_timeline = floor_timeline.copy()
    floor_timeline["event_date"] = local_date(floor_timeline["time"])
    observed_floor_windows = floor_timeline[
        floor_timeline["pressure_floor_observed"].fillna(False)
    ]
    indoor_hours = (
        observed_floor_windows.groupby("event_date")
        .size()
        .mul(WINDOW_MINUTES / 60)
        .rename("pressure_floor_observed_hours")
    )

    grouped = events.groupby("event_date")
    rows = []
    for date_value, group in grouped:
        ascents = group["stair_direction"].eq("ascent")
        descents = group["stair_direction"].eq("descent")
        total_events = len(group)
        hours = indoor_hours.get(date_value, 0)
        rows.append(
            {
                "event_date": date_value,
                "stair_events": total_events,
                "ascents": int(ascents.sum()),
                "descents": int(descents.sum()),
                "acc_supported_events": int(
                    group["floor_shift_acc_supported"].fillna(False).sum()
                ),
                "unsupported_events": int(
                    group["unsupported_floor_shift_candidate"].fillna(False).sum()
                ),
                "mean_ascent_duration_min": group.loc[
                    ascents, "estimated_duration_min"
                ].mean(),
                "mean_descent_duration_min": group.loc[
                    descents, "estimated_duration_min"
                ].mean(),
                "median_event_duration_min": group[
                    "estimated_duration_min"
                ].median(),
                "pressure_floor_observed_hours": hours,
                "stair_events_per_observed_hour": total_events / hours
                if hours
                else pd.NA,
            }
        )

    summary = pd.DataFrame(rows)
    all_dates = pd.DataFrame({"event_date": indoor_hours.index})
    summary = all_dates.merge(summary, on="event_date", how="left")
    summary["pressure_floor_observed_hours"] = summary[
        "pressure_floor_observed_hours"
    ].fillna(summary["event_date"].map(indoor_hours))
    fill_zero_cols = [
        "stair_events",
        "ascents",
        "descents",
        "acc_supported_events",
        "unsupported_events",
    ]
    summary[fill_zero_cols] = summary[fill_zero_cols].fillna(0).astype(int)
    summary["stair_events_per_observed_hour"] = summary.apply(
        lambda row: row["stair_events"] / row["pressure_floor_observed_hours"]
        if row["pressure_floor_observed_hours"]
        else pd.NA,
        axis=1,
    )
    return summary.sort_values("event_date")


def plot_stair_events(events, daily_summary):
    color_map = {"ascent": "#d62728", "descent": "#1f77b4", "unknown": "#7f7f7f"}
    y_map = {"descent": 0, "ascent": 1}

    fig, ax = plt.subplots(figsize=(12.5, 3.8))

    for direction, group in events.groupby("stair_direction"):
        ax.scatter(
            group["shift_time"],
            group["stair_direction"].map(y_map),
            s=48,
            color=color_map.get(direction, "#7f7f7f"),
            label=direction,
        )
    unsupported = events["unsupported_floor_shift_candidate"].fillna(False)
    ax.scatter(
        events.loc[unsupported, "shift_time"],
        events.loc[unsupported, "stair_direction"].map(y_map),
        s=92,
        facecolors="none",
        edgecolors="black",
        linewidths=1.2,
        label="ACC unsupported",
    )
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Descent 2F->1F", "Ascent 1F->2F"])
    ax.set_title("Pressure-derived stair ascent/descent events")
    ax.set_ylabel("Event type")
    ax.set_xlabel("Time")
    ax.grid(axis="x", alpha=0.22)
    ax.legend(loc="upper left", fontsize=8)

    x_min = events["shift_time"].min()
    x_max = events["shift_time"].max()
    padding = pd.Timedelta(hours=3)
    ax.set_xlim(x_min - padding, x_max + padding)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return PLOT_OUTPUT


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    floor_timeline, shift_support, acc_features = load_inputs()
    events = build_stair_events(shift_support, acc_features)
    duration_details = build_duration_details(events)
    daily_summary = build_daily_summary(events, floor_timeline)

    events.to_csv(EVENTS_OUTPUT, index=False)
    duration_details.to_csv(DURATION_DETAILS_OUTPUT, index=False)
    daily_summary.to_csv(DAILY_SUMMARY_OUTPUT, index=False)
    plot_path = plot_stair_events(events, daily_summary)

    print("Stair event quantification complete")
    print("Saved outputs:")
    for output in [EVENTS_OUTPUT, DURATION_DETAILS_OUTPUT, DAILY_SUMMARY_OUTPUT, plot_path]:
        print(output)
    print("\nEvent counts:")
    print(
        events["stair_direction"]
        .value_counts()
        .rename_axis("stair_direction")
        .reset_index(name="event_count")
        .to_string(index=False)
    )
    print("\nDaily summary:")
    print(daily_summary.to_string(index=False))
    print("\nDuration/window anomalies:")
    anomaly_rows = duration_details.loc[
        duration_details["any_duration_or_window_anomaly"]
    ]
    if anomaly_rows.empty:
        print("No long-duration or support-window anomalies detected.")
    else:
        print(
            anomaly_rows[
                [
                    "shift_time",
                    "stair_direction",
                    "estimated_duration_min",
                    "support_window_duration_min",
                    "floor_shift_acc_supported",
                    "duration_anomaly_explanation",
                    "acc_support_explanation",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
