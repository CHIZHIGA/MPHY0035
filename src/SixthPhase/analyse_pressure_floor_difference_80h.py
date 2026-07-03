import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_pressure_only_80h import (
    BEACON_PRESSURE_PATH,
    BRACELET_PRESSURE_PATH,
    RESULTS_DIR,
    SPIKE_THRESHOLD_HPA,
    BEACON_SPIKE_WINDOW,
    BEACON_SHORT_SPIKE_MAX_ROWS,
    correct_baseline_offset_short_segments,
    correct_long_plateaus,
    correct_short_spikes,
    load_pressure_csv,
    pressure_columns,
)


BEACON_GROUP_OUTPUT = RESULTS_DIR / "new80h_beacon_pressure_floor_group_candidates.csv"
PAIRWISE_OUTPUT = RESULTS_DIR / "new80h_beacon_pressure_pairwise_median_difference.csv"
DIFFERENCE_OUTPUT = RESULTS_DIR / "new80h_bracelet_beacon_pressure_differences_5min.csv"
CLOSEST_OUTPUT = RESULTS_DIR / "new80h_pressure_closest_beacon_5min.csv"
BASELINE_OUTPUT = RESULTS_DIR / "new80h_pressure_same_floor_baseline_estimate.csv"
GROUP_PLOT_OUTPUT = RESULTS_DIR / "new80h_beacon_pressure_floor_group_offsets.png"
DIFFERENCE_PLOT_OUTPUT = (
    RESULTS_DIR / "new80h_bracelet_beacon_pressure_difference_timeline.png"
)
BASELINE_DIFFERENCE_PLOT_OUTPUT = (
    RESULTS_DIR / "new80h_bracelet_beacon_pressure_difference_same_floor_baseline.png"
)
CLOSEST_PLOT_OUTPUT = RESULTS_DIR / "new80h_pressure_closest_beacon_timeline.png"

GROUP_LABELS = {
    "lower_pressure_candidate_upper_floor": "upper_floor_candidate",
    "higher_pressure_candidate_lower_floor": "lower_floor_candidate",
}


def pressure_to_height_meters(delta_hpa):
    return -8.3 * delta_hpa


def robust_mad(values):
    clean = pd.Series(values).dropna()
    if clean.empty:
        return np.nan
    median = clean.median()
    return (clean - median).abs().median()


def trim_series(values, lower_quantile=0.01, upper_quantile=0.99):
    clean = pd.Series(values).dropna()
    if clean.empty:
        return clean
    lower = clean.quantile(lower_quantile)
    upper = clean.quantile(upper_quantile)
    return clean.loc[clean.between(lower, upper)]


def fit_two_kmedians_1d(values, max_iterations=100):
    clean = trim_series(values)
    if len(clean) < 2:
        return np.array([np.nan, np.nan]), pd.Series(dtype=int)

    centers = np.array([clean.quantile(0.25), clean.quantile(0.75)], dtype=float)
    labels = pd.Series(0, index=clean.index, dtype=int)

    for _ in range(max_iterations):
        distances = np.abs(clean.to_numpy()[:, None] - centers[None, :])
        new_labels = pd.Series(distances.argmin(axis=1), index=clean.index, dtype=int)
        new_centers = centers.copy()
        for label in (0, 1):
            cluster = clean.loc[new_labels == label]
            if not cluster.empty:
                new_centers[label] = cluster.median()

        if np.allclose(np.sort(centers), np.sort(new_centers), atol=1e-6):
            labels = new_labels
            centers = new_centers
            break
        labels = new_labels
        centers = new_centers

    order = np.argsort(centers)
    sorted_centers = centers[order]
    remap = {old_label: new_label for new_label, old_label in enumerate(order)}
    labels = labels.map(remap)
    return sorted_centers, labels


def split_two_pressure_groups(relative_offsets):
    ordered = relative_offsets.sort_values()
    gaps = ordered.diff().iloc[1:]
    split_at = gaps.idxmax()
    split_position = ordered.index.get_loc(split_at)
    lower_pressure = set(ordered.index[:split_position])
    higher_pressure = set(ordered.index[split_position:])
    return lower_pressure, higher_pressure


