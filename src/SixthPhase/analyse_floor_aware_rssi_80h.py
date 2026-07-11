import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "Results" / "SixthPhase" / "NewData80h"

SENSOR_FEATURES_PATH = RESULTS_DIR / "new80h_5min_sensor_features.csv"
FLOOR_TIMELINE_PATH = RESULTS_DIR / "new80h_pressure_inferred_floor_timeline_5min.csv"
SHIFT_SUPPORT_PATH = RESULTS_DIR / "new80h_pressure_floor_shift_acc_support.csv"
ACC_FEATURES_PATH = RESULTS_DIR / "new80h_acc_5min_features.csv"

CONSISTENCY_OUTPUT = RESULTS_DIR / "new80h_pressure_rssi_floor_consistency_5min.csv"
CONSISTENCY_PLOT_OUTPUT = (
    RESULTS_DIR / "new80h_pressure_rssi_floor_consistency_timeline.png"
)
MISMATCH_PLOT_OUTPUT = (
    RESULTS_DIR / "new80h_rssi_pressure_floor_mismatch_timeline.png"
)
FLOOR_AWARE_OUTPUT = RESULTS_DIR / "new80h_floor_aware_rssi_location_5min.csv"
FLOOR_AWARE_PLOT_OUTPUT = (
    RESULTS_DIR / "new80h_floor_aware_rssi_location_timeline.png"
)
RAW_VS_FLOOR_AWARE_PLOT_OUTPUT = (
    RESULTS_DIR / "new80h_raw_vs_pressure_acc_floor_aware_rssi_timeline.png"
)
TWO_LINE_BEACON_TIMELINE_OUTPUT = (
    RESULTS_DIR / "new80h_raw_vs_pressure_acc_floor_aware_rssi_two_line_timeline.png"
)
BRUTE_FORCE_TWO_LINE_TIMELINE_OUTPUT = (
    RESULTS_DIR
    / "new80h_raw_vs_pressure_floor_bruteforce_rssi_two_line_timeline.png"
)
BRUTE_FORCE_SUMMARY_OUTPUT = (
    RESULTS_DIR / "new80h_pressure_floor_bruteforce_rssi_switch_summary.csv"
)
SWITCH_SUMMARY_OUTPUT = RESULTS_DIR / "new80h_floor_aware_rssi_switch_summary.csv"

BEACON_TO_FLOOR = {
    "CA59": "1F",
    "1933": "1F",
    "D7FD": "2F",
    "3E05": "2F",
}
FLOOR_TO_BEACONS = {
    "1F": ["CA59", "1933"],
    "2F": ["D7FD", "3E05"],
}

FLOOR_TO_Y = {"1F": 1, "2F": 2}
BEACON_ORDER = ["CA59", "1933", "D7FD", "3E05"]
BEACON_TO_Y = {beacon: index for index, beacon in enumerate(BEACON_ORDER)}
BEACON_COLORS = {
    "CA59": "#2ca02c",
    "1933": "#1f77b4",
    "D7FD": "#d62728",
    "3E05": "#ff7f0e",
}

PRESSURE_CONFIDENCE_HIGH_THRESHOLD = 0.75


def load_inputs():
    sensor_features = pd.read_csv(SENSOR_FEATURES_PATH, parse_dates=["time"])
    floor_timeline = pd.read_csv(FLOOR_TIMELINE_PATH, parse_dates=["time"])
    acc_features = pd.read_csv(ACC_FEATURES_PATH, parse_dates=["time"])
    shift_support = pd.read_csv(SHIFT_SUPPORT_PATH, parse_dates=["shift_time"])
    for column in ["support_window_start", "support_window_end"]:
        if column in shift_support.columns:
            shift_support[column] = pd.to_datetime(shift_support[column], utc=True)
    return sensor_features, floor_timeline, acc_features, shift_support


def mark_acc_supported_shift_windows(frame, shift_support):
    updated = frame.copy()
    updated["near_acc_supported_floor_shift"] = False
    updated["near_unsupported_floor_shift"] = False

    for _, shift in shift_support.iterrows():
        window_mask = updated["time"].between(
            shift["support_window_start"], shift["support_window_end"]
        )
        if bool(shift["floor_shift_acc_supported"]):
            updated.loc[window_mask, "near_acc_supported_floor_shift"] = True
        else:
            updated.loc[window_mask, "near_unsupported_floor_shift"] = True
    return updated


