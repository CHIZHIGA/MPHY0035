import json
import os
from datetime import datetime, timedelta

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_A002", "AA002")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "002")
os.makedirs(RESULTS_DIR, exist_ok=True)

PARTICIPANT = "AA002"
TARGET_DATE = "2023-07-17"
START_TIME_STR = f"{TARGET_DATE} 00:00"
END_TIME_STR = f"{TARGET_DATE} 23:50"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
INTERVAL_MINUTES = 10

LOCATION_PATH = os.path.join(DATA_DIR, "annotator.json")
STEP_ACTIVITY_PATH = os.path.join(DATA_DIR, "auto_activity_level_steps_10min.json")
ACC_ACTIVITY_PATH = os.path.join(DATA_DIR, "auto_activity_level_acc_10min.json")
FUSED_ACTIVITY_PATH = os.path.join(DATA_DIR, "auto_activity_level_fused_10min.json")

GIF_PATH = os.path.join(
    RESULTS_DIR,
    f"{PARTICIPANT}_activity_location_10min_compare_{TARGET_DATE}.gif",
)
FIRST_FRAME_PATH = os.path.join(
    RESULTS_DIR,
    f"{PARTICIPANT}_activity_location_10min_compare_{TARGET_DATE}_first_frame.png",
)


# =====================================
# Visual settings
# =====================================

ROOM_POSITIONS = {
    "Bedroom": (0.25, 0.75),
    "Kitchen": (0.75, 0.75),
    "Living": (0.25, 0.25),
    "Office": (0.75, 0.25),
}

MAIN_ROOMS = set(ROOM_POSITIONS.keys())
OUTSIDE_LOCATIONS = {"Indoor transition", "Other", "Other 2", "Out", "Unknown"}

ACTIVITY_COLORS = {
    "Sleep": "#355C7D",
    "Sedentary": "#90A4AE",
    "Light activity": "#F9A826",
    "Moderate to Vigorous activity": "#D64541",
    "Unknown activity": "#CFCFCF",
}

METHODS = [
    {
        "key": "step",
        "title": "Step count estimate",
        "path": STEP_ACTIVITY_PATH,
    },
    {
        "key": "acc",
        "title": "Acceleration estimate",
        "path": ACC_ACTIVITY_PATH,
    },
    {
        "key": "fused",
        "title": "Fused estimate",
        "path": FUSED_ACTIVITY_PATH,
    },
]

HIGH_ACTIVITY_LABELS = {"Light activity", "Moderate to Vigorous activity"}
LOW_ACTIVITY_LABELS = {"Sleep", "Sedentary"}


# =====================================
# Data helpers
# =====================================

def parse_timestamp_ms(timestamp_ms):
    return datetime.fromtimestamp(int(timestamp_ms) / 1000.0)


def parse_datetime_string(value):
    return datetime.strptime(value, DATETIME_FORMAT)


def load_timerange_labels(path, data_key):
    with open(path, "r") as f:
        annot = json.load(f)

    records = []
    for shape in annot.get("shapes", []):
        if shape.get("type") != "timerange":
            continue

        label = shape.get("data", {}).get(data_key)
        if label is None:
            continue

        records.append(
            {
                "start": parse_timestamp_ms(shape["start"]),
                "end": parse_timestamp_ms(shape["end"]),
                "label": label,
            }
        )
    return records


def get_dominant_label(records, current_time, interval_minutes):
    interval_start = current_time
    interval_end = current_time + timedelta(minutes=interval_minutes)

    overlap_seconds_by_label = {}
    for row in records:
        if row["start"] >= interval_end or row["end"] <= interval_start:
            continue

        overlap_start = max(row["start"], interval_start)
        overlap_end = min(row["end"], interval_end)
        overlap_seconds = max((overlap_end - overlap_start).total_seconds(), 0)

        if overlap_seconds <= 0:
            continue

        label = row["label"]
        overlap_seconds_by_label[label] = (
            overlap_seconds_by_label.get(label, 0) + overlap_seconds
        )

    if not overlap_seconds_by_label:
        return None

    ranked_labels = sorted(
        overlap_seconds_by_label.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return ranked_labels[0][0]


def activity_display(label):
    return label or "Unknown activity"


def context_flag(current_time, location_label, labels_by_method):
    location = location_label or "Unknown"
    high_methods = [
        method["key"]
        for method in METHODS
        if labels_by_method.get(method["key"]) in HIGH_ACTIVITY_LABELS
    ]
    low_methods = [
        method["key"]
        for method in METHODS
        if labels_by_method.get(method["key"]) in LOW_ACTIVITY_LABELS
    ]

    is_night = current_time.hour >= 22 or current_time.hour < 7
    if location == "Bedroom" and is_night and len(low_methods) >= 2:
        return "Bedroom + night + low activity"
    if location == "Bedroom" and high_methods:
        return "Bedroom + high activity"
    if location in {"Indoor transition", "Out", "Other 2"} and high_methods:
        return "Transition/Out + high activity"
    if labels_by_method.get("step") in LOW_ACTIVITY_LABELS and labels_by_method.get("acc") in HIGH_ACTIVITY_LABELS:
        return "possible non-walking movement"
    if labels_by_method.get("step") == labels_by_method.get("acc"):
        return "step and acceleration agree"
    return "step and acceleration differ"


# =====================================
# Drawing helpers
# =====================================

def draw_simple_map(ax, location_label, activity_label, title):
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, linewidth=2, color="#222222"))
    ax.plot([0.5, 0.5], [0, 1], linewidth=1, color="#222222")
    ax.plot([0, 1], [0.5, 0.5], linewidth=1, color="#222222")

    for room, (x, y) in ROOM_POSITIONS.items():
        ax.text(x, y, room, ha="center", va="center", fontsize=10, color="#222222")

    display_activity = activity_display(activity_label)
    marker_color = ACTIVITY_COLORS.get(display_activity, ACTIVITY_COLORS["Unknown activity"])

    if location_label in MAIN_ROOMS:
        x, y = ROOM_POSITIONS[location_label]
        marker = "o"
    else:
        x, y = 1.17, 0.50
        marker = "^"
        outside_label = location_label or "Unknown"
        ax.text(1.17, 0.64, outside_label, ha="center", va="bottom", fontsize=9)

    ax.plot(
        x,
        y,
        marker,
        markersize=18,
        color=marker_color,
        markeredgecolor="#FFFFFF",
        markeredgewidth=2,
        zorder=5,
    )
    ax.text(
        x,
        y - 0.09,
        PARTICIPANT,
        ha="center",
        va="top",
        fontsize=9,
        weight="bold",
        color="#222222",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.80),
    )

    ax.text(0.5, 1.08, title, ha="center", va="bottom", fontsize=11, weight="bold")
    ax.text(
        0.5,
        -0.13,
        display_activity,
        ha="center",
        va="top",
        fontsize=10,
        color=marker_color,
        weight="bold",
        wrap=True,
    )

    ax.set_xlim(-0.12, 1.36)
    ax.set_ylim(-0.22, 1.18)
    ax.set_aspect("equal")
    ax.axis("off")