def prepare_clean_pressure():
    beacon_pressure = load_pressure_csv(BEACON_PRESSURE_PATH)
    bracelet_pressure = load_pressure_csv(BRACELET_PRESSURE_PATH)

    beacon_cols = pressure_columns(beacon_pressure)
    beacon_clean, _, _ = correct_short_spikes(
        beacon_pressure,
        beacon_cols,
        BEACON_SPIKE_WINDOW,
        SPIKE_THRESHOLD_HPA,
        BEACON_SHORT_SPIKE_MAX_ROWS,
    )
    bracelet_plateau_clean, _, _ = correct_long_plateaus(
        bracelet_pressure, beacon_clean, beacon_cols
    )
    bracelet_clean, _, _, _ = correct_baseline_offset_short_segments(
        bracelet_plateau_clean, beacon_clean, beacon_cols
    )
    return beacon_clean, bracelet_clean, beacon_cols


def build_beacon_group_table(beacon_pressure, beacon_cols):
    relative = beacon_pressure[beacon_cols].sub(
        beacon_pressure[beacon_cols].median(axis=1), axis=0
    )
    median_relative = relative.median().sort_values()
    lower_pressure, higher_pressure = split_two_pressure_groups(median_relative)

    rows = []
    for beacon in median_relative.index:
        group = (
            "lower_pressure_candidate_upper_floor"
            if beacon in lower_pressure
            else "higher_pressure_candidate_lower_floor"
        )
        rows.append(
            {
                "beacon": beacon,
                "median_pressure_hpa": beacon_pressure[beacon].median(),
                "median_relative_to_beacon_median_hpa": median_relative[beacon],
                "approx_height_vs_beacon_median_m": pressure_to_height_meters(
                    median_relative[beacon]
                ),
                "pressure_group": group,
            }
        )
    return pd.DataFrame(rows)


def build_pairwise_table(beacon_pressure, beacon_cols):
    medians = beacon_pressure[beacon_cols].median()
    pairwise = pd.DataFrame(index=beacon_cols, columns=beacon_cols, dtype=float)
    for row_beacon in beacon_cols:
        for col_beacon in beacon_cols:
            pairwise.loc[row_beacon, col_beacon] = medians[row_beacon] - medians[col_beacon]
    return pairwise


def build_pressure_difference_tables(beacon_pressure, bracelet_pressure, beacon_cols):
    beacon_5min = beacon_pressure[["time", *beacon_cols]].copy()
    beacon_5min["window_start"] = beacon_5min["time"].dt.floor("5min")
    beacon_5min = (
        beacon_5min.groupby("window_start")[beacon_cols]
        .median()
        .reset_index()
        .rename(columns={"window_start": "time"})
    )

    bracelet = bracelet_pressure[["time", "PRESSURE"]].copy()
    bracelet["window_start"] = bracelet["time"].dt.floor("5min")
    bracelet_5min = (
        bracelet.groupby("window_start")["PRESSURE"]
        .median()
        .reset_index()
        .rename(columns={"window_start": "time", "PRESSURE": "bracelet_pressure_hpa"})
    )

    merged = bracelet_5min.merge(beacon_5min, on="time", how="inner")
    differences = merged[["time", "bracelet_pressure_hpa"]].copy()
    abs_differences = {}
    for beacon in beacon_cols:
        diff_col = f"bracelet_minus_{beacon}_hpa"
        abs_col = f"abs_bracelet_minus_{beacon}_hpa"
        differences[diff_col] = merged["bracelet_pressure_hpa"] - merged[beacon]
        differences[abs_col] = differences[diff_col].abs()
        abs_differences[beacon] = differences[abs_col]

    abs_frame = pd.DataFrame(abs_differences)
    differences["pressure_closest_beacon"] = abs_frame.idxmin(axis=1)
    differences["pressure_closest_abs_diff_hpa"] = abs_frame.min(axis=1)
    differences["pressure_second_abs_diff_hpa"] = abs_frame.apply(
        lambda row: row.sort_values().iloc[1] if row.notna().sum() >= 2 else np.nan,
        axis=1,
    )
    differences["pressure_closest_margin_hpa"] = (
        differences["pressure_second_abs_diff_hpa"]
        - differences["pressure_closest_abs_diff_hpa"]
    )

    closest = differences[
        [
            "time",
            "bracelet_pressure_hpa",
            "pressure_closest_beacon",
            "pressure_closest_abs_diff_hpa",
            "pressure_second_abs_diff_hpa",
            "pressure_closest_margin_hpa",
        ]
    ].copy()
    return differences, closest


