import os
import json
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches


# =====================================
# Read participant from command line
# =====================================

if len(sys.argv) < 2:
    print("Usage: python plot_location_from_annotation.py <PARTICIPANT_ID>")
    sys.exit(1)

PARTICIPANT = sys.argv[1]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", PARTICIPANT)
RESULTS_DIR = os.path.join(BASE_DIR, "Data", "Results")

ANNOT_FILE = os.path.join(DATA_DIR, "annotator.json")

os.makedirs(RESULTS_DIR, exist_ok=True)


print(f"Processing participant: {PARTICIPANT}")


# =====================================
# Load annotation file
# =====================================

with open(ANNOT_FILE, "r") as f:
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

loc_df = pd.DataFrame(records)

if loc_df.empty:
    print("No valid location annotations found.")
    sys.exit(1)


# =====================================
# Build 10-second grid
# =====================================

start_time = loc_df["start"].min()
end_time = loc_df["end"].max()

time_index = pd.date_range(start=start_time, end=end_time, freq="10s")

location_series = pd.Series(index=time_index, dtype="object")

for _, row in loc_df.iterrows():
    mask = (time_index >= row["start"]) & (time_index <= row["end"])
    location_series.loc[mask] = row["location"]

location_series = location_series.fillna("Unknown")


# =====================================
# Convert to day × hour matrix
# =====================================

df = pd.DataFrame({
    "time": location_series.index,
    "location": location_series.values
})

df["date"] = df["time"].dt.date
df["hour"] = df["time"].dt.hour

locations = sorted(df["location"].unique())
loc_map = {loc: i for i, loc in enumerate(locations)}

df["loc_code"] = df["location"].map(loc_map)

pivot = (
    df.groupby(["date", "hour"])["loc_code"]
    .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else np.nan)
    .unstack()
)


# =====================================
# Define discrete colormap
# =====================================

color_list = [
    "#1f78b4",  # Bedroom
    "#33a02c",  # Indoor transition
    "#6a3d9a",  # Kitchen
    "#ff7f00",  # Living
    "#b15928",  # Office
    "#bdbdbd",  # Other
    "#ffd92f",  # Out
    "#17becf",  # Unknown
]

cmap = ListedColormap(color_list[:len(loc_map)])


# =====================================
# Plot
# =====================================

plt.figure(figsize=(10, 6))

plt.imshow(pivot.T, aspect="auto", origin="lower", cmap=cmap)

plt.yticks(range(24), [f"{h}:00" for h in range(24)])
plt.xticks(range(len(pivot.index)), pivot.index, rotation=45)

legend_patches = [
    mpatches.Patch(color=color_list[i], label=loc)
    for loc, i in loc_map.items()
]

plt.legend(
    handles=legend_patches,
    title="Location",
    bbox_to_anchor=(1.02, 1),
    loc="upper left"
)

plt.title(f"{PARTICIPANT} – Daily location timeline (hourly mode)")
plt.xlabel("Date")
plt.ylabel("Hour of day")

plt.tight_layout()

output_path = os.path.join(
    RESULTS_DIR,
    f"{PARTICIPANT}_location_timeline.png"
)

plt.savefig(output_path, dpi=300)
print("Saved:", output_path)

plt.show()