import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_X001")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "X001", "ForthPhase")
os.makedirs(RESULTS_DIR, exist_ok=True)

SIDES = ["LEFT_WRIST", "RIGHT_WRIST"]
SIDE_TO_ROLE = {
    "LEFT_WRIST": "SUBJECT",
    "RIGHT_WRIST": "STUDY_PARTNER",
}
WINDOWS = ["5min", "10min", "30min"]

OTHER_TAG_CODE_MAP = {
    "08": "08E5",
    "19": "1933",
    "25": "2501",
    "71": "714C",
    "74": "747F",
    "9E": "9EDA",
    "D4": "D496",
}

STATE_ORDER = [
    "both_in_home_same_location",
    "both_in_home_different_location",
    "subject_in_home_study_partner_away_or_unmapped",
    "study_partner_in_home_subject_away_or_unmapped",
    "both_away_or_unmapped",
]

STATE_LABELS = {
    "both_in_home_same_location": "Same location",
    "both_in_home_different_location": "Different locations",
    "subject_in_home_study_partner_away_or_unmapped": "Subject home only",
    "study_partner_in_home_subject_away_or_unmapped": "Study-partner home only",
    "both_away_or_unmapped": "Both away/unmapped",
}

STATE_COLORS = {
    "both_in_home_same_location": "#2ca02c",
    "both_in_home_different_location": "#ff7f0e",
    "subject_in_home_study_partner_away_or_unmapped": "#1f77b4",
    "study_partner_in_home_subject_away_or_unmapped": "#9467bd",
    "both_away_or_unmapped": "#7f7f7f",
}

RSSI_FEATURES_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_features.csv",
)
COMPARISON_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_comparison.csv",
)
COPRESENCE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_copresence_summary.csv",
)
COPRESENCE_TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_copresence_timeline.csv",
)
TRANSITION_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_transition_summary.csv",
)
COPRESENCE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_copresence_comparison.png",
)
STABILITY_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_stability_comparison.png",
)
TIMELINE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_fixed_rssi_window_location_timeline.png",
)


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
    records["role"] = SIDE_TO_ROLE[side]
    return records.sort_values("time")


def build_rssi_windows(side, samples, window):
    metadata = read_metadata(side)
    beacon_rows = pd.DataFrame(metadata.get("beacons", []))
    role = SIDE_TO_ROLE[side]

    pivot = samples.pivot_table(
        index="time",
        columns="beacon_id",
        values="rssi",
        aggfunc="mean",
    ).sort_index()

    mean_rssi = pivot.resample(window).mean().dropna(how="all")
    counts = pivot.resample(window).count().reindex(mean_rssi.index)
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
    for start, window_frame in pivot.resample(window):
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
    output = pd.DataFrame(
        {
            "time": mean_rssi.index,
            "side": side,
            "role": role,
            "window": window,
            "strongest_beacon": strongest_beacon.values,
            "strongest_rssi": strongest_rssi.values,
            "strongest_second_gap": strongest_second_gap.values,
            "total_rssi_samples": total_samples.values,
        }
    ).set_index("time")
    output = output.join(props, how="left")
    output = output.loc[output["total_rssi_samples"] > 0].copy()
    output["strongest_location"] = [
        active_beacon_location(beacon_rows, beacon, timestamp)
        for timestamp, beacon in zip(output.index, output["strongest_beacon"])
    ]
    output["mapped_location_available"] = output["strongest_location"].ne("Unmapped")
    output["estimated_in_home"] = (
        output["strongest_location"].notna()
        & output["strongest_location"].ne("Unmapped")
        & output["mapped_location_available"]
    )
    output["rssi_confidence_score"] = (
        0.60 * output["strongest_beacon_proportion"].fillna(0).clip(0, 1)
        + 0.40 * (output["strongest_second_gap"].fillna(0).clip(0, 15) / 15)
    )
    return output.reset_index()


def classify_state(row):
    subject_home = bool(row["subject_estimated_in_home"])
    partner_home = bool(row["study_partner_estimated_in_home"])

    if subject_home and partner_home:
        if row["subject_strongest_location"] == row["study_partner_strongest_location"]:
            return "both_in_home_same_location"
        return "both_in_home_different_location"

    if subject_home and not partner_home:
        return "subject_in_home_study_partner_away_or_unmapped"

    if partner_home and not subject_home:
        return "study_partner_in_home_subject_away_or_unmapped"

    return "both_away_or_unmapped"