def build_floor_aware_rssi_table(sensor_features, floor_timeline, acc_features, shift_support):
    keep_floor_cols = [
        "time",
        "pressure_inferred_floor_smoothed_label",
        "pressure_floor_confidence",
        "pressure_floor_margin_hpa",
        "pressure_floor_distance_hpa",
        "environmental_beacon_available",
        "long_environmental_data_gap",
        "confirmed_out_of_home",
        "pressure_floor_observed",
    ]
    merged = sensor_features.merge(floor_timeline[keep_floor_cols], on="time", how="left")
    merged = merged.merge(
        acc_features[
            [
                "time",
                "acc_magnitude_mean_clean",
                "acc_magnitude_std_clean",
                "acc_motion_score",
                "acc_spike_count_gt_1p2",
            ]
        ],
        on="time",
        how="left",
    )
    merged = mark_acc_supported_shift_windows(merged, shift_support)
    merged["rssi_gap_before_minutes"] = (
        merged["time"].diff().dt.total_seconds() / 60
    )
    merged["rssi_observation_contiguous"] = merged["time"].diff().eq(
        pd.Timedelta(minutes=5)
    )

    merged["rssi_strongest_beacon_floor"] = merged["strongest_beacon"].map(
        BEACON_TO_FLOOR
    )
    merged["rssi_pressure_floor_consistent"] = (
        merged["rssi_strongest_beacon_floor"]
        == merged["pressure_inferred_floor_smoothed_label"]
    )
    merged["pressure_confidence_high"] = merged["pressure_floor_confidence"].ge(
        PRESSURE_CONFIDENCE_HIGH_THRESHOLD
    )
    merged["pressure_acc_floor_trusted"] = (
        merged["pressure_confidence_high"] & ~merged["near_unsupported_floor_shift"]
    )

    same_floor_best_beacons = []
    same_floor_best_rssi = []
    for _, row in merged.iterrows():
        floor = row["pressure_inferred_floor_smoothed_label"]
        candidate_beacons = FLOOR_TO_BEACONS.get(floor, [])
        available = [
            beacon
            for beacon in candidate_beacons
            if beacon in merged.columns and pd.notna(row[beacon])
        ]
        if not available:
            same_floor_best_beacons.append(pd.NA)
            same_floor_best_rssi.append(np.nan)
            continue
        values = row[available].astype(float)
        best_beacon = values.idxmax()
        same_floor_best_beacons.append(best_beacon)
        same_floor_best_rssi.append(values[best_beacon])

    merged["same_floor_best_rssi_beacon"] = same_floor_best_beacons
    merged["same_floor_best_rssi"] = same_floor_best_rssi
    merged["pressure_acc_should_switch_to_same_floor_beacon"] = (
        ~merged["rssi_pressure_floor_consistent"].fillna(False)
        & merged["pressure_acc_floor_trusted"].fillna(False)
        & merged["same_floor_best_rssi_beacon"].notna()
    )
    merged["pressure_floor_bruteforce_should_switch"] = (
        ~merged["rssi_pressure_floor_consistent"].fillna(False)
        & merged["same_floor_best_rssi_beacon"].notna()
    )
    merged["pressure_floor_bruteforce_no_same_floor_candidate"] = (
        ~merged["rssi_pressure_floor_consistent"].fillna(False)
        & merged["same_floor_best_rssi_beacon"].isna()
    )

    conditions = [
        merged["rssi_pressure_floor_consistent"].fillna(False),
        merged["pressure_floor_confidence"].lt(PRESSURE_CONFIDENCE_HIGH_THRESHOLD),
        merged["near_unsupported_floor_shift"],
        merged["near_acc_supported_floor_shift"],
        merged["pressure_confidence_high"] & ~merged["near_acc_supported_floor_shift"],
    ]
    choices = [
        "floor_consistent",
        "pressure_uncertain",
        "acc_unsupported_floor_shift",
        "possible_cross_floor_transition",
        "floor_conflict",
    ]
    merged["floor_aware_rssi_status"] = np.select(
        conditions, choices, default="insufficient_floor_or_rssi"
    )
    merged["floor_aware_rssi_beacon"] = merged["strongest_beacon"]
    merged["floor_aware_rssi_floor"] = merged["rssi_strongest_beacon_floor"]
    merged["pressure_acc_floor_aware_rssi_beacon"] = merged["strongest_beacon"].mask(
        merged["pressure_acc_should_switch_to_same_floor_beacon"],
        merged["same_floor_best_rssi_beacon"],
    )
    merged["pressure_acc_floor_aware_rssi"] = merged["strongest_rssi"].mask(
        merged["pressure_acc_should_switch_to_same_floor_beacon"],
        merged["same_floor_best_rssi"],
    )
    merged["pressure_acc_floor_aware_rssi_floor"] = merged[
        "pressure_acc_floor_aware_rssi_beacon"
    ].map(BEACON_TO_FLOOR)
    merged["pressure_acc_floor_aware_changed"] = (
        merged["pressure_acc_floor_aware_rssi_beacon"] != merged["strongest_beacon"]
    ) & merged["pressure_acc_floor_aware_rssi_beacon"].notna()
    merged["pressure_acc_floor_aware_change_reason"] = np.select(
        [
            merged["pressure_acc_floor_aware_changed"],
            merged["rssi_pressure_floor_consistent"].fillna(False),
            merged["near_unsupported_floor_shift"],
            merged["pressure_floor_confidence"].lt(PRESSURE_CONFIDENCE_HIGH_THRESHOLD),
        ],
        [
            "switched_to_best_same_floor_beacon",
            "raw_rssi_already_same_floor",
            "kept_raw_due_to_acc_unsupported_shift",
            "kept_raw_due_to_low_pressure_confidence",
        ],
        default="kept_raw_no_same_floor_switch",
    )
    merged["pressure_floor_bruteforce_rssi_beacon"] = merged["strongest_beacon"].mask(
        merged["pressure_floor_bruteforce_should_switch"],
        merged["same_floor_best_rssi_beacon"],
    )
    merged["pressure_floor_bruteforce_rssi"] = merged["strongest_rssi"].mask(
        merged["pressure_floor_bruteforce_should_switch"],
        merged["same_floor_best_rssi"],
    )
    merged["pressure_floor_bruteforce_rssi_floor"] = merged[
        "pressure_floor_bruteforce_rssi_beacon"
    ].map(BEACON_TO_FLOOR)
    merged["pressure_floor_bruteforce_changed"] = (
        merged["pressure_floor_bruteforce_rssi_beacon"] != merged["strongest_beacon"]
    ) & merged["pressure_floor_bruteforce_rssi_beacon"].notna()
    merged["floor_aware_rssi_confidence_factor"] = merged[
        "floor_aware_rssi_status"
    ].map(
        {
            "floor_consistent": 1.0,
            "pressure_uncertain": 0.8,
            "possible_cross_floor_transition": 0.75,
            "floor_conflict": 0.5,
            "acc_unsupported_floor_shift": 0.55,
            "insufficient_floor_or_rssi": 0.5,
        }
    )
    merged["floor_aware_rssi_interpretation"] = merged["floor_aware_rssi_status"].map(
        {
            "floor_consistent": "RSSI strongest beacon is on the pressure-inferred floor",
            "pressure_uncertain": "Pressure floor confidence is low; keep RSSI but flag uncertainty",
            "possible_cross_floor_transition": "RSSI and pressure disagree near an ACC-supported floor shift",
            "floor_conflict": "RSSI and high-confidence pressure floor disagree without ACC shift support",
            "acc_unsupported_floor_shift": "Pressure floor shift lacks ACC support; keep raw RSSI",
            "insufficient_floor_or_rssi": "Missing floor or RSSI evidence",
        }
    )
    return merged