def add_floor_group_differences(differences, group_table):
    updated = differences.copy()
    group_diff_cols = {}
    for group, beacons in group_table.groupby("pressure_group")["beacon"]:
        short_label = GROUP_LABELS[group]
        diff_cols = [f"bracelet_minus_{beacon}_hpa" for beacon in beacons]
        group_diff_col = f"bracelet_minus_{short_label}_group_median_hpa"
        updated[group_diff_col] = updated[diff_cols].median(axis=1)
        group_diff_cols[short_label] = group_diff_col
    return updated, group_diff_cols


def bootstrap_median_ci(values, iterations=1000, confidence=0.95, seed=20260703):
    clean = pd.Series(values).dropna().to_numpy()
    if len(clean) < 2:
        return np.nan, np.nan

    rng = np.random.default_rng(seed)
    medians = []
    for _ in range(iterations):
        sample = rng.choice(clean, size=len(clean), replace=True)
        medians.append(np.median(sample))
    alpha = (1 - confidence) / 2
    return (
        float(np.quantile(medians, alpha)),
        float(np.quantile(medians, 1 - alpha)),
    )


def estimate_same_floor_baseline(differences, group_diff_cols):
    group_cols = list(group_diff_cols.values())
    pooled = pd.concat([differences[column] for column in group_cols], ignore_index=True)
    mixture_centers, mixture_labels = fit_two_kmedians_1d(pooled)
    same_floor_center = mixture_centers[np.nanargmin(np.abs(mixture_centers))]
    other_floor_center = mixture_centers[np.nanargmax(np.abs(mixture_centers))]

    group_abs = differences[group_cols].abs()
    nearest_group_diff = differences[group_cols].where(
        group_abs.eq(group_abs.min(axis=1), axis=0)
    ).stack()
    nearest_group_diff = trim_series(nearest_group_diff)
    nearest_ci_low, nearest_ci_high = bootstrap_median_ci(nearest_group_diff)

    floor_gap_hpa = np.nan
    if len(group_cols) == 2:
        floor_gap_hpa = (differences[group_cols[0]] - differences[group_cols[1]]).abs()
        floor_gap_hpa = trim_series(floor_gap_hpa).median()

    cluster_counts = mixture_labels.value_counts().sort_index()
    baseline = pd.DataFrame(
        [
            {
                "method": (
                    "1D robust k-medians on bracelet-minus-floor-group "
                    "pressure differences; same-floor center is the "
                    "mixture center closest to zero"
                ),
                "same_floor_baseline_hpa": same_floor_center,
                "same_floor_bracelet_height_offset_m": pressure_to_height_meters(
                    same_floor_center
                ),
                "other_floor_cluster_center_hpa": other_floor_center,
                "mixture_center_low_hpa": mixture_centers[0],
                "mixture_center_high_hpa": mixture_centers[1],
                "mixture_cluster_low_count": int(cluster_counts.get(0, 0)),
                "mixture_cluster_high_count": int(cluster_counts.get(1, 0)),
                "nearest_group_median_hpa": nearest_group_diff.median(),
                "nearest_group_mean_hpa": nearest_group_diff.mean(),
                "nearest_group_mad_hpa": robust_mad(nearest_group_diff),
                "nearest_group_p05_hpa": nearest_group_diff.quantile(0.05),
                "nearest_group_p25_hpa": nearest_group_diff.quantile(0.25),
                "nearest_group_p75_hpa": nearest_group_diff.quantile(0.75),
                "nearest_group_p95_hpa": nearest_group_diff.quantile(0.95),
                "nearest_group_median_ci95_low_hpa": nearest_ci_low,
                "nearest_group_median_ci95_high_hpa": nearest_ci_high,
                "estimated_floor_gap_hpa": floor_gap_hpa,
                "estimated_floor_height_m": abs(pressure_to_height_meters(floor_gap_hpa)),
                "pooled_group_difference_samples": len(trim_series(pooled)),
                "nearest_group_samples": len(nearest_group_diff),
            }
        ]
    )
    return baseline