def build_window_copresence(features, window):
    subset = features.loc[features["window"] == window].copy()
    subject_raw = (
        subset.loc[subset["role"] == "SUBJECT"].sort_values("time").set_index("time")
    )
    partner_raw = (
        subset.loc[subset["role"] == "STUDY_PARTNER"]
        .sort_values("time")
        .set_index("time")
    )

    common_start = max(subject_raw.index.min(), partner_raw.index.min())
    common_end = min(subject_raw.index.max(), partner_raw.index.max())
    common_index = pd.date_range(start=common_start, end=common_end, freq=window)

    keep_cols = [
        "strongest_beacon",
        "strongest_location",
        "estimated_in_home",
        "rssi_confidence_score",
        "strongest_beacon_proportion",
        "strongest_second_gap",
        "total_rssi_samples",
    ]
    subject = subject_raw[keep_cols].reindex(common_index)
    partner = partner_raw[keep_cols].reindex(common_index)
    subject["estimated_in_home"] = subject["estimated_in_home"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )
    partner["estimated_in_home"] = partner["estimated_in_home"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )

    timeline = subject.add_prefix("subject_").join(
        partner.add_prefix("study_partner_"),
        how="inner",
    )
    timeline["window"] = window
    timeline["copresence_state"] = timeline.apply(classify_state, axis=1)
    timeline["copresence_label"] = timeline["copresence_state"].map(STATE_LABELS)
    timeline["minimum_rssi_confidence"] = timeline[
        [
            "subject_rssi_confidence_score",
            "study_partner_rssi_confidence_score",
        ]
    ].min(axis=1)
    timeline = timeline.reset_index().rename(columns={"index": "time"})
    return timeline


def summarize_copresence(timeline, window):
    window_minutes = pd.to_timedelta(window).total_seconds() / 60
    total_windows = len(timeline)
    rows = []
    counts = timeline["copresence_state"].value_counts()
    for state in STATE_ORDER:
        windows = int(counts.get(state, 0))
        rows.append(
            {
                "window": window,
                "copresence_state": state,
                "copresence_label": STATE_LABELS[state],
                "windows": windows,
                "hours": windows * window_minutes / 60,
                "percentage_of_shared_time": windows / total_windows
                if total_windows
                else np.nan,
                "total_shared_windows": total_windows,
                "total_shared_hours": total_windows * window_minutes / 60,
            }
        )
    return pd.DataFrame(rows)