def render_frame(current_time, location_label, labels_by_method):
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.2), dpi=110)
    fig.patch.set_facecolor("white")

    for ax, method in zip(axes, METHODS):
        draw_simple_map(
            ax,
            location_label,
            labels_by_method.get(method["key"]),
            method["title"],
        )

    step_label = labels_by_method.get("step")
    acc_label = labels_by_method.get("acc")
    agreement = "YES" if step_label == acc_label else "NO"
    flag = context_flag(current_time, location_label, labels_by_method)
    location_display = location_label or "Unknown"

    fig.suptitle(
        f"{PARTICIPANT} location + activity comparison | {current_time:%Y-%m-%d %H:%M}",
        fontsize=14,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.065,
        f"Dominant location: {location_display} | Step vs Acc agree: {agreement} | Context: {flag}",
        ha="center",
        va="center",
        fontsize=10,
    )

    legend_handles = [
        mpatches.Patch(color=color, label=label)
        for label, color in ACTIVITY_COLORS.items()
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=len(legend_handles),
        frameon=False,
        bbox_to_anchor=(0.5, -0.005),
        fontsize=9,
    )

    plt.tight_layout(rect=[0.01, 0.10, 0.99, 0.92])

    fig.canvas.draw()
    rgba_image = np.asarray(fig.canvas.buffer_rgba())
    rgb_image = rgba_image[:, :, :3].copy()
    return fig, rgb_image


# =====================================
# Main
# =====================================

def main():
    print(f"Loading location annotations from: {LOCATION_PATH}")
    location_records = load_timerange_labels(LOCATION_PATH, "location")

    activity_records_by_method = {}
    for method in METHODS:
        print(f"Loading {method['title']} from: {method['path']}")
        activity_records_by_method[method["key"]] = load_timerange_labels(
            method["path"],
            "activityLevel",
        )

    start_time = parse_datetime_string(START_TIME_STR)
    end_time = parse_datetime_string(END_TIME_STR)

    gif_frames = []
    current_time = start_time
    frame_count = 0
    first_frame_saved = False

    print(f"Generating 10-minute comparison GIF from {start_time} to {end_time}")
    while current_time <= end_time:
        location_label = get_dominant_label(
            location_records,
            current_time,
            INTERVAL_MINUTES,
        )
        labels_by_method = {
            method["key"]: get_dominant_label(
                activity_records_by_method[method["key"]],
                current_time,
                INTERVAL_MINUTES,
            )
            for method in METHODS
        }

        fig, rgb_image = render_frame(current_time, location_label, labels_by_method)
        gif_frames.append(Image.fromarray(rgb_image))

        if not first_frame_saved:
            fig.savefig(FIRST_FRAME_PATH, dpi=220, bbox_inches="tight")
            first_frame_saved = True

        plt.close(fig)

        current_time += timedelta(minutes=INTERVAL_MINUTES)
        frame_count += 1

        if frame_count % 24 == 0:
            print(f"  processed {frame_count} frames ({current_time})")

    if gif_frames:
        gif_frames[0].save(
            GIF_PATH,
            save_all=True,
            append_images=gif_frames[1:],
            duration=400,
            loop=0,
        )

    print(f"\nSaved GIF: {GIF_PATH}")
    print(f"Saved first frame: {FIRST_FRAME_PATH}")
    print(f"Total frames: {frame_count}")


if __name__ == "__main__":
    main()
