import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# ==========================
# Configuration
# ==========================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "AB002")
RESULTS_DIR = os.path.join(BASE_DIR, "Data", "Results")

os.makedirs(RESULTS_DIR, exist_ok=True)

TARGET_DATE = "2023-07-17"


# ==========================
# Load annotation
# ==========================

annot_file = os.path.join(DATA_DIR, "annotator.json")

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

df_annot = pd.DataFrame(records)


# ==========================
# Build 10-second grid for target day
# ==========================

day_start = pd.to_datetime(TARGET_DATE)
day_end = day_start + pd.Timedelta(days=1)

time_index = pd.date_range(start=day_start, end=day_end, freq="10s")

location_series = pd.Series(index=time_index, dtype="object")

for _, row in df_annot.iterrows():
    mask = (time_index >= row["start"]) & (time_index <= row["end"])
    location_series.loc[mask] = row["location"]

location_series = location_series.fillna("Unknown")

df_day = pd.DataFrame({
    "time": location_series.index,
    "location": location_series.values
})

df_day["hour"] = df_day["time"].dt.hour


# ==========================
# Hourly dominant location
# ==========================

hourly_loc = (
    df_day.groupby("hour")["location"]
    .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "Unknown")
)


# ==========================
# Define floorplan layout
# ==========================

# Coordinates for four main rooms (centers)
room_positions = {
    "Bedroom": (0.25, 0.75),
    "Kitchen": (0.75, 0.75),
    "Living":  (0.25, 0.25),
    "Office":  (0.75, 0.25),
}

outside_categories = [
    "Indoor transition",
    "Other",
    "Out",
    "Unknown"
]


# ==========================
# Draw frames
# ==========================

for hour in range(24):

    loc = hourly_loc.get(hour, "Unknown")

    fig, ax = plt.subplots(figsize=(6, 6))

    # Draw outer square
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, linewidth=2))

    # Draw 2x2 inner grid
    ax.plot([0.5, 0.5], [0, 1], linewidth=1)
    ax.plot([0, 1], [0.5, 0.5], linewidth=1)

    # Room labels
    for room, (x, y) in room_positions.items():
        ax.text(x, y, room, ha="center", va="center")

    # Plot person marker
    if loc in room_positions:
        x, y = room_positions[loc]
        ax.plot(x, y, 'o', markersize=15)  # circle
    else:
        # outside square
        ax.plot(1.15, 0.5, '^', markersize=15)  # triangle
        ax.text(1.15, 0.6, loc, ha="center")

    ax.set_xlim(-0.2, 1.4)
    ax.set_ylim(-0.2, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.set_title(f"AB002 – {TARGET_DATE} – {hour:02d}:00")

    output_file = os.path.join(
        RESULTS_DIR,
        f"AB002_{TARGET_DATE}_hour_{hour:02d}.png"
    )

    plt.savefig(output_file, dpi=150)
    plt.close()

print("24 frames generated.")