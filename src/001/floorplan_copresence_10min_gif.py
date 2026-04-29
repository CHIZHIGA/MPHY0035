import json
import os
from datetime import datetime, timedelta

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

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

P1 = "AA001"
P2 = "AB001"

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
START_TIME_STR = "2023-06-21 18:00"
END_TIME_STR = "2023-06-22 18:00"
INTERVAL_MINUTES = 10

GIF_NAME = f"{P1}_{P2}_copresence_10min.gif"
FIRST_FRAME_NAME = f"{P1}_{P2}_copresence_10min_first_frame.png"

FLOORPLAN_PATH = os.path.join(DATA_DIR, "map", "image.png")


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


def parse_datetime_string(value):
    return datetime.strptime(value, DATETIME_FORMAT)


def parse_timestamp_ms(timestamp_ms):
    return datetime.fromtimestamp(int(timestamp_ms) / 1000.0)


def load_location_annotations(participant):
    """Load timerange location annotations for a participant."""
    annot_path = os.path.join(DATA_DIR, participant, "annotator.json")
    with open(annot_path, "r") as f:
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


def get_dominant_label(records, current_time, interval_minutes):
    """Return the location with the largest overlap in the time window."""
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


def render_frame(current_time, loc_a, loc_b, floorplan_img, img_aspect):
    together = (loc_a == loc_b) and (loc_a in MAIN_ROOMS)
    marker_color = "#00DD00" if together else "#DD0000"

    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    ax.imshow(floorplan_img, extent=[0, img_aspect, 0, 1], aspect="auto", zorder=0)

    if loc_a in MAIN_ROOMS:
        x, y = ROOM_POSITIONS[loc_a]
        ax.plot(
            x - 0.08,
            y,
            "o",
            markersize=14,
            color=marker_color,
            markeredgecolor="#FFFFFF",
            markeredgewidth=2.5,
            zorder=5,
        )
    else:
        ax.text(
            0.05,
            0.95,
            f"{P1}: {loc_a or 'Unknown'}",
            fontsize=10,
            color=marker_color,
            transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
        )

    if loc_b in MAIN_ROOMS:
        x, y = ROOM_POSITIONS[loc_b]
        ax.plot(
            x + 0.08,
            y,
            "s",
            markersize=14,
            color=marker_color,
            markeredgecolor="#FFFFFF",
            markeredgewidth=2.5,
            zorder=5,
        )
    else:
        ax.text(
            0.05,
            0.90,
            f"{P2}: {loc_b or 'Unknown'}",
            fontsize=10,
            color=marker_color,
            transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
        )

    ax.text(
        0.5,
        0.98,
        current_time.strftime("%Y-%m-%d %H:%M"),
        ha="center",
        va="top",
        fontsize=12,
        weight="bold",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    status_text = "TOGETHER" if together else "SEPARATE"
    ax.text(
        0.5,
        -0.02,
        f"Status: {status_text}",
        ha="center",
        va="bottom",
        fontsize=11,
        weight="bold",
        transform=ax.transAxes,
        color=marker_color,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    ax.text(
        0.5,
        0.05,
        f"{P1}: {loc_a or 'Unknown'} | {P2}: {loc_b or 'Unknown'}",
        ha="center",
        va="bottom",
        fontsize=9,
        style="italic",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.7),
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
    print(f"Loading annotation data for {P1} and {P2}...")
    df_a = load_location_annotations(P1)
    df_b = load_location_annotations(P2)

    print(f"Loaded {len(df_a)} intervals for {P1}")
    print(f"Loaded {len(df_b)} intervals for {P2}")

    floorplan_img = Image.open(FLOORPLAN_PATH)
    img_width, img_height = floorplan_img.size
    img_aspect = img_width / img_height

    gif_path = os.path.join(RESULTS_DIR, GIF_NAME)
    first_frame_path = os.path.join(RESULTS_DIR, FIRST_FRAME_NAME)

    start_time = parse_datetime_string(START_TIME_STR)
    end_time = parse_datetime_string(END_TIME_STR)

    print(f"Generating location-only co-presence GIF: {gif_path}")

    current_time = start_time
    frame_count = 0
    first_frame_saved = False
    gif_frames = []

    while current_time <= end_time:
        loc_a = get_dominant_label(df_a, current_time, INTERVAL_MINUTES)
        loc_b = get_dominant_label(df_b, current_time, INTERVAL_MINUTES)

        fig, rgb_image = render_frame(
            current_time, loc_a, loc_b, floorplan_img, img_aspect
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

    print(f"Saved GIF: {gif_path}")
    print(f"Saved first frame: {first_frame_path}")
    print(f"Total frames: {frame_count}")


if __name__ == "__main__":
    main()
