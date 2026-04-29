import json
import os
from datetime import timedelta

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_A001")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "001")
os.makedirs(RESULTS_DIR, exist_ok=True)

PARTICIPANT = "AA001"

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
START_TIME_STR = "2023-06-21 18:00"
END_TIME_STR = "2023-06-22 18:00"
INTERVAL_MINUTES = 10

GIF_NAME = f"{PARTICIPANT}_activity_location_10min.gif"
FIRST_FRAME_NAME = f"{PARTICIPANT}_activity_location_10min_first_frame.png"

FLOORPLAN_PATH = os.path.join(DATA_DIR, "map", "image.png")
LOCATION_PATH = os.path.join(DATA_DIR, PARTICIPANT, "annotator.json")
ACTIVITY_PATH = os.path.join(
    DATA_DIR, PARTICIPANT, "auto_activity_level_20231102_094535.json"
)


# =====================================
# Visual settings
# =====================================

ROOM_POSITIONS = {
    "Living": (0.37, 0.69),
    "Office": (0.37, 0.38),
    "Kitchen": (0.86, 0.69),
    "Bathroom": (1.60, 0.69),
    "Bedroom": (1.60, 0.38),
    "Stairs": (0.61, 0.50),
}

MAIN_ROOMS = set(ROOM_POSITIONS.keys())

ACTIVITY_COLORS = {
    "Sleep": "#355C7D",
    "Sedentary": "#90A4AE",
    "Light activity": "#F9A826",
    "Moderate to Vigorous activity": "#D64541",
    "Unknown activity": "#CFCFCF",
}


# =====================================
# Load data
# =====================================

def load_location_annotations(participant):
    """Load timerange location annotations."""
    with open(os.path.join(DATA_DIR, participant, "annotator.json"), "r") as f:
        annot = json.load(f)

    records = []
    for shape in annot.get("shapes", []):
        if shape.get("type") != "timerange":
            continue
        location = shape.get("data", {}).get("location")
        if location is None:
            continue
        records.append(
            {
                "start": parse_timestamp_ms(shape["start"]),
                "end": parse_timestamp_ms(shape["end"]),
                "label": location,
            }
        )
    return records


def load_activity_annotations(participant):
    """Load timerange activity annotations."""
    activity_file = os.path.join(
        DATA_DIR, participant, "auto_activity_level_20231102_094535.json"
    )
    with open(activity_file, "r") as f:
        annot = json.load(f)

    records = []
    for shape in annot.get("shapes", []):
        if shape.get("type") != "timerange":
            continue
        activity_level = shape.get("data", {}).get("activityLevel")
        if activity_level is None:
            continue
        records.append(
            {
                "start": parse_timestamp_ms(shape["start"]),
                "end": parse_timestamp_ms(shape["end"]),
                "label": activity_level,
            }
        )
    return records


def get_dominant_label(df, current_time, interval_minutes, label_col="label"):
    """Return the label with the largest overlap in the time window."""
    interval_start = current_time
    interval_end = current_time + timedelta(minutes=interval_minutes)

    overlap_seconds_by_label = {}
    for row in df:
        if row["start"] >= interval_end or row["end"] <= interval_start:
            continue

        overlap_start = max(row["start"], interval_start)
        overlap_end = min(row["end"], interval_end)
        overlap_seconds = max((overlap_end - overlap_start).total_seconds(), 0)

        if overlap_seconds <= 0:
            continue

        label = row[label_col]
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


def parse_timestamp_ms(timestamp_ms):
    return datetime_from_unix_ms(int(timestamp_ms))


def datetime_from_unix_ms(timestamp_ms):
    from datetime import datetime

    return datetime.fromtimestamp(timestamp_ms / 1000.0)


def parse_datetime_string(value):
    from datetime import datetime

    return datetime.strptime(value, DATETIME_FORMAT)


