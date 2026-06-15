import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_X001")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "X001")
os.makedirs(RESULTS_DIR, exist_ok=True)

SIDES = ["LEFT_WRIST", "RIGHT_WRIST"]
WINDOW = "10min"
ACC_CHUNKSIZE = 1_000_000

AVAILABILITY_PATH = os.path.join(RESULTS_DIR, "X001_data_availability_summary.csv")
FEATURES_PATH = os.path.join(RESULTS_DIR, "X001_10min_sensor_features.csv")
COMPARISON_PATH = os.path.join(RESULTS_DIR, "X001_left_right_comparison_summary.csv")

AVAILABILITY_FIG = os.path.join(RESULTS_DIR, "X001_data_availability_timeline.png")
BEACON_FIG = os.path.join(RESULTS_DIR, "X001_beacon_detection_summary.png")
MOVEMENT_FIG = os.path.join(RESULTS_DIR, "X001_left_right_movement_comparison.png")
RSSI_LOCATION_FIG = os.path.join(RESULTS_DIR, "X001_left_right_rssi_location_comparison.png")
CONFIDENCE_FIG = os.path.join(RESULTS_DIR, "X001_rssi_confidence_comparison.png")

SENSOR_FILES = {
    "tags": ("SAMPLES_tags.csv", True),
    "step_count": ("SAMPLES_Step_count.csv", False),
    "he_acc": ("SAMPLES_HE_ACC.csv", False),
    "pressure": ("SAMPLES_PRESSURE.csv", False),
}

OTHER_TAG_CODE_MAP = {
    "08": "08E5",
    "19": "1933",
    "25": "2501",
    "71": "714C",
    "74": "747F",
    "9E": "9EDA",
    "D4": "D496",
}


def read_metadata(side):
    path = os.path.join(DATA_DIR, side, "metadata_subject.json")
    with open(path, "r") as f:
        return json.load(f)


def active_beacon_location(beacon_rows, beacon_id, timestamp):
    rows = beacon_rows.loc[beacon_rows["beacon_id"] == beacon_id]
    if rows.empty:
        return "Unmapped"

    timestamp_sec = int(timestamp.timestamp())
    active = rows.loc[
        (rows["start_date"] <= timestamp_sec)
        & ((rows["end_date"] == 0) | (rows["end_date"] > timestamp_sec))
    ]
    if active.empty:
        return "Unmapped"
    return active.iloc[-1]["location"]


def parse_other_tags(value):
    if pd.isna(value):
        return []

    records = []
    for item in str(value).split(";"):
        parts = item.strip().split()
        if len(parts) != 2:
            continue
        rssi_text, code = parts
        beacon_id = OTHER_TAG_CODE_MAP.get(code.upper())
        if beacon_id is None:
            beacon_id = f"External_{code.upper()}"
        try:
            rssi = float(rssi_text)
        except ValueError:
            continue
        records.append((beacon_id, rssi))
    return records


def sensor_time_range(side, sensor_name, file_name, has_header):
    path = os.path.join(DATA_DIR, side, file_name)
    if has_header:
        frame = pd.read_csv(
            path,
            usecols=["timestamp"],
            low_memory=False,
            on_bad_lines="skip",
        )
        timestamp = pd.to_numeric(frame["timestamp"], errors="coerce").dropna()
    else:
        frame = pd.read_csv(path, header=None, usecols=[0], names=["timestamp"])
        timestamp = pd.to_numeric(frame["timestamp"], errors="coerce").dropna()

    start = pd.to_datetime(timestamp.min(), unit="ms")
    end = pd.to_datetime(timestamp.max(), unit="ms")
    duration_hours = (end - start).total_seconds() / 3600
    return {
        "side": side,
        "sensor": sensor_name,
        "rows": len(timestamp),
        "start_time": start,
        "end_time": end,
        "duration_hours": duration_hours,
        "rows_per_hour": len(timestamp) / duration_hours if duration_hours > 0 else np.nan,
    }


