import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import imageio.v2 as imageio

# ==========================
# Configuration
# ==========================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Data", "Results")

os.makedirs(RESULTS_DIR, exist_ok=True)

P1 = "AA002"
P2 = "AB002"
TARGET_DATE = "2023-07-17"

# ==========================
# Load annotation helper
# ==========================

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


def build_hourly_locations(df_annot):

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

    hourly_loc = (
        df_day.groupby("hour")["location"]
        .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "Unknown")
    )

    return hourly_loc


# ==========================
# Load both participants
# ==========================

df_A_annot = load_annotation(P1)
df_B_annot = load_annotation(P2)

hourly_A = build_hourly_locations(df_A_annot)
hourly_B = build_hourly_locations(df_B_annot)

# ==========================
# Floorplan layout
# ==========================

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
# Generate frames
# ==========================

frame_files = []

for hour in range(24):

    loc_A = hourly_A.get(hour, "Unknown")
    loc_B = hourly_B.get(hour, "Unknown")

    fig, ax = plt.subplots(figsize=(6, 6))

    # Draw outer square
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, linewidth=2))

    # Draw 2x2 grid
    ax.plot([0.5, 0.5], [0, 1], linewidth=1)
    ax.plot([0, 1], [0.5, 0.5], linewidth=1)

    # Room labels
    for room, (x, y) in room_positions.items():
        ax.text(x, y, room, ha="center", va="center")

    # Determine color (copresence)
    if (loc_A == loc_B) and (loc_A in room_positions):
        color = "green"
    else:
        color = "red"

    # Plot participant A
    if loc_A in room_positions:
        x, y = room_positions[loc_A]
        ax.plot(x - 0.05, y, 'o', markersize=15, color=color)
    else:
        ax.plot(1.15, 0.6, '^', markersize=15, color=color)

    # Plot participant B
    if loc_B in room_positions:
        x, y = room_positions[loc_B]
        ax.plot(x + 0.05, y, 'o', markersize=15, color=color)
    else:
        ax.plot(1.15, 0.4, '^', markersize=15, color=color)

    ax.set_xlim(-0.2, 1.4)
    ax.set_ylim(-0.2, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.set_title(f"{P1} & {P2} – {TARGET_DATE} – {hour:02d}:00")

    frame_path = os.path.join(
        RESULTS_DIR,
        f"frame_{hour:02d}.png"
    )

    plt.savefig(frame_path, dpi=150)
    plt.close()

    frame_files.append(frame_path)

# ==========================
# Create GIF
# ==========================

gif_path = os.path.join(
    RESULTS_DIR,
    f"{P1}_{P2}_{TARGET_DATE}_copresence.gif"
)

with imageio.get_writer(gif_path, mode='I', duration=0.8) as writer:
    for filename in frame_files:
        image = imageio.imread(filename)
        writer.append_data(image)

print("GIF saved:", gif_path)