def add_baseline_adjusted_differences(differences, beacon_cols, baseline_hpa):
    updated = differences.copy()
    adjusted_abs_differences = {}
    for beacon in beacon_cols:
        diff_col = f"bracelet_minus_{beacon}_hpa"
        adjusted_col = f"{diff_col}_minus_same_floor_baseline"
        adjusted_abs_col = f"abs_{adjusted_col}"
        updated[adjusted_col] = updated[diff_col] - baseline_hpa
        updated[adjusted_abs_col] = updated[adjusted_col].abs()
        adjusted_abs_differences[beacon] = updated[adjusted_abs_col]

    adjusted_abs_frame = pd.DataFrame(adjusted_abs_differences)
    updated["pressure_closest_beacon_after_baseline"] = adjusted_abs_frame.idxmin(axis=1)
    updated["pressure_closest_abs_diff_after_baseline_hpa"] = adjusted_abs_frame.min(axis=1)
    return updated


def plot_beacon_groups(group_table, pairwise):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    colors = group_table["pressure_group"].map(
        {
            "lower_pressure_candidate_upper_floor": "#4c78a8",
            "higher_pressure_candidate_lower_floor": "#f58518",
        }
    )
    axes[0].bar(
        group_table["beacon"],
        group_table["median_relative_to_beacon_median_hpa"],
        color=colors,
    )
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_title("Beacon pressure offset candidates")
    axes[0].set_ylabel("Median offset vs beacon median (hPa)")
    axes[0].set_xlabel("Beacon")
    axes[0].grid(axis="y", alpha=0.2)

    image = axes[1].imshow(pairwise.astype(float), cmap="coolwarm")
    axes[1].set_xticks(range(len(pairwise.columns)))
    axes[1].set_xticklabels(pairwise.columns)
    axes[1].set_yticks(range(len(pairwise.index)))
    axes[1].set_yticklabels(pairwise.index)
    axes[1].set_title("Pairwise beacon pressure differences")
    for row in range(len(pairwise.index)):
        for col in range(len(pairwise.columns)):
            axes[1].text(
                col,
                row,
                f"{pairwise.iloc[row, col]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
            )
    fig.colorbar(image, ax=axes[1], fraction=0.046, pad=0.04, label="hPa")
    fig.tight_layout()
    fig.savefig(GROUP_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return GROUP_PLOT_OUTPUT


def plot_bracelet_beacon_differences(differences, beacon_cols):
    fig, ax = plt.subplots(figsize=(13, 5.5))
    for beacon in beacon_cols:
        ax.plot(
            differences["time"],
            differences[f"bracelet_minus_{beacon}_hpa"],
            linewidth=1.0,
            label=f"Bracelet - {beacon}",
        )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Bracelet pressure difference to each beacon")
    ax.set_ylabel("Bracelet minus beacon pressure (hPa)")
    ax.set_xlabel("Time")
    ax.grid(alpha=0.2)
    ax.legend(ncol=4, fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(DIFFERENCE_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return DIFFERENCE_PLOT_OUTPUT


def plot_bracelet_beacon_differences_with_baseline(
    differences, beacon_cols, baseline_table
):
    baseline_hpa = baseline_table["same_floor_baseline_hpa"].iloc[0]
    floor_gap_hpa = baseline_table["estimated_floor_gap_hpa"].iloc[0]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    for beacon in beacon_cols:
        ax.plot(
            differences["time"],
            differences[f"bracelet_minus_{beacon}_hpa"],
            linewidth=1.0,
            label=f"Bracelet - {beacon}",
        )
    ax.axhline(0, color="black", linewidth=0.8, label="Zero pressure difference")
    ax.axhline(
        baseline_hpa,
        color="#2ca02c",
        linestyle="--",
        linewidth=1.4,
        label=f"Robust same-floor baseline ({baseline_hpa:.3f} hPa)",
    )
    if pd.notna(floor_gap_hpa):
        ax.axhline(
            baseline_hpa - floor_gap_hpa,
            color="#666666",
            linestyle=":",
            linewidth=1.0,
            label=f"One-floor lower-pressure offset ({baseline_hpa - floor_gap_hpa:.3f} hPa)",
        )
        ax.axhline(
            baseline_hpa + floor_gap_hpa,
            color="#666666",
            linestyle=":",
            linewidth=1.0,
            label=f"One-floor higher-pressure offset ({baseline_hpa + floor_gap_hpa:.3f} hPa)",
        )
    ax.set_title("Bracelet pressure difference with robust same-floor baseline")
    ax.set_ylabel("Bracelet minus beacon pressure (hPa)")
    ax.set_xlabel("Time")
    ax.grid(alpha=0.2)
    ax.legend(ncol=3, fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(BASELINE_DIFFERENCE_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return BASELINE_DIFFERENCE_PLOT_OUTPUT


def plot_pressure_closest_beacon(closest, beacon_cols):
    beacon_order = {beacon: index for index, beacon in enumerate(beacon_cols)}
    fig, axes = plt.subplots(2, 1, figsize=(13, 6.5), sharex=True)
    axes[0].scatter(
        closest["time"],
        closest["pressure_closest_beacon"].map(beacon_order),
        c=closest["pressure_closest_beacon"].map(beacon_order),
        cmap="tab10",
        s=12,
    )
    axes[0].set_yticks(list(beacon_order.values()))
    axes[0].set_yticklabels(list(beacon_order.keys()))
    axes[0].set_title("Pressure-closest beacon over time")
    axes[0].set_ylabel("Closest beacon")
    axes[0].grid(axis="x", alpha=0.2)

    axes[1].plot(
        closest["time"],
        closest["pressure_closest_abs_diff_hpa"],
        linewidth=1.0,
        label="Closest absolute pressure difference",
    )
    axes[1].plot(
        closest["time"],
        closest["pressure_closest_margin_hpa"],
        linewidth=1.0,
        label="Margin to second closest",
    )
    axes[1].set_ylabel("hPa")
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.2)
    axes[1].legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CLOSEST_PLOT_OUTPUT, dpi=220)
    plt.close(fig)
    return CLOSEST_PLOT_OUTPUT


def main():
    beacon_pressure, bracelet_pressure, beacon_cols = prepare_clean_pressure()

    group_table = build_beacon_group_table(beacon_pressure, beacon_cols)
    pairwise = build_pairwise_table(beacon_pressure, beacon_cols)
    differences, closest = build_pressure_difference_tables(
        beacon_pressure, bracelet_pressure, beacon_cols
    )
    differences, group_diff_cols = add_floor_group_differences(differences, group_table)
    baseline_table = estimate_same_floor_baseline(differences, group_diff_cols)
    baseline_hpa = baseline_table["same_floor_baseline_hpa"].iloc[0]
    differences = add_baseline_adjusted_differences(
        differences, beacon_cols, baseline_hpa
    )
    group_map = group_table.set_index("beacon")["pressure_group"]
    closest["pressure_closest_group"] = closest["pressure_closest_beacon"].map(group_map)

    group_table.to_csv(BEACON_GROUP_OUTPUT, index=False)
    pairwise.to_csv(PAIRWISE_OUTPUT)
    baseline_table.to_csv(BASELINE_OUTPUT, index=False)
    differences.to_csv(DIFFERENCE_OUTPUT, index=False)
    closest.to_csv(CLOSEST_OUTPUT, index=False)

    outputs = [
        BEACON_GROUP_OUTPUT,
        PAIRWISE_OUTPUT,
        BASELINE_OUTPUT,
        DIFFERENCE_OUTPUT,
        CLOSEST_OUTPUT,
        plot_beacon_groups(group_table, pairwise),
        plot_bracelet_beacon_differences(differences, beacon_cols),
        plot_bracelet_beacon_differences_with_baseline(
            differences, beacon_cols, baseline_table
        ),
        plot_pressure_closest_beacon(closest, beacon_cols),
    ]

    print("Pressure floor-difference analysis complete")
    print("Saved outputs:")
    for output in outputs:
        print(output)
    print("\nBeacon pressure group candidates:")
    print(group_table.to_string(index=False))
    print("\nSame-floor pressure baseline estimate:")
    print(baseline_table.to_string(index=False))


if __name__ == "__main__":
    main()