def build_availability_summary():
    rows = []
    for side in SIDES:
        metadata = read_metadata(side)
        for sensor_name, (file_name, has_header) in SENSOR_FILES.items():
            row = sensor_time_range(side, sensor_name, file_name, has_header)
            row["subject_type"] = metadata.get("subject_type")
            row["device_position"] = metadata.get("device_position")
            row["timezone"] = metadata.get("timezone")
            rows.append(row)

    availability = pd.DataFrame(rows)
    common_start = availability.groupby("side")["start_time"].max().max()
    common_end = availability.groupby("side")["end_time"].min().min()
    availability["common_overlap_start"] = common_start
    availability["common_overlap_end"] = common_end
    common_hours = max((common_end - common_start).total_seconds() / 3600, 0)
    availability["common_overlap_hours"] = common_hours
    availability["common_overlap_fraction_of_sensor_span"] = (
        common_hours / availability["duration_hours"]
    ).clip(lower=0, upper=1)
    return availability


def load_rssi_samples(side):
    path = os.path.join(DATA_DIR, side, "SAMPLES_tags.csv")
    tags = pd.read_csv(
        path,
        usecols=["timestamp", "uuid", "rssi", "info_other_tags"],
        low_memory=False,
        on_bad_lines="skip",
    )
    tags["timestamp"] = pd.to_numeric(tags["timestamp"], errors="coerce")
    tags["rssi"] = pd.to_numeric(tags["rssi"], errors="coerce")
    tags = tags.dropna(subset=["timestamp", "uuid", "rssi"])
    tags["time"] = pd.to_datetime(tags["timestamp"], unit="ms")
    tags["beacon_id"] = tags["uuid"].astype(str).str.upper()

    records = tags[["time", "beacon_id", "rssi"]].copy()

    other_records = []
    for row in tags.itertuples(index=False):
        for beacon_id, rssi in parse_other_tags(row.info_other_tags):
            other_records.append(
                {
                    "time": row.time,
                    "beacon_id": beacon_id,
                    "rssi": rssi,
                }
            )
    if other_records:
        records = pd.concat([records, pd.DataFrame(other_records)], ignore_index=True)

    records["side"] = side
    return records.sort_values("time")


def build_rssi_windows(side, samples):
    metadata = read_metadata(side)
    beacon_rows = pd.DataFrame(metadata.get("beacons", []))

    pivot = samples.pivot_table(
        index="time",
        columns="beacon_id",
        values="rssi",
        aggfunc="mean",
    ).sort_index()

    mean_rssi = pivot.resample(WINDOW).mean().dropna(how="all")
    counts = pivot.resample(WINDOW).count().reindex(mean_rssi.index)
    total_samples = counts.sum(axis=1)
    strongest_beacon = mean_rssi.idxmax(axis=1)
    strongest_rssi = mean_rssi.max(axis=1)
    second_rssi = mean_rssi.apply(
        lambda row: row.dropna().sort_values(ascending=False).iloc[1]
        if row.dropna().shape[0] >= 2
        else np.nan,
        axis=1,
    )
    strongest_second_gap = strongest_rssi - second_rssi

    prop_rows = []
    for start, window_frame in pivot.resample(WINDOW):
        if window_frame.empty:
            continue
        winners = window_frame.idxmax(axis=1).dropna()
        counts_norm = winners.value_counts(normalize=True)
        prop_rows.append(
            {
                "time": start,
                "strongest_beacon_proportion": (
                    counts_norm.max() if not counts_norm.empty else np.nan
                ),
            }
        )

    props = pd.DataFrame(prop_rows).set_index("time")
    windows = pd.DataFrame(
        {
            "time": mean_rssi.index,
            "side": side,
            "strongest_beacon": strongest_beacon.values,
            "strongest_rssi": strongest_rssi.values,
            "strongest_second_gap": strongest_second_gap.values,
            "total_rssi_samples": total_samples.values,
        }
    ).set_index("time")
    windows = windows.join(props, how="left")
    windows = windows.loc[windows["total_rssi_samples"] > 0].copy()

    windows["strongest_location"] = [
        active_beacon_location(beacon_rows, beacon, timestamp)
        for timestamp, beacon in zip(windows.index, windows["strongest_beacon"])
    ]
    windows["rssi_confidence_score"] = (
        0.60 * windows["strongest_beacon_proportion"].fillna(0).clip(0, 1)
        + 0.40 * (windows["strongest_second_gap"].fillna(0).clip(0, 15) / 15)
    )
    windows["mapped_location_available"] = windows["strongest_location"].ne("Unmapped")
    return windows.reset_index()


