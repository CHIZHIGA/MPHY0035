import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ==========================
# Configuration
# ==========================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Data", "Results")

os.makedirs(RESULTS_DIR, exist_ok=True)

P1 = "AA002"
P2 = "AB002"


# ==========================
# Helper function
# ==========================

def build_location_series(participant):
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

    df = pd.DataFrame(records)

    start_time = df["start"].min()
    end_time = df["end"].max()

    time_index = pd.date_range(start=start_time, end=end_time, freq="10s")

    location_series = pd.Series(index=time_index, dtype="object")

    for _, row in df.iterrows():
        mask = (time_index >= row["start"]) & (time_index <= row["end"])
        location_series.loc[mask] = row["location"]

    return location_series.fillna("Unknown")


# ==========================
# Build both location tables (not time grid yet)
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


df_A_annot = load_annotation(P1)
df_B_annot = load_annotation(P2)

# ==========================
# Build COMMON time grid
# ==========================

common_start = max(
    df_A_annot["start"].min(),
    df_B_annot["start"].min()
)

common_end = min(
    df_A_annot["end"].max(),
    df_B_annot["end"].max()
)

time_index = pd.date_range(
    start=common_start.floor("10s"),
    end=common_end.ceil("10s"),
    freq="10s"
)

# ==========================
# Map location onto common grid
# ==========================

def map_location(df_annot, time_index):
    location_series = pd.Series(index=time_index, dtype="object")

    for _, row in df_annot.iterrows():
        mask = (time_index >= row["start"]) & (time_index <= row["end"])
        location_series.loc[mask] = row["location"]

    return location_series.fillna("Unknown")


loc_A = map_location(df_A_annot, time_index)
loc_B = map_location(df_B_annot, time_index)

df = pd.DataFrame({
    "loc_A": loc_A,
    "loc_B": loc_B
})


# ==========================
# Define co-presence
# ==========================

df["copresence"] = (
    (df["loc_A"] == df["loc_B"]) &
    (df["loc_A"] != "Out") &
    (df["loc_A"] != "Unknown")
)


# ==========================
# Build day × hour matrix
# ==========================

df["date"] = df.index.date
df["hour"] = df.index.hour

pivot = (
    df.groupby(["date", "hour"])["copresence"]
    .mean()   # proportion of time within hour
    .unstack()
)


# ==========================
# Plot heatmap
# ==========================

plt.figure(figsize=(10, 6))

plt.imshow(
    pivot.T,
    aspect="auto",
    origin="lower",
    vmin=0,
    vmax=1
)

plt.colorbar(label="Co-presence proportion (0–1)")

plt.yticks(range(24), [f"{h}:00" for h in range(24)])
plt.xticks(range(len(pivot.index)), pivot.index, rotation=45)

plt.title(f"{P1} & {P2} – Day × Hour Co-presence")
plt.xlabel("Date")
plt.ylabel("Hour of day")

plt.tight_layout()

output_path = os.path.join(
    RESULTS_DIR,
    f"{P1}_{P2}_copresence_heatmap.png"
)

plt.savefig(output_path, dpi=300)
print("Saved:", output_path)

plt.show()

# ==========================
# Daily co-presence ratio
# ==========================

# (Remove Unknown）
valid_mask = (
    (df["loc_A"] != "Unknown") &
    (df["loc_B"] != "Unknown")
)

df_valid = df[valid_mask].copy()

df_valid["date"] = df_valid.index.date

# ==========================
# Remove partial days
# ==========================

df_valid["hour"] = df_valid.index.hour
df_valid["date"] = df_valid.index.date

hours_per_day = (
    df_valid.groupby("date")["hour"]
    .nunique()
)

print("Hours per day:")
print(hours_per_day)

full_days = hours_per_day[hours_per_day >= 20].index

df_full = df_valid[df_valid["date"].isin(full_days)]

daily_ratio = (
    df_full.groupby("date")["copresence"]
    .mean()
)

print("Daily co-presence ratio:")
print(daily_ratio)

plt.figure(figsize=(8, 4))

plt.plot(
    daily_ratio.index,
    daily_ratio.values,
    marker="o",
    linewidth=2
)

plt.ylim(0, 1)
plt.ylabel("Daily co-presence ratio")
plt.xlabel("Date")
plt.title(f"{P1} & {P2} – Daily Co-presence Ratio (Full days only)")

plt.xticks(rotation=45)
plt.grid(alpha=0.3)

plt.tight_layout()

output_path = os.path.join(
    RESULTS_DIR,
    f"{P1}_{P2}_copresence_ratio.png"
)

plt.savefig(output_path, dpi=300)
print("Saved:", output_path)

plt.show()