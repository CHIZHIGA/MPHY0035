import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
THIRD_PHASE_DIR = os.path.join(BASE_DIR, "Results", "X001", "ThirdPhase")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "X001", "ForthPhase")
os.makedirs(RESULTS_DIR, exist_ok=True)

FEATURES_PATH = os.path.join(THIRD_PHASE_DIR, "X001_10min_sensor_features.csv")
TIMELINE_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_copresence_timeline_10min.csv",
)
SUMMARY_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_copresence_summary.csv",
)
DAILY_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_copresence_by_day.csv",
)
HOURLY_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_copresence_by_hour.csv",
)
SAME_LOCATION_PATH = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_same_location_by_room.csv",
)

TIMELINE_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_copresence_timeline.png",
)
SUMMARY_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_copresence_summary.png",
)
DAILY_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_daily_copresence_hours.png",
)
HOURLY_FIG = os.path.join(
    RESULTS_DIR,
    "X001_forthphase_hourly_copresence_pattern.png",
)

SIDE_TO_ROLE = {
    "LEFT_WRIST": "SUBJECT",
    "RIGHT_WRIST": "STUDY_PARTNER",
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


def load_features():
    if not os.path.exists(FEATURES_PATH):
        raise FileNotFoundError(
            f"Missing ThirdPhase feature table: {FEATURES_PATH}. "
            "Run src/X001/analyse_home_x001_availability.py first."
        )

    features = pd.read_csv(FEATURES_PATH)
    features["time"] = pd.to_datetime(features["time"])
    features["role"] = features["side"].map(SIDE_TO_ROLE)
    features = features.dropna(subset=["role"])
    return features


def prepare_role_frame(features, role):
    frame = features.loc[features["role"] == role].copy()
    frame = frame.sort_values("time").set_index("time")
    mapped_available = frame["mapped_location_available"].map(
        lambda value: str(value).lower() == "true"
    )
    frame["estimated_in_home"] = (
        frame["strongest_location"].notna()
        & frame["strongest_location"].ne("Unmapped")
        & mapped_available
    )
    keep_cols = [
        "strongest_beacon",
        "strongest_location",
        "estimated_in_home",
        "rssi_confidence_score",
        "strongest_beacon_proportion",
        "strongest_second_gap",
        "total_rssi_samples",
        "steps_in_window",
        "movement_intensity",
    ]
    return frame[keep_cols].add_prefix(f"{role.lower()}_")


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


def build_timeline(features):
    subject = prepare_role_frame(features, "SUBJECT")
    partner = prepare_role_frame(features, "STUDY_PARTNER")

    common_index = subject.index.intersection(partner.index).sort_values()
    timeline = subject.loc[common_index].join(partner.loc[common_index], how="inner")
    timeline["copresence_state"] = timeline.apply(classify_state, axis=1)
    timeline["copresence_label"] = timeline["copresence_state"].map(STATE_LABELS)
    timeline["same_estimated_location"] = (
        timeline["copresence_state"] == "both_in_home_same_location"
    )
    timeline["both_estimated_in_home"] = (
        timeline["subject_estimated_in_home"]
        & timeline["study_partner_estimated_in_home"]
    )
    timeline["minimum_rssi_confidence"] = timeline[
        ["subject_rssi_confidence_score", "study_partner_rssi_confidence_score"]
    ].min(axis=1)
    timeline["mean_steps"] = timeline[
        ["subject_steps_in_window", "study_partner_steps_in_window"]
    ].mean(axis=1)
    timeline["date"] = timeline.index.date
    timeline["hour"] = timeline.index.hour
    timeline = timeline.reset_index().rename(columns={"index": "time"})
    return timeline


def summarize_timeline(timeline):
    minutes_per_window = 10
    total_windows = len(timeline)
    total_hours = total_windows * minutes_per_window / 60

    rows = []
    counts = timeline["copresence_state"].value_counts()
    for state in STATE_ORDER:
        windows = int(counts.get(state, 0))
        rows.append(
            {
                "copresence_state": state,
                "copresence_label": STATE_LABELS[state],
                "windows": windows,
                "hours": windows * minutes_per_window / 60,
                "percentage_of_shared_time": windows / total_windows
                if total_windows
                else np.nan,
            }
        )

    summary = pd.DataFrame(rows)
    summary["total_shared_windows"] = total_windows
    summary["total_shared_hours"] = total_hours
    return summary


def summarize_by_day(timeline):
    daily = (
        timeline.groupby(["date", "copresence_state"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=STATE_ORDER, fill_value=0)
    )
    daily = daily * 10 / 60
    daily = daily.reset_index()
    return daily


def summarize_by_hour(timeline):
    hourly = (
        timeline.groupby(["hour", "copresence_state"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=STATE_ORDER, fill_value=0)
    )
    hourly_fraction = hourly.div(hourly.sum(axis=1), axis=0).fillna(0)
    hourly_fraction = hourly_fraction.reset_index()
    return hourly_fraction


def summarize_same_location(timeline):
    same = timeline.loc[
        timeline["copresence_state"] == "both_in_home_same_location"
    ].copy()
    if same.empty:
        return pd.DataFrame(
            columns=[
                "estimated_location",
                "windows",
                "hours",
                "percentage_of_same_location_time",
            ]
        )

    counts = same["subject_strongest_location"].value_counts()
    summary = counts.rename_axis("estimated_location").reset_index(name="windows")
    summary["hours"] = summary["windows"] * 10 / 60
    summary["percentage_of_same_location_time"] = summary["windows"] / summary[
        "windows"
    ].sum()
    return summary


def plot_summary(summary):
    plot_data = summary.sort_values("hours")
    colors = [STATE_COLORS[state] for state in plot_data["copresence_state"]]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(plot_data["copresence_label"], plot_data["hours"], color=colors)
    for y, value in enumerate(plot_data["hours"]):
        ax.text(value + 0.5, y, f"{value:.1f} h", va="center")
    ax.set_xlabel("Hours")
    ax.set_title("Home_X001 ForthPhase: Estimated Co-Presence Summary")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SUMMARY_FIG, dpi=200)
    plt.close(fig)


def plot_timeline(timeline):
    state_codes = {state: index for index, state in enumerate(STATE_ORDER)}
    location_values = sorted(
        pd.concat(
            [
                timeline["subject_strongest_location"],
                timeline["study_partner_strongest_location"],
            ]
        )
        .dropna()
        .unique()
    )
    location_codes = {location: index for index, location in enumerate(location_values)}

    fig, axes = plt.subplots(
        4,
        1,
        figsize=(14, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1, 0.8, 0.8]},
    )

    axes[0].scatter(
        timeline["time"],
        timeline["subject_strongest_location"].map(location_codes),
        s=12,
        c=timeline["subject_rssi_confidence_score"],
        cmap="viridis",
        vmin=0,
        vmax=1,
    )
    axes[0].set_title("SUBJECT estimated location")

    axes[1].scatter(
        timeline["time"],
        timeline["study_partner_strongest_location"].map(location_codes),
        s=12,
        c=timeline["study_partner_rssi_confidence_score"],
        cmap="viridis",
        vmin=0,
        vmax=1,
    )
    axes[1].set_title("STUDY_PARTNER estimated location")

    axes[2].scatter(
        timeline["time"],
        timeline["copresence_state"].map(state_codes),
        s=12,
        c=[STATE_COLORS[state] for state in timeline["copresence_state"]],
    )
    axes[2].set_title("Estimated co-presence state")

    axes[3].plot(
        timeline["time"],
        timeline["minimum_rssi_confidence"],
        color="#4c78a8",
        linewidth=1.2,
        label="Minimum RSSI confidence",
    )
    axes[3].plot(
        timeline["time"],
        timeline["mean_steps"] / max(timeline["mean_steps"].max(), 1),
        color="#f58518",
        linewidth=1.0,
        alpha=0.8,
        label="Mean steps, scaled",
    )
    axes[3].set_ylim(0, 1.05)
    axes[3].set_title("Confidence and movement context")
    axes[3].legend(loc="upper right")

    for ax in axes[:2]:
        ax.set_yticks(list(location_codes.values()))
        ax.set_yticklabels(list(location_codes.keys()))
        ax.grid(alpha=0.2)

    axes[2].set_yticks(list(state_codes.values()))
    axes[2].set_yticklabels([STATE_LABELS[state] for state in STATE_ORDER])
    axes[2].grid(alpha=0.2)
    axes[3].grid(alpha=0.2)
    axes[3].set_xlabel("Time")
    fig.suptitle(
        "Home_X001 ForthPhase: SUBJECT/STUDY_PARTNER Estimated Co-Presence Timeline",
        y=0.995,
    )
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(TIMELINE_FIG, dpi=200)
    plt.close(fig)


def plot_daily(daily):
    plot_data = daily.set_index("date")[STATE_ORDER]
    colors = [STATE_COLORS[state] for state in STATE_ORDER]
    ax = plot_data.plot(
        kind="bar",
        stacked=True,
        figsize=(12, 5.5),
        color=colors,
        width=0.85,
    )
    ax.set_ylabel("Hours")
    ax.set_title("Home_X001 ForthPhase: Estimated Co-Presence Hours by Day")
    ax.legend([STATE_LABELS[state] for state in STATE_ORDER], loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(DAILY_FIG, dpi=200)
    plt.close()


def plot_hourly(hourly):
    plot_data = hourly.set_index("hour")[STATE_ORDER]
    colors = [STATE_COLORS[state] for state in STATE_ORDER]
    ax = plot_data.plot(
        kind="bar",
        stacked=True,
        figsize=(13, 5.5),
        color=colors,
        width=0.9,
    )
    ax.set_ylabel("Fraction of windows")
    ax.set_xlabel("Hour of day")
    ax.set_ylim(0, 1)
    ax.set_title("Home_X001 ForthPhase: Estimated Co-Presence Pattern by Hour")
    ax.legend([STATE_LABELS[state] for state in STATE_ORDER], loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(HOURLY_FIG, dpi=200)
    plt.close()


def main():
    features = load_features()
    timeline = build_timeline(features)
    summary = summarize_timeline(timeline)
    daily = summarize_by_day(timeline)
    hourly = summarize_by_hour(timeline)
    same_location = summarize_same_location(timeline)

    timeline.to_csv(TIMELINE_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    daily.to_csv(DAILY_PATH, index=False)
    hourly.to_csv(HOURLY_PATH, index=False)
    same_location.to_csv(SAME_LOCATION_PATH, index=False)

    plot_summary(summary)
    plot_timeline(timeline)
    plot_daily(daily)
    plot_hourly(hourly)

    print("Saved ForthPhase co-presence outputs:")
    print(TIMELINE_PATH)
    print(SUMMARY_PATH)
    print(DAILY_PATH)
    print(HOURLY_PATH)
    print(SAME_LOCATION_PATH)
    print(TIMELINE_FIG)
    print(SUMMARY_FIG)
    print(DAILY_FIG)
    print(HOURLY_FIG)
    print("\nCo-presence summary:")
    print(summary.to_string(index=False))
    print("\nSame estimated location by room:")
    print(same_location.to_string(index=False))


if __name__ == "__main__":
    main()
