import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import imageio
from datetime import datetime, timedelta

# =====================================
# Configuration
# =====================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Data", "Results")
os.makedirs(RESULTS_DIR, exist_ok=True)

P1 = "AA002"
P2 = "AB002"

START_TIME = pd.to_datetime("2023-07-14 13:00")
END_TIME   = pd.to_datetime("2023-07-21 09:00")

GIF_NAME = f"{P1}_{P2}_week_copresence.gif"


# =====================================
# Load annotation
# =====================================

def load_annotation(participant):
    annot_file = os.path.join(DATA_DIR, participant, "annotator.json")

    with open(annot_file, "r") as f:
        annot = json.load(f)

    records = []
    for s in annot.get("shapes", []):
        if s.get("type") != "timerange":
            continue
        location = s.get("data", {}).get("location")
        if location is None:
            continue
        records.append({
            "start": pd.to_datetime(s["start"], unit="ms"),
            "end": pd.to_datetime(s["end"], unit="ms"),
            "location": location
        })
    return pd.DataFrame(records)


def get_hourly_location(df_annot, current_time):
    hour_start = current_time
    hour_end   = current_time + pd.Timedelta(hours=1)

    mask = (df_annot["start"] < hour_end) & (df_annot["end"] > hour_start)
    df_overlap = df_annot[mask]

    if df_overlap.empty:
        return "Unknown"

    return df_overlap["location"].mode().iloc[0]


df_A = load_annotation(P1)
df_B = load_annotation(P2)


# =====================================
# Floorplan layout
# =====================================

room_positions = {
    "Bedroom": (0.25, 0.75),
    "Kitchen": (0.75, 0.75),
    "Living":  (0.25, 0.25),
    "Office":  (0.75, 0.25),
}

main_rooms = list(room_positions.keys())


# =====================================
# Generate GIF
# =====================================

gif_path = os.path.join(RESULTS_DIR, GIF_NAME)

with imageio.get_writer(gif_path, mode='I', duration=1000) as writer:

    current_time = START_TIME
    frame_count = 0

    while current_time <= END_TIME:

        loc_A = get_hourly_location(df_A, current_time)
        loc_B = get_hourly_location(df_B, current_time)

        together = (loc_A == loc_B) and (loc_A in main_rooms)

        fig, ax = plt.subplots(figsize=(6, 6))

        # Draw house square
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, linewidth=2, color="black"))

        # Grid lines
        ax.plot([0.5, 0.5], [0, 1], linewidth=1, color="black")
        ax.plot([0, 1], [0.5, 0.5], linewidth=1, color="black")

        # Highlight room if together
        if together:
            x, y = room_positions[loc_A]
            ax.add_patch(
                plt.Rectangle((x-0.25, y-0.25), 0.5, 0.5,
                              color="#2ecc71", alpha=0.2)
            )

        # Room labels
        for room, (x, y) in room_positions.items():
            ax.text(x, y, room, ha="center", va="center", fontsize=10)

        # Determine marker color
        color = "#2ecc71" if together else "#e74c3c"

        # Plot participant A
        if loc_A in main_rooms:
            x, y = room_positions[loc_A]
            ax.plot(x - 0.05, y, 'o', markersize=14, color=color)
        else:
            ax.plot(1.15, 0.6, '^', markersize=14, color=color)

        # Plot participant B
        if loc_B in main_rooms:
            x, y = room_positions[loc_B]
            ax.plot(x + 0.05, y, 'o', markersize=14, color=color)
        else:
            ax.plot(1.15, 0.4, '^', markersize=14, color=color)

        # Night shading
        if 0 <= current_time.hour < 6:
            ax.add_patch(
                plt.Rectangle((-0.2, -0.2), 1.6, 1.6,
                              color="gray", alpha=0.15)
            )

        # Status text
        status_text = "TOGETHER" if together else "SEPARATE"
        status_color = "#2ecc71" if together else "#e74c3c"

        ax.text(0.5, 1.15, f"{current_time.strftime('%a %d %b %Y – %H:00')}",
                ha="center", fontsize=11)

        ax.text(0.5, -0.15, f"Status: {status_text}",
                ha="center", fontsize=12, color=status_color)

        ax.set_xlim(-0.2, 1.4)
        ax.set_ylim(-0.2, 1.3)
        ax.set_aspect("equal")
        ax.axis("off")

        # Convert to image array
        fig.canvas.draw()
        image = np.frombuffer(fig.canvas.tostring_argb(), dtype='uint8')
        image = image.reshape(fig.canvas.get_width_height()[::-1] + (4,))  # ARGB has 4 channels
        writer.append_data(image)

        plt.close(fig)

        current_time += timedelta(hours=1)
        frame_count += 1

print(f"GIF saved to: {gif_path}")
print(f"Total frames: {frame_count}")