def summarize_role_stability(features):
    rows = []
    for window, group in features.groupby("window"):
        for role, prefix in [
            ("SUBJECT", "subject"),
            ("STUDY_PARTNER", "study_partner"),
        ]:
            location = group[f"{prefix}_strongest_location"].fillna("Missing")
            transition_count = location.ne(location.shift()).sum() - 1
            transition_count = max(int(transition_count), 0)
            in_home_fraction = group[f"{prefix}_estimated_in_home"].mean()
            rows.append(
                {
                    "window": window,
                    "role": role,
                    "shared_timeline_windows": len(group),
                    "estimated_in_home_fraction": in_home_fraction,
                    "unmapped_or_missing_fraction": 1 - in_home_fraction,
                    "mean_rssi_confidence_score": group[
                        f"{prefix}_rssi_confidence_score"
                    ].mean(),
                    "median_rssi_confidence_score": group[
                        f"{prefix}_rssi_confidence_score"
                    ].median(),
                    "mean_strongest_beacon_proportion": group[
                        f"{prefix}_strongest_beacon_proportion"
                    ].mean(),
                    "mean_strongest_second_gap": group[
                        f"{prefix}_strongest_second_gap"
                    ].mean(),
                    "location_transition_count": transition_count,
                    "transitions_per_day": transition_count
                    / max(
                        (
                            len(group)
                            * pd.to_timedelta(window).total_seconds()
                            / 86400
                        ),
                        1,
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_outputs():
    all_features = []
    for side in SIDES:
        print(f"Loading RSSI samples for {side}...")
        samples = load_rssi_samples(side)
        for window in WINDOWS:
            print(f"  Building {window} RSSI-only windows...")
            all_features.append(build_rssi_windows(side, samples, window))

    features = pd.concat(all_features, ignore_index=True)

    timelines = []
    summaries = []
    for window in WINDOWS:
        timeline = build_window_copresence(features, window)
        timelines.append(timeline)
        summaries.append(summarize_copresence(timeline, window))

    copresence = pd.concat(timelines, ignore_index=True)
    copresence_summary = pd.concat(summaries, ignore_index=True)
    stability_summary = summarize_role_stability(copresence)
    return features, copresence, copresence_summary, stability_summary


def plot_copresence_summary(copresence_summary):
    pivot = copresence_summary.pivot(
        index="window",
        columns="copresence_state",
        values="percentage_of_shared_time",
    ).reindex(index=WINDOWS, columns=STATE_ORDER)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for state in STATE_ORDER:
        values = pivot[state].fillna(0).values
        ax.bar(
            x,
            values,
            bottom=bottom,
            label=STATE_LABELS[state],
            color=STATE_COLORS[state],
        )
        bottom += values

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction of shared time")
    ax.set_title("Home_X001 ForthPhase 4a: RSSI-Only Co-Presence by Window Size")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COPRESENCE_FIG, dpi=200)
    plt.close(fig)


def plot_stability(stability_summary):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    metrics = [
        ("mean_rssi_confidence_score", "Mean RSSI confidence"),
        ("estimated_in_home_fraction", "Estimated in-home fraction"),
        ("location_transition_count", "Location transitions"),
    ]
    for ax, (metric, title) in zip(axes, metrics):
        pivot = stability_summary.pivot(index="window", columns="role", values=metric)
        pivot = pivot.reindex(WINDOWS)
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("Window")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="")
    fig.suptitle("Home_X001 ForthPhase 4a: RSSI-Only Stability Summary", y=1.03)
    fig.tight_layout()
    fig.savefig(STABILITY_FIG, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_location_timeline(features):
    plot_features = features.loc[features["window"].isin(WINDOWS)].copy()
    location_values = sorted(plot_features["strongest_location"].dropna().unique())
    location_codes = {location: index for index, location in enumerate(location_values)}

    fig, axes = plt.subplots(len(WINDOWS), 1, figsize=(14, 8), sharex=True)
    for ax, window in zip(axes, WINDOWS):
        subset = plot_features.loc[plot_features["window"] == window].copy()
        for role, marker in [("SUBJECT", "o"), ("STUDY_PARTNER", "s")]:
            role_data = subset.loc[subset["role"] == role].sort_values("time")
            ax.scatter(
                role_data["time"],
                role_data["strongest_location"].map(location_codes),
                s=10,
                marker=marker,
                alpha=0.8,
                label=role,
            )
        ax.set_title(f"{window} RSSI-only estimated location")
        ax.set_yticks(list(location_codes.values()))
        ax.set_yticklabels(list(location_codes.keys()))
        ax.grid(alpha=0.2)
        ax.legend(loc="upper right")
    axes[-1].set_xlabel("Time")
    fig.suptitle("Home_X001 ForthPhase 4a: Fixed-Window RSSI Location Timeline", y=0.995)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(TIMELINE_FIG, dpi=200)
    plt.close(fig)


def main():
    features, copresence, copresence_summary, stability_summary = build_outputs()

    features.to_csv(RSSI_FEATURES_PATH, index=False)
    copresence.to_csv(COPRESENCE_TIMELINE_PATH, index=False)
    copresence_summary.to_csv(COPRESENCE_PATH, index=False)
    stability_summary.to_csv(COMPARISON_PATH, index=False)
    stability_summary.to_csv(TRANSITION_PATH, index=False)

    plot_copresence_summary(copresence_summary)
    plot_stability(stability_summary)
    plot_location_timeline(features)

    print("\nSaved fixed-window RSSI-only outputs:")
    print(RSSI_FEATURES_PATH)
    print(COPRESENCE_TIMELINE_PATH)
    print(COPRESENCE_PATH)
    print(COMPARISON_PATH)
    print(TRANSITION_PATH)
    print(COPRESENCE_FIG)
    print(STABILITY_FIG)
    print(TIMELINE_FIG)
    print("\nCo-presence summary:")
    print(copresence_summary.to_string(index=False))
    print("\nStability summary:")
    print(stability_summary.to_string(index=False))


if __name__ == "__main__":
    main()