def build_consistency_table(floor_aware):
    columns = [
        "time",
        "strongest_beacon",
        "strongest_rssi",
        "second_rssi",
        "strongest_second_gap",
        "rssi_available_beacons",
        "rssi_strongest_beacon_floor",
        "pressure_inferred_floor_smoothed_label",
        "pressure_floor_confidence",
        "pressure_floor_margin_hpa",
        "environmental_beacon_available",
        "pressure_floor_observed",
        "rssi_gap_before_minutes",
        "rssi_observation_contiguous",
        "acc_motion_score",
        "near_acc_supported_floor_shift",
        "near_unsupported_floor_shift",
        "rssi_pressure_floor_consistent",
        "floor_aware_rssi_status",
        "same_floor_best_rssi_beacon",
        "same_floor_best_rssi",
        "pressure_acc_floor_trusted",
        "pressure_acc_floor_aware_rssi_beacon",
        "pressure_acc_floor_aware_changed",
        "pressure_acc_floor_aware_change_reason",
    ]
    return floor_aware[columns].copy()


def plot_consistency_timeline(consistency):
    status_colors = {
        "floor_consistent": "#2ca02c",
        "pressure_uncertain": "#8c6bb1",
        "possible_cross_floor_transition": "#ffbf00",
        "floor_conflict": "#d62728",
        "acc_unsupported_floor_shift": "#e377c2",
        "insufficient_floor_or_rssi": "#7f7f7f",
    }

    fig, axes = plt.subplots(3, 1, figsize=(13.5, 7.5), sharex=True)

    axes[0].step(
        consistency["time"],
        consistency["pressure_inferred_floor_smoothed_label"].map(FLOOR_TO_Y),
        where="mid",
        color="black",
        linewidth=1.2,
        label="Pressure floor",
    )
    axes[0].scatter(
        consistency["time"],
        consistency["rssi_strongest_beacon_floor"].map(FLOOR_TO_Y),
        c=consistency["floor_aware_rssi_status"].map(status_colors),
        s=16,
        label="RSSI strongest beacon floor",
    )
    axes[0].set_yticks([1, 2])
    axes[0].set_yticklabels(["1F: CA59/1933", "2F: D7FD/3E05"])
    axes[0].set_ylim(0.6, 2.4)
    axes[0].set_ylabel("Floor")
    axes[0].set_title("Pressure floor and strongest-RSSI floor consistency")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[0].grid(axis="x", alpha=0.2)

    status_y = {
        status: index for index, status in enumerate(status_colors.keys())
    }
    axes[1].scatter(
        consistency["time"],
        consistency["floor_aware_rssi_status"].map(status_y),
        c=consistency["floor_aware_rssi_status"].map(status_colors),
        s=16,
    )
    axes[1].set_yticks(list(status_y.values()))
    axes[1].set_yticklabels(list(status_y.keys()))
    axes[1].set_ylabel("Status")
    axes[1].grid(axis="x", alpha=0.2)

    rssi_line = axes[2].plot(
        consistency["time"],
        consistency["strongest_second_gap"],
        linewidth=1.0,
        label="RSSI strongest-second gap",
        color="#1f77b4",
    )[0]
    evidence_axis = axes[2].twinx()
    pressure_line = evidence_axis.plot(
        consistency["time"],
        consistency["pressure_floor_confidence"],
        linewidth=1.0,
        label="Pressure floor confidence",
        color="#ff7f0e",
    )[0]
    acc_line = evidence_axis.plot(
        consistency["time"],
        consistency["acc_motion_score"],
        linewidth=1.0,
        label="ACC motion score",
        color="#2ca02c",
    )[0]
    axes[2].set_ylabel("RSSI gap (dB)")
    evidence_axis.set_ylabel("Confidence / ACC score")
    evidence_axis.set_ylim(-0.05, 1.05)
    axes[2].set_xlabel("Time")
    axes[2].legend(
        [rssi_line, pressure_line, acc_line],
        [line.get_label() for line in [rssi_line, pressure_line, acc_line]],
        fontsize=8,
        ncol=3,
    )
    axes[2].grid(alpha=0.2)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CONSISTENCY_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return CONSISTENCY_PLOT_OUTPUT