def build_step_windows(side):
    path = os.path.join(DATA_DIR, side, "SAMPLES_Step_count.csv")
    steps = pd.read_csv(
        path,
        header=None,
        names=["timestamp", "timestamp_str", "step_count"],
    )
    steps["time"] = pd.to_datetime(pd.to_numeric(steps["timestamp"], errors="coerce"), unit="ms")
    steps["step_count"] = pd.to_numeric(steps["step_count"], errors="coerce")
    steps = steps.dropna(subset=["time", "step_count"]).sort_values("time").set_index("time")
    diff = steps["step_count"].diff().fillna(0)
    steps["step_reset_flag"] = diff < 0
    steps["step_increment"] = diff.clip(lower=0)
    windows = steps.resample(WINDOW).agg(
        steps_in_window=("step_increment", "sum"),
        step_samples=("step_count", "count"),
        step_resets=("step_reset_flag", "sum"),
    )
    windows["side"] = side
    return windows.reset_index()


def build_acc_windows(side):
    path = os.path.join(DATA_DIR, side, "SAMPLES_HE_ACC.csv")
    partials = []
    for chunk in pd.read_csv(
        path,
        header=None,
        names=["timestamp", "timestamp_str", "acc_x", "acc_y", "acc_z"],
        chunksize=ACC_CHUNKSIZE,
    ):
        chunk["time"] = pd.to_datetime(
            pd.to_numeric(chunk["timestamp"], errors="coerce"),
            unit="ms",
        )
        acc_x = pd.to_numeric(chunk["acc_x"], errors="coerce")
        acc_y = pd.to_numeric(chunk["acc_y"], errors="coerce")
        acc_z = pd.to_numeric(chunk["acc_z"], errors="coerce")
        acc_mag = np.sqrt(acc_x.pow(2) + acc_y.pow(2) + acc_z.pow(2))
        frame = pd.DataFrame(
            {
                "time": chunk["time"],
                "acc_mag": acc_mag,
                "acc_mag_sq": acc_mag.pow(2),
            }
        ).dropna(subset=["time", "acc_mag"])
        grouped = frame.set_index("time").resample(WINDOW).agg(
            acc_count=("acc_mag", "count"),
            acc_sum=("acc_mag", "sum"),
            acc_sumsq=("acc_mag_sq", "sum"),
            acc_min=("acc_mag", "min"),
            acc_max=("acc_mag", "max"),
        )
        partials.append(grouped)

    combined = pd.concat(partials).groupby(level=0).agg(
        acc_count=("acc_count", "sum"),
        acc_sum=("acc_sum", "sum"),
        acc_sumsq=("acc_sumsq", "sum"),
        acc_min=("acc_min", "min"),
        acc_max=("acc_max", "max"),
    )
    combined["acc_mean"] = combined["acc_sum"] / combined["acc_count"]
    variance = combined["acc_sumsq"] / combined["acc_count"] - combined["acc_mean"].pow(2)
    combined["acc_std"] = np.sqrt(variance.clip(lower=0))
    combined["acc_range"] = combined["acc_max"] - combined["acc_min"]
    combined["side"] = side
    return combined.reset_index()


