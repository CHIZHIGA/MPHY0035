import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ==========================
# Configuration
# ==========================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "001")

os.makedirs(RESULTS_DIR, exist_ok=True)

P1 = "AA001"
P2 = "AB001"


# ==========================
# Helper function
# ==========================

def load_annotation(participant):
    annot_file = os.path.join(DATA_DIR, "Home_A001", participant, "annotator.json")

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

print(f"Loaded {len(df_A_annot)} records for {P1}")
print(f"Loaded {len(df_B_annot)} records for {P2}")

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

print(f"Common time range: {common_start} to {common_end}")

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

print(f"\nHeatmap data: {len(pivot)} days × 24 hours")
print(f"Date range: {pivot.index[0]} to {pivot.index[-1]}")

# ==========================
# Plot heatmap
# ==========================

fig, ax = plt.subplots(figsize=(14, 7))

im = ax.imshow(
    pivot.T,
    aspect="auto",
    origin="lower",
    vmin=0,
    vmax=1,
    cmap="YlOrRd"
)

cbar = plt.colorbar(im, ax=ax, label="Co-presence proportion (0–1)")

ax.set_yticks(range(24))
ax.set_yticklabels([f"{h}:00" for h in range(24)])
ax.set_xticks(range(len(pivot.index)))
ax.set_xticklabels(pivot.index, rotation=45)

ax.set_title(f"{P1} & {P2} – Day × Hour Co-presence", fontsize=14, weight='bold')
ax.set_xlabel("Date", fontsize=12)
ax.set_ylabel("Hour of day", fontsize=12)

plt.tight_layout()

output_path = os.path.join(
    RESULTS_DIR,
    f"{P1}_{P2}_copresence_heatmap.png"
)

plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"\n✓ Heatmap saved: {output_path}")

plt.close()

# ==========================
# Daily co-presence ratio
# ==========================

# Remove Unknown
valid_mask = (
    (df["loc_A"] != "Unknown") &
    (df["loc_B"] != "Unknown")
)

df_valid = df[valid_mask].copy()

df_valid["date"] = df_valid.index.date
df_valid["hour"] = df_valid.index.hour

hours_per_day = (
    df_valid.groupby("date")["hour"]
    .nunique()
)

print("\nHours per day:")
print(hours_per_day)

full_days = hours_per_day[hours_per_day >= 20].index

df_full = df_valid[df_valid["date"].isin(full_days)]

daily_ratio = (
    df_full.groupby("date")["copresence"]
    .mean()
)

print("\nDaily co-presence ratio (full days only):")
print(daily_ratio)

fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(
    daily_ratio.index,
    daily_ratio.values,
    marker="o",
    linewidth=2.5,
    markersize=8,
    color="#FF8C00"
)

ax.set_ylim(0, 1)
ax.set_ylabel("Daily co-presence ratio", fontsize=12)
ax.set_xlabel("Date", fontsize=12)
ax.set_title(f"{P1} & {P2} – Daily Co-presence Ratio (Full days only)", fontsize=14, weight='bold')

ax.set_xticklabels(daily_ratio.index, rotation=45)
ax.grid(alpha=0.3)

plt.tight_layout()

output_path = os.path.join(
    RESULTS_DIR,
    f"{P1}_{P2}_copresence_ratio.png"
)

plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"✓ Daily ratio plot saved: {output_path}")

plt.close()

print("\n✓ Analysis complete!")
