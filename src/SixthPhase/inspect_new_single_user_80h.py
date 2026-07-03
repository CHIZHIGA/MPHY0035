import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data" / "New data- 80 hour single user"
RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

USER_DIR = DATA_DIR / "559662"

SENSOR_FILES = [
    "BEACONS_RSSI.csv",
    "BEACONS_PRESSURE.csv",
    "BEACONS_TEMPERATURE.csv",
    "BEACONS_HUMIDITY_PERCENT.csv",
    "BEACONS_LIGHT.csv",
    "BEACONS_AUDIO_NOISE_RMS.csv",
    "HE_ACC.csv",
    "GYRO.csv",
    "PRESSURE.csv",
]


def load_csv(path):
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).copy()
    frame["time"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.sort_values("time")


def median_interval_minutes(frame):
    diffs = frame["time"].diff().dropna().dt.total_seconds() / 60
    return diffs.median() if not diffs.empty else np.nan


def expected_rows(frame, median_minutes):
    if frame.empty or pd.isna(median_minutes) or median_minutes <= 0:
        return np.nan
    duration_minutes = (
        frame["time"].max() - frame["time"].min()
    ).total_seconds() / 60
    return int(np.floor(duration_minutes / median_minutes)) + 1


def availability_summary():
    rows = []
    loaded = {}
    for filename in SENSOR_FILES:
        path = USER_DIR / filename
        if not path.exists():
            rows.append(
                {
                    "sensor_file": filename,
                    "exists": False,
                    "rows": 0,
                    "start_time": "",
                    "end_time": "",
                    "duration_hours": np.nan,
                    "median_interval_minutes": np.nan,
                    "expected_rows": np.nan,
                    "coverage_fraction": np.nan,
                    "data_columns": "",
                }
            )
            continue

        frame = load_csv(path)
        loaded[filename] = frame
        median_minutes = median_interval_minutes(frame)
        expected = expected_rows(frame, median_minutes)
        duration_hours = (
            (frame["time"].max() - frame["time"].min()).total_seconds() / 3600
            if len(frame)
            else np.nan
        )
        rows.append(
            {
                "sensor_file": filename,
                "exists": True,
                "rows": len(frame),
                "start_time": frame["time"].min(),
                "end_time": frame["time"].max(),
                "duration_hours": duration_hours,
                "median_interval_minutes": median_minutes,
                "expected_rows": expected,
                "coverage_fraction": len(frame) / expected
                if expected and expected > 0
                else np.nan,
                "data_columns": ", ".join(
                    column for column in frame.columns if column not in {"timestamp", "time"}
                ),
            }
        )
    return pd.DataFrame(rows), loaded


def beacon_rssi_summary(rssi):
    beacon_cols = [column for column in rssi.columns if column not in {"timestamp", "time"}]
    rows = []
    for beacon in beacon_cols:
        values = pd.to_numeric(rssi[beacon], errors="coerce")
        rows.append(
            {
                "beacon": beacon,
                "non_missing_rows": int(values.notna().sum()),
                "coverage_fraction": values.notna().mean(),
                "mean_rssi": values.mean(),
                "median_rssi": values.median(),
                "max_rssi": values.max(),
                "min_rssi": values.min(),
            }
        )
    return pd.DataFrame(rows)


def build_5min_features(rssi, acc=None, pressure=None):
    beacon_cols = [column for column in rssi.columns if column not in {"timestamp", "time"}]
    features = rssi[["time", *beacon_cols]].copy()
    rssi_values = features[beacon_cols].apply(pd.to_numeric, errors="coerce")
    features["strongest_beacon"] = rssi_values.idxmax(axis=1)
    features["strongest_rssi"] = rssi_values.max(axis=1)
    features["second_rssi"] = rssi_values.apply(
        lambda row: row.dropna().sort_values(ascending=False).iloc[1]
        if row.dropna().shape[0] >= 2
        else np.nan,
        axis=1,
    )
    features["strongest_second_gap"] = (
        features["strongest_rssi"] - features["second_rssi"]
    )
    features["rssi_available_beacons"] = rssi_values.notna().sum(axis=1)

    if acc is not None and "MAGNITUDE" in acc.columns:
        acc_frame = acc[["time", "MAGNITUDE"]].copy()
        acc_frame["window_start"] = acc_frame["time"].dt.floor("5min")
        acc_summary = (
            acc_frame.groupby("window_start")["MAGNITUDE"]
            .agg(acc_magnitude_mean="mean", acc_magnitude_std="std")
            .reset_index()
            .rename(columns={"window_start": "time"})
        )
        features = features.merge(acc_summary, on="time", how="left")

    if pressure is not None and "PRESSURE" in pressure.columns:
        pressure_frame = pressure[["time", "PRESSURE"]].copy()
        pressure_frame["window_start"] = pressure_frame["time"].dt.floor("5min")
        pressure_summary = (
            pressure_frame.groupby("window_start")["PRESSURE"]
            .agg(pressure_mean="mean", pressure_std="std")
            .reset_index()
            .rename(columns={"window_start": "time"})
        )
        features = features.merge(pressure_summary, on="time", how="left")

    return features


def plot_availability(summary):
    plot_data = summary.loc[summary["exists"]].copy()
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for index, row in plot_data.iterrows():
        ax.plot(
            [pd.to_datetime(row["start_time"]), pd.to_datetime(row["end_time"])],
            [index, index],
            linewidth=8,
            solid_capstyle="butt",
        )
    ax.set_yticks(plot_data.index)
    ax.set_yticklabels(plot_data["sensor_file"])
    ax.set_xlabel("Time")
    ax.set_title("New 80h single-user data: sensor availability")
    ax.grid(axis="x", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    output = RESULTS_DIR / "new80h_sensor_availability_timeline.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_rssi_overview(rssi):
    beacon_cols = [column for column in rssi.columns if column not in {"timestamp", "time"}]
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for beacon in beacon_cols:
        axes[0].plot(rssi["time"], pd.to_numeric(rssi[beacon], errors="coerce"), label=beacon)
    axes[0].set_ylabel("Mean RSSI")
    axes[0].set_title("Beacon RSSI time series")
    axes[0].legend(title="Beacon", ncol=len(beacon_cols), loc="lower left")
    axes[0].grid(alpha=0.2)

    rssi_values = rssi[beacon_cols].apply(pd.to_numeric, errors="coerce")
    strongest = rssi_values.idxmax(axis=1)
    beacon_order = {beacon: idx for idx, beacon in enumerate(beacon_cols)}
    axes[1].scatter(
        rssi["time"],
        strongest.map(beacon_order),
        c=strongest.map(beacon_order),
        cmap="tab10",
        s=12,
    )
    axes[1].set_yticks(list(beacon_order.values()))
    axes[1].set_yticklabels(list(beacon_order.keys()))
    axes[1].set_ylabel("Strongest beacon")
    axes[1].set_xlabel("Time")
    axes[1].grid(axis="x", alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    output = RESULTS_DIR / "new80h_beacon_rssi_overview.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_motion_pressure(acc, pressure):
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.2), sharex=True)
    if acc is not None and "MAGNITUDE" in acc.columns:
        axes[0].plot(acc["time"], pd.to_numeric(acc["MAGNITUDE"], errors="coerce"), linewidth=0.8)
    axes[0].set_ylabel("ACC magnitude")
    axes[0].set_title("Bracelet movement and pressure")
    axes[0].grid(alpha=0.2)

    if pressure is not None and "PRESSURE" in pressure.columns:
        axes[1].plot(
            pressure["time"],
            pd.to_numeric(pressure["PRESSURE"], errors="coerce"),
            linewidth=0.8,
            color="#4c78a8",
        )
    axes[1].set_ylabel("Pressure")
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    output = RESULTS_DIR / "new80h_motion_pressure_overview.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def main():
    summary, loaded = availability_summary()
    summary.to_csv(RESULTS_DIR / "new80h_data_availability_summary.csv", index=False)

    rssi = loaded.get("BEACONS_RSSI.csv")
    acc = loaded.get("HE_ACC.csv")
    pressure = loaded.get("PRESSURE.csv")

    outputs = [plot_availability(summary)]
    if rssi is not None:
        rssi_summary = beacon_rssi_summary(rssi)
        rssi_summary.to_csv(RESULTS_DIR / "new80h_beacon_rssi_summary.csv", index=False)
        features = build_5min_features(rssi, acc=acc, pressure=pressure)
        features.to_csv(RESULTS_DIR / "new80h_5min_sensor_features.csv", index=False)
        outputs.append(plot_rssi_overview(rssi))
    if acc is not None or pressure is not None:
        outputs.append(plot_motion_pressure(acc, pressure))

    print("New 80h single-user data quick look")
    print("Data directory:", USER_DIR)
    print("\nAvailability summary:")
    print(
        summary[
            [
                "sensor_file",
                "rows",
                "start_time",
                "end_time",
                "duration_hours",
                "median_interval_minutes",
                "coverage_fraction",
            ]
        ].to_string(index=False)
    )
    if rssi is not None:
        print("\nBeacon RSSI summary:")
        print(rssi_summary.to_string(index=False))
    print("\nSaved outputs:")
    for path in [
        RESULTS_DIR / "new80h_data_availability_summary.csv",
        RESULTS_DIR / "new80h_beacon_rssi_summary.csv",
        RESULTS_DIR / "new80h_5min_sensor_features.csv",
        *outputs,
    ]:
        if path.exists():
            print(path)


if __name__ == "__main__":
    main()