def render_frame(
    current_time,
    location_label,
    activity_label,
    floorplan_img,
    img_aspect,
):
    """Render a single floorplan frame."""
    activity_display = activity_label or "Unknown activity"
    marker_color = ACTIVITY_COLORS.get(activity_display, ACTIVITY_COLORS["Unknown activity"])

    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    ax.imshow(floorplan_img, extent=[0, img_aspect, 0, 1], aspect="auto", zorder=0)

    if location_label in MAIN_ROOMS:
        x, y = ROOM_POSITIONS[location_label]
        ax.plot(
            x,
            y,
            "o",
            markersize=18,
            color=marker_color,
            markeredgecolor="#FFFFFF",
            markeredgewidth=2.5,
            zorder=5,
        )
        ax.text(
            x,
            y - 0.07,
            PARTICIPANT,
            ha="center",
            va="top",
            fontsize=10,
            weight="bold",
            color="#222222",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.80),
        )
    else:
        display_location = location_label or "Unknown"
        ax.text(
            0.03,
            0.90,
            f"{PARTICIPANT} position: {display_location}",
            fontsize=10,
            color="#222222",
            transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
        )

    time_str = current_time.strftime("%Y-%m-%d %H:%M")
    ax.text(
        0.5,
        0.98,
        time_str,
        ha="center",
        va="top",
        fontsize=12,
        weight="bold",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    location_display = location_label or "Unknown"
    ax.text(
        0.5,
        0.06,
        f"Location: {location_display}",
        ha="center",
        va="bottom",
        fontsize=10,
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.80),
    )
    ax.text(
        0.5,
        0.01,
        f"Activity: {activity_display}",
        ha="center",
        va="bottom",
        fontsize=10,
        weight="bold",
        color=marker_color,
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    legend_handles = [
        mpatches.Patch(color=color, label=label)
        for label, color in ACTIVITY_COLORS.items()
    ]
    ax.legend(
        handles=legend_handles,
        title="AA001 activity",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        framealpha=0.95,
    )

    ax.set_xlim(0, img_aspect)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.tight_layout()

    fig.canvas.draw()
    buf = fig.canvas.buffer_rgba()
    ncols, nrows = fig.canvas.get_width_height()
    rgba_image = np.frombuffer(buf, dtype=np.uint8).reshape((nrows, ncols, 4))
    rgb_image = rgba_image[:, :, :3]
    return fig, rgb_image


def main():
    print(f"Loading location data from: {LOCATION_PATH}")
    print(f"Loading activity data from: {ACTIVITY_PATH}")

    df_location = load_location_annotations(PARTICIPANT)
    df_activity = load_activity_annotations(PARTICIPANT)

    print(f"Loaded {len(df_location)} location intervals")
    print(f"Loaded {len(df_activity)} activity intervals")

    floorplan_img = Image.open(FLOORPLAN_PATH)
    img_width, img_height = floorplan_img.size
    img_aspect = img_width / img_height

    gif_path = os.path.join(RESULTS_DIR, GIF_NAME)
    first_frame_path = os.path.join(RESULTS_DIR, FIRST_FRAME_NAME)

    print(f"Generating GIF with {INTERVAL_MINUTES}-minute intervals...")
    start_time = parse_datetime_string(START_TIME_STR)
    end_time = parse_datetime_string(END_TIME_STR)

    print(f"Date range: {start_time} to {end_time}")
    print(f"Output GIF: {gif_path}")

    current_time = start_time
    frame_count = 0
    first_frame_saved = False

    gif_frames = []

    while current_time <= end_time:
        location_label = get_dominant_label(
            df_location, current_time, INTERVAL_MINUTES
        )
        activity_label = get_dominant_label(
            df_activity, current_time, INTERVAL_MINUTES
        )

        fig, rgb_image = render_frame(
            current_time,
            location_label,
            activity_label,
            floorplan_img,
            img_aspect,
        )

        gif_frames.append(Image.fromarray(rgb_image))

        if not first_frame_saved:
            fig.savefig(first_frame_path, dpi=300, bbox_inches="tight")
            first_frame_saved = True

        plt.close(fig)

        current_time += timedelta(minutes=INTERVAL_MINUTES)
        frame_count += 1

        if frame_count % 24 == 0:
            print(f"  Processed {frame_count} frames ({current_time})")

    if gif_frames:
        gif_frames[0].save(
            gif_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=500,
            loop=0,
        )

    print(f"\nSaved GIF: {gif_path}")
    print(f"Saved first frame: {first_frame_path}")
    print(f"Total frames: {frame_count}")


if __name__ == "__main__":
    main()