def build_features():
    all_features = []
    beacon_summaries = []
    for side in SIDES:
        rssi_samples = load_rssi_samples(side)
        beacon_summary = (
            rssi_samples.groupby(["side", "beacon_id"])["rssi"]
            .agg(detections="count", mean_rssi="mean", min_rssi="min", max_rssi="max")
            .reset_index()
        )
        beacon_summaries.append(beacon_summary)

        rssi_windows = build_rssi_windows(side, rssi_samples)
        step_windows = build_step_windows(side)
        acc_windows = build_acc_windows(side)

        features = rssi_windows.merge(step_windows, on=["time", "side"], how="outer")
        features = features.merge(acc_windows, on=["time", "side"], how="outer")
        features["window"] = WINDOW
        features["steps_in_window"] = features["steps_in_window"].fillna(0)
        features["step_samples"] = features["step_samples"].fillna(0)
        features["step_resets"] = features["step_resets"].fillna(0)
        features["movement_intensity"] = features["acc_std"]
        all_features.append(features)

    return pd.concat(all_features, ignore_index=True), pd.concat(beacon_summaries, ignore_index=True)


def compare_left_right(features):
    left = features.loc[features["side"] == "LEFT_WRIST"].set_index("time")
    right = features.loc[features["side"] == "RIGHT_WRIST"].set_index("time")
    common_index = left.index.intersection(right.index)
    left = left.loc[common_index]
    right = right.loc[common_index]

    comparable_location = left["strongest_location"].notna() & right["strongest_location"].notna()
    same_beacon = left["strongest_beacon"].eq(right["strongest_beacon"])
    same_location = left["strongest_location"].eq(right["strongest_location"])

    comparison = pd.DataFrame(
        [
            {
                "common_10min_windows": len(common_index),
                "common_start_time": common_index.min() if len(common_index) else pd.NaT,
                "common_end_time": common_index.max() if len(common_index) else pd.NaT,
                "same_strongest_beacon_fraction": same_beacon.mean(),
                "same_mapped_location_fraction": same_location.loc[comparable_location].mean(),
                "step_count_correlation": left["steps_in_window"].corr(right["steps_in_window"]),
                "movement_intensity_correlation": left["movement_intensity"].corr(
                    right["movement_intensity"]
                ),
                "rssi_confidence_correlation": left["rssi_confidence_score"].corr(
                    right["rssi_confidence_score"]
                ),
                "left_high_conf_right_low_count": int(
                    (
                        left["rssi_confidence_score"].ge(0.70)
                        & right["rssi_confidence_score"].lt(0.40)
                    ).sum()
                ),
                "right_high_conf_left_low_count": int(
                    (
                        right["rssi_confidence_score"].ge(0.70)
                        & left["rssi_confidence_score"].lt(0.40)
                    ).sum()
                ),
            }
        ]
    )
    return comparison


def plot_availability(availability):
    fig, ax = plt.subplots(figsize=(12, 4.8))
    y_labels = []
    y_positions = []
    for idx, row in availability.sort_values(["side", "sensor"]).reset_index(drop=True).iterrows():
        y_labels.append(f"{row['side']} {row['sensor']}")
        y_positions.append(idx)
        ax.plot(
            [row["start_time"], row["end_time"]],
            [idx, idx],
            linewidth=8,
            solid_capstyle="butt",
        )
    common_start = availability["common_overlap_start"].iloc[0]
    common_end = availability["common_overlap_end"].iloc[0]
    ax.axvspan(common_start, common_end, color="grey", alpha=0.15, label="Common overlap")
    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels)
    ax.set_title("Home_X001 Sensor Availability Timeline")
    ax.set_xlabel("Time")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper right")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(AVAILABILITY_FIG, dpi=200)
    plt.close(fig)