def plot_mismatch_timeline(consistency):
    plot_data = consistency.copy()
    mismatch = ~plot_data["rssi_pressure_floor_consistent"].fillna(False)

    fig, axes = plt.subplots(3, 1, figsize=(13.5, 7.0), sharex=True)
    axes[0].step(
        plot_data["time"],
        plot_data["pressure_inferred_floor_smoothed_label"].map(FLOOR_TO_Y),
        where="mid",
        color="black",
        linewidth=1.2,
        label="Pressure floor",
    )
    axes[0].scatter(
        plot_data["time"],
        plot_data["rssi_strongest_beacon_floor"].map(FLOOR_TO_Y),
        c=np.where(mismatch, "#d62728", "#2ca02c"),
        s=18,
        label="RSSI strongest beacon floor",
    )
    axes[0].set_yticks([1, 2])
    axes[0].set_yticklabels(["1F: CA59/1933", "2F: D7FD/3E05"])
    axes[0].set_ylim(0.6, 2.4)
    axes[0].set_ylabel("Floor")
    axes[0].set_title("Windows where strongest RSSI disagrees with pressure floor")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[0].grid(axis="x", alpha=0.2)

    axes[1].scatter(
        plot_data.loc[mismatch, "time"],
        plot_data.loc[mismatch, "strongest_beacon"].map(BEACON_TO_Y),
        c="#d62728",
        s=22,
        label="Mismatch windows",
    )
    axes[1].scatter(
        plot_data.loc[~mismatch, "time"],
        plot_data.loc[~mismatch, "strongest_beacon"].map(BEACON_TO_Y),
        c="#c7c7c7",
        s=8,
        alpha=0.35,
        label="Consistent windows",
    )
    axes[1].set_yticks(list(BEACON_TO_Y.values()))
    axes[1].set_yticklabels(BEACON_ORDER)
    axes[1].set_ylabel("Raw strongest beacon")
    axes[1].legend(fontsize=8, loc="upper left")
    axes[1].grid(axis="x", alpha=0.2)

    axes[2].plot(
        plot_data["time"],
        plot_data["pressure_floor_confidence"],
        color="#ff7f0e",
        linewidth=1.0,
        label="Pressure confidence",
    )
    axes[2].scatter(
        plot_data.loc[mismatch, "time"],
        plot_data.loc[mismatch, "pressure_floor_confidence"],
        c="#d62728",
        s=22,
        label="Mismatch confidence",
    )
    axes[2].set_ylim(-0.05, 1.05)
    axes[2].set_ylabel("Pressure confidence")
    axes[2].set_xlabel("Time")
    axes[2].legend(fontsize=8, loc="upper left")
    axes[2].grid(alpha=0.2)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(MISMATCH_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return MISMATCH_PLOT_OUTPUT


def plot_floor_aware_rssi_timeline(floor_aware):
    status_colors = {
        "floor_consistent": "#2ca02c",
        "pressure_uncertain": "#8c6bb1",
        "possible_cross_floor_transition": "#ffbf00",
        "floor_conflict": "#d62728",
        "acc_unsupported_floor_shift": "#e377c2",
        "insufficient_floor_or_rssi": "#7f7f7f",
    }

    fig, axes = plt.subplots(3, 1, figsize=(13.5, 7.5), sharex=True)

    axes[0].scatter(
        floor_aware["time"],
        floor_aware["strongest_beacon"].map(BEACON_TO_Y),
        c=floor_aware["floor_aware_rssi_status"].map(status_colors),
        s=18,
        label="Original strongest RSSI beacon",
    )
    axes[0].set_yticks(list(BEACON_TO_Y.values()))
    axes[0].set_yticklabels(BEACON_ORDER)
    axes[0].set_ylabel("Strongest beacon")
    axes[0].set_title("Floor-aware interpretation of strongest RSSI")
    axes[0].grid(axis="x", alpha=0.2)
    axes[0].legend(fontsize=8, loc="upper left")

    axes[1].step(
        floor_aware["time"],
        floor_aware["pressure_inferred_floor_smoothed_label"].map(FLOOR_TO_Y),
        where="mid",
        color="black",
        linewidth=1.2,
        label="Pressure floor",
    )
    axes[1].scatter(
        floor_aware["time"],
        floor_aware["rssi_strongest_beacon_floor"].map(FLOOR_TO_Y),
        c=floor_aware["floor_aware_rssi_status"].map(status_colors),
        s=16,
        label="RSSI strongest beacon floor",
    )
    axes[1].set_yticks([1, 2])
    axes[1].set_yticklabels(["1F", "2F"])
    axes[1].set_ylim(0.6, 2.4)
    axes[1].set_ylabel("Floor")
    axes[1].grid(axis="x", alpha=0.2)
    axes[1].legend(fontsize=8, loc="upper left")

    rssi_line = axes[2].plot(
        floor_aware["time"],
        floor_aware["strongest_second_gap"],
        linewidth=1.0,
        label="RSSI gap",
        color="#1f77b4",
    )[0]
    evidence_axis = axes[2].twinx()
    pressure_line = evidence_axis.plot(
        floor_aware["time"],
        floor_aware["pressure_floor_confidence"],
        linewidth=1.0,
        label="Pressure confidence",
        color="#ff7f0e",
    )[0]
    factor_line = evidence_axis.plot(
        floor_aware["time"],
        floor_aware["floor_aware_rssi_confidence_factor"],
        linewidth=1.0,
        label="Floor-aware RSSI confidence factor",
        color="#2ca02c",
    )[0]
    axes[2].set_ylabel("RSSI gap (dB)")
    evidence_axis.set_ylabel("Confidence / factor")
    evidence_axis.set_ylim(-0.05, 1.05)
    axes[2].set_xlabel("Time")
    axes[2].legend(
        [rssi_line, pressure_line, factor_line],
        [line.get_label() for line in [rssi_line, pressure_line, factor_line]],
        fontsize=8,
        ncol=3,
    )
    axes[2].grid(alpha=0.2)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FLOOR_AWARE_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return FLOOR_AWARE_PLOT_OUTPUT


def plot_raw_vs_pressure_acc_floor_aware(floor_aware):
    changed = floor_aware["pressure_acc_floor_aware_changed"].fillna(False)
    fig, axes = plt.subplots(3, 1, figsize=(13.5, 7.4), sharex=True)

    axes[0].scatter(
        floor_aware["time"],
        floor_aware["strongest_beacon"].map(BEACON_TO_Y),
        c=np.where(changed, "#d62728", "#2ca02c"),
        s=18,
        label="Raw strongest RSSI beacon",
    )
    axes[0].set_yticks(list(BEACON_TO_Y.values()))
    axes[0].set_yticklabels(BEACON_ORDER)
    axes[0].set_ylabel("Raw RSSI")
    axes[0].set_title("Raw strongest RSSI vs pressure+ACC floor-aware RSSI")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[0].grid(axis="x", alpha=0.2)

    axes[1].scatter(
        floor_aware["time"],
        floor_aware["pressure_acc_floor_aware_rssi_beacon"].map(BEACON_TO_Y),
        c=np.where(changed, "#d62728", "#2ca02c"),
        s=18,
        label="Pressure+ACC floor-aware beacon",
    )
    axes[1].set_yticks(list(BEACON_TO_Y.values()))
    axes[1].set_yticklabels(BEACON_ORDER)
    axes[1].set_ylabel("Adjusted RSSI")
    axes[1].legend(fontsize=8, loc="upper left")
    axes[1].grid(axis="x", alpha=0.2)

    axes[2].step(
        floor_aware["time"],
        floor_aware["pressure_inferred_floor_smoothed_label"].map(FLOOR_TO_Y),
        where="mid",
        color="black",
        linewidth=1.2,
        label="Pressure floor",
    )
    axes[2].scatter(
        floor_aware.loc[changed, "time"],
        floor_aware.loc[changed, "pressure_inferred_floor_smoothed_label"].map(
            FLOOR_TO_Y
        ),
        c="#d62728",
        s=24,
        label="Changed windows",
    )
    axes[2].set_yticks([1, 2])
    axes[2].set_yticklabels(["1F", "2F"])
    axes[2].set_ylim(0.6, 2.4)
    axes[2].set_ylabel("Pressure floor")
    axes[2].set_xlabel("Time")
    axes[2].legend(fontsize=8, loc="upper left")
    axes[2].grid(axis="x", alpha=0.2)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(RAW_VS_FLOOR_AWARE_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return RAW_VS_FLOOR_AWARE_PLOT_OUTPUT


def plot_two_line_beacon_timeline(floor_aware):
    plot_data = floor_aware.sort_values("time").copy()
    plot_data["window_end"] = plot_data["time"].shift(-1)
    median_step = plot_data["time"].diff().median()
    if pd.isna(median_step):
        median_step = pd.Timedelta(minutes=5)
    plot_data["window_end"] = plot_data["window_end"].fillna(
        plot_data["time"] + median_step
    )
    changed = plot_data["pressure_acc_floor_aware_changed"].fillna(False)
    mismatch = ~plot_data["rssi_pressure_floor_consistent"].fillna(False)
    unchanged_mismatch = mismatch & ~changed

    rows = [
        ("Raw strongest RSSI", "strongest_beacon", 2),
        (
            "Pressure+ACC floor-aware RSSI",
            "pressure_acc_floor_aware_rssi_beacon",
            1,
        ),
    ]

    fig, ax = plt.subplots(figsize=(14, 4.6))
    for _, row in plot_data.iterrows():
        for _, column, y in rows:
            beacon = row[column]
            color = BEACON_COLORS.get(beacon, "#9d9da1")
            ax.plot(
                [row["time"], row["window_end"]],
                [y, y],
                color=color,
                linewidth=9,
                solid_capstyle="butt",
            )

    correction_rows = plot_data.loc[changed]
    unchanged_mismatch_rows = plot_data.loc[unchanged_mismatch]
    for row in correction_rows.itertuples(index=False):
        ax.axvline(row.time, color="#111111", linestyle=":", linewidth=0.8, alpha=0.35)

    for _, column, y in rows:
        ax.scatter(
            correction_rows["time"],
            np.full(len(correction_rows), y),
            s=58,
            facecolors="none",
            edgecolors="#111111",
            linewidths=1.4,
            zorder=5,
        label="_nolegend_",
        )

    ax.scatter(
        unchanged_mismatch_rows["time"],
        np.full(len(unchanged_mismatch_rows), 2),
        s=46,
        facecolors="none",
        edgecolors="#6f6f6f",
        linewidths=1.1,
        zorder=5,
        label="_nolegend_",
    )

    ax.scatter(
        correction_rows["time"],
        np.full(len(correction_rows), 1.5),
        s=28,
        marker="v",
        color="#111111",
        zorder=6,
        label="Corrected 5-min windows",
    )

    ax.set_yticks([2, 1])
    ax.set_yticklabels([label for label, _, _ in rows])
    ax.set_ylim(0.45, 2.55)
    ax.set_title(
        "Raw strongest RSSI and pressure+ACC floor-aware RSSI beacon timeline"
    )
    ax.grid(axis="x", alpha=0.22)

    beacon_handles = [
        plt.Line2D(
            [0],
            [0],
            color=BEACON_COLORS[beacon],
            linewidth=8,
            label=f"{beacon} ({BEACON_TO_FLOOR[beacon]})",
        )
        for beacon in BEACON_ORDER
    ]
    correction_handle = plt.Line2D(
        [0],
        [0],
        marker="v",
        color="#111111",
        linestyle="None",
        markersize=6,
        label=f"Corrected windows ({int(changed.sum())})",
    )
    unchanged_mismatch_handle = plt.Line2D(
        [0],
        [0],
        marker="o",
        markerfacecolor="none",
        markeredgecolor="#6f6f6f",
        linestyle="None",
        markersize=7,
        label=f"Unchanged mismatch windows ({int(unchanged_mismatch.sum())})",
    )
    ax.legend(
        handles=beacon_handles + [correction_handle, unchanged_mismatch_handle],
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title="Beacon",
    )

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(TWO_LINE_BEACON_TIMELINE_OUTPUT, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return TWO_LINE_BEACON_TIMELINE_OUTPUT


def plot_bruteforce_two_line_beacon_timeline(floor_aware):
    plot_data = floor_aware.sort_values("time").copy()
    plot_data["window_end"] = plot_data["time"].shift(-1)
    median_step = plot_data["time"].diff().median()
    if pd.isna(median_step):
        median_step = pd.Timedelta(minutes=5)
    plot_data["window_end"] = plot_data["window_end"].fillna(
        plot_data["time"] + median_step
    )
    changed = plot_data["pressure_floor_bruteforce_changed"].fillna(False)
    no_candidate = plot_data[
        "pressure_floor_bruteforce_no_same_floor_candidate"
    ].fillna(False)

    rows = [
        ("Raw strongest RSSI", "strongest_beacon", 2),
        (
            "Pressure-floor brute-force RSSI",
            "pressure_floor_bruteforce_rssi_beacon",
            1,
        ),
    ]

    fig, ax = plt.subplots(figsize=(14, 4.6))
    for _, row in plot_data.iterrows():
        for _, column, y in rows:
            beacon = row[column]
            color = BEACON_COLORS.get(beacon, "#9d9da1")
            ax.plot(
                [row["time"], row["window_end"]],
                [y, y],
                color=color,
                linewidth=9,
                solid_capstyle="butt",
            )

    changed_rows = plot_data.loc[changed]
    no_candidate_rows = plot_data.loc[no_candidate]
    for row in changed_rows.itertuples(index=False):
        ax.axvline(row.time, color="#111111", linestyle=":", linewidth=0.8, alpha=0.35)

    for _, column, y in rows:
        ax.scatter(
            changed_rows["time"],
            np.full(len(changed_rows), y),
            s=58,
            facecolors="none",
            edgecolors="#111111",
            linewidths=1.4,
            zorder=5,
            label="_nolegend_",
        )

    ax.scatter(
        changed_rows["time"],
        np.full(len(changed_rows), 1.5),
        s=28,
        marker="v",
        color="#111111",
        zorder=6,
        label="_nolegend_",
    )
    ax.scatter(
        no_candidate_rows["time"],
        np.full(len(no_candidate_rows), 2),
        s=72,
        marker="x",
        color="#7f7f7f",
        linewidths=1.5,
        zorder=6,
        label="_nolegend_",
    )

    ax.set_yticks([2, 1])
    ax.set_yticklabels([label for label, _, _ in rows])
    ax.set_ylim(0.45, 2.55)
    ax.set_title(
        "Raw strongest RSSI and pressure-floor brute-force RSSI beacon timeline"
    )
    ax.grid(axis="x", alpha=0.22)

    beacon_handles = [
        plt.Line2D(
            [0],
            [0],
            color=BEACON_COLORS[beacon],
            linewidth=8,
            label=f"{beacon} ({BEACON_TO_FLOOR[beacon]})",
        )
        for beacon in BEACON_ORDER
    ]
    changed_handle = plt.Line2D(
        [0],
        [0],
        marker="v",
        color="#111111",
        linestyle="None",
        markersize=6,
        label=f"Brute-force switched windows ({int(changed.sum())})",
    )
    no_candidate_handle = plt.Line2D(
        [0],
        [0],
        marker="x",
        color="#7f7f7f",
        linestyle="None",
        markersize=7,
        label=f"No same-floor RSSI candidate ({int(no_candidate.sum())})",
    )
    ax.legend(
        handles=beacon_handles + [changed_handle, no_candidate_handle],
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        title="Beacon",
    )

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(BRUTE_FORCE_TWO_LINE_TIMELINE_OUTPUT, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return BRUTE_FORCE_TWO_LINE_TIMELINE_OUTPUT


def build_switch_summary(floor_aware):
    total_windows = len(floor_aware)
    mismatch = ~floor_aware["rssi_pressure_floor_consistent"].fillna(False)
    changed = floor_aware["pressure_acc_floor_aware_changed"].fillna(False)
    trusted = floor_aware["pressure_acc_floor_trusted"].fillna(False)

    rows = [
        {
            "metric": "total_5min_windows",
            "count": total_windows,
            "percentage": 100.0,
        },
        {
            "metric": "raw_strongest_rssi_pressure_floor_mismatch",
            "count": int(mismatch.sum()),
            "percentage": 100 * mismatch.mean(),
        },
        {
            "metric": "pressure_acc_floor_trusted_windows",
            "count": int(trusted.sum()),
            "percentage": 100 * trusted.mean(),
        },
        {
            "metric": "changed_to_best_same_floor_beacon",
            "count": int(changed.sum()),
            "percentage": 100 * changed.mean(),
        },
        {
            "metric": "changed_as_percentage_of_mismatches",
            "count": int(changed.sum()),
            "percentage": 100 * changed.sum() / mismatch.sum() if mismatch.sum() else 0,
        },
    ]

    for reason, count in (
        floor_aware["pressure_acc_floor_aware_change_reason"]
        .value_counts(dropna=False)
        .items()
    ):
        rows.append(
            {
                "metric": f"change_reason__{reason}",
                "count": int(count),
                "percentage": 100 * count / total_windows if total_windows else 0,
            }
        )
    return pd.DataFrame(rows)


def build_bruteforce_switch_summary(floor_aware):
    total_windows = len(floor_aware)
    mismatch = ~floor_aware["rssi_pressure_floor_consistent"].fillna(False)
    changed = floor_aware["pressure_floor_bruteforce_changed"].fillna(False)
    no_candidate = floor_aware[
        "pressure_floor_bruteforce_no_same_floor_candidate"
    ].fillna(False)

    return pd.DataFrame(
        [
            {
                "metric": "total_5min_windows",
                "count": total_windows,
                "percentage": 100.0,
            },
            {
                "metric": "raw_strongest_rssi_pressure_floor_mismatch",
                "count": int(mismatch.sum()),
                "percentage": 100 * mismatch.mean(),
            },
            {
                "metric": "bruteforce_changed_to_best_same_floor_beacon",
                "count": int(changed.sum()),
                "percentage": 100 * changed.mean(),
            },
            {
                "metric": "bruteforce_changed_as_percentage_of_mismatches",
                "count": int(changed.sum()),
                "percentage": 100 * changed.sum() / mismatch.sum()
                if mismatch.sum()
                else 0,
            },
            {
                "metric": "mismatch_with_no_same_floor_rssi_candidate",
                "count": int(no_candidate.sum()),
                "percentage": 100 * no_candidate.sum() / mismatch.sum()
                if mismatch.sum()
                else 0,
            },
        ]
    )


def main():
    sensor_features, floor_timeline, acc_features, shift_support = load_inputs()
    floor_aware = build_floor_aware_rssi_table(
        sensor_features, floor_timeline, acc_features, shift_support
    )
    consistency = build_consistency_table(floor_aware)
    switch_summary = build_switch_summary(floor_aware)
    bruteforce_switch_summary = build_bruteforce_switch_summary(floor_aware)

    consistency.to_csv(CONSISTENCY_OUTPUT, index=False)
    floor_aware.to_csv(FLOOR_AWARE_OUTPUT, index=False)
    switch_summary.to_csv(SWITCH_SUMMARY_OUTPUT, index=False)
    bruteforce_switch_summary.to_csv(BRUTE_FORCE_SUMMARY_OUTPUT, index=False)
    consistency_plot = plot_consistency_timeline(consistency)
    mismatch_plot = plot_mismatch_timeline(consistency)
    floor_aware_plot = plot_floor_aware_rssi_timeline(floor_aware)
    raw_vs_floor_aware_plot = plot_raw_vs_pressure_acc_floor_aware(floor_aware)
    two_line_beacon_timeline = plot_two_line_beacon_timeline(floor_aware)
    bruteforce_two_line_timeline = plot_bruteforce_two_line_beacon_timeline(
        floor_aware
    )

    print("Floor-aware RSSI analysis complete")
    print("Saved outputs:")
    for output in [
        CONSISTENCY_OUTPUT,
        consistency_plot,
        mismatch_plot,
        FLOOR_AWARE_OUTPUT,
        floor_aware_plot,
        RAW_VS_FLOOR_AWARE_PLOT_OUTPUT,
        two_line_beacon_timeline,
        bruteforce_two_line_timeline,
        SWITCH_SUMMARY_OUTPUT,
        BRUTE_FORCE_SUMMARY_OUTPUT,
    ]:
        print(output)
    print("\nRSSI-pressure floor consistency:")
    print(
        consistency["rssi_pressure_floor_consistent"]
        .value_counts(dropna=False)
        .rename_axis("consistent")
        .reset_index(name="window_count")
        .to_string(index=False)
    )
    print("\nFloor-aware RSSI status:")
    print(
        floor_aware["floor_aware_rssi_status"]
        .value_counts(dropna=False)
        .rename_axis("status")
        .reset_index(name="window_count")
        .to_string(index=False)
    )
    print("\nPressure+ACC floor-aware RSSI switching summary:")
    print(switch_summary.to_string(index=False))
    print("\nPressure-floor brute-force RSSI switching summary:")
    print(bruteforce_switch_summary.to_string(index=False))


if __name__ == "__main__":
    main()