def plot_beacon_summary(beacon_summary):
    top = beacon_summary.sort_values("detections", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, side in zip(axes, SIDES):
        data = top.loc[top["side"] == side].head(12).sort_values("detections")
        ax.barh(data["beacon_id"], data["detections"], color="#4C78A8")
        ax2 = ax.twiny()
        ax2.plot(data["mean_rssi"], data["beacon_id"], color="#F58518", marker="o")
        ax.set_title(f"{side}: beacon detections and mean RSSI")
        ax.set_xlabel("Detections")
        ax2.set_xlabel("Mean RSSI")
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle("Home_X001 Beacon Detection Summary", y=1.02)
    fig.tight_layout()
    fig.savefig(BEACON_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_movement(features):
    fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    for side in SIDES:
        data = features.loc[features["side"] == side].sort_values("time")
        axes[0].plot(data["time"], data["steps_in_window"], label=side, linewidth=1.2)
        axes[1].plot(data["time"], data["movement_intensity"], label=side, linewidth=1.2)
    axes[0].set_title("10min Step Count")
    axes[0].set_ylabel("Steps")
    axes[1].set_title("10min Accelerometer Movement Intensity")
    axes[1].set_ylabel("Acceleration std")
    axes[1].set_xlabel("Time")
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.legend()
    fig.suptitle("Home_X001 Left/Right Movement Comparison", y=0.98)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(MOVEMENT_FIG, dpi=200)
    plt.close(fig)


def plot_rssi_location(features):
    locations = sorted(features["strongest_location"].dropna().unique())
    location_codes = {location: idx for idx, location in enumerate(locations)}
    fig, axes = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    for ax, side in zip(axes, SIDES):
        data = features.loc[features["side"] == side].sort_values("time").copy()
        data["location_code"] = data["strongest_location"].map(location_codes)
        ax.scatter(
            data["time"],
            data["location_code"],
            s=10,
            c=data["rssi_confidence_score"],
            cmap="viridis",
            vmin=0,
            vmax=1,
        )
        ax.set_title(f"{side}: strongest RSSI mapped location")
        ax.set_yticks(list(location_codes.values()))
        ax.set_yticklabels(list(location_codes.keys()))
        ax.grid(alpha=0.2)
    fig.suptitle("Home_X001 Strongest Beacon / Mapped Location Timeline", y=0.98)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(RSSI_LOCATION_FIG, dpi=200)
    plt.close(fig)


def plot_confidence(features):
    fig, ax = plt.subplots(figsize=(14, 4.5))
    for side in SIDES:
        data = features.loc[features["side"] == side].sort_values("time")
        ax.plot(data["time"], data["rssi_confidence_score"], label=side, linewidth=1.2)
    ax.set_title("Home_X001 10min RSSI Confidence Comparison")
    ax.set_ylabel("RSSI confidence score")
    ax.set_xlabel("Time")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CONFIDENCE_FIG, dpi=200)
    plt.close(fig)


def main():
    print("Building Home_X001 availability summary...")
    availability = build_availability_summary()
    availability.to_csv(AVAILABILITY_PATH, index=False)

    print("Building 10min RSSI, step count, and accelerometer features...")
    features, beacon_summary = build_features()
    features.to_csv(FEATURES_PATH, index=False)

    print("Building left/right descriptive comparison...")
    comparison = compare_left_right(features)
    comparison.to_csv(COMPARISON_PATH, index=False)

    print("Drawing figures...")
    plot_availability(availability)
    plot_beacon_summary(beacon_summary)
    plot_movement(features)
    plot_rssi_location(features)
    plot_confidence(features)

    print("\nSaved CSV outputs:")
    print(AVAILABILITY_PATH)
    print(FEATURES_PATH)
    print(COMPARISON_PATH)
    print("\nSaved figures:")
    print(AVAILABILITY_FIG)
    print(BEACON_FIG)
    print(MOVEMENT_FIG)
    print(RSSI_LOCATION_FIG)
    print(CONFIDENCE_FIG)
    print("\nLeft/right descriptive comparison:")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
