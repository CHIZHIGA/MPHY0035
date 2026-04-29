import os
import json
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches


# ==========================
# Configuration
# ==========================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "Data", "Home_A001")
RESULTS_DIR = os.path.join(BASE_DIR, "Results", "001")

os.makedirs(RESULTS_DIR, exist_ok=True)

P1 = "AA001"
P2 = "AB001"

LOCATION_COLORS = {
    "Bathroom": "#e7298a",            # Pink
    "Bedroom": "#1f78b4",             # Blue
    "Dining": "#66c2a5",              # Teal
    "Entrance": "#8da0cb",            # Lavender blue
    "Indoor transition": "#33a02c",   # Green
    "Kitchen": "#6a3d9a",             # Purple
    "Living": "#ff7f00",              # Orange
    "Office": "#b15928",              # Brown
    "Outdoors": "#ffd92f",            # Yellow
    "Unknown": "#cccccc",             # Light gray
}

LOCATION_ORDER = list(LOCATION_COLORS.keys())


# ==========================
# Load annotation
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


df_A = load_annotation(P1)
df_B = load_annotation(P2)

print(f"Loaded {len(df_A)} records for {P1}")
print(f"Loaded {len(df_B)} records for {P2}")


# ==========================
# Dominant-location helpers
# ==========================

def get_dominant_location(df_annot, window_start, window_end):
    """Return the location with the greatest overlap in a time window."""
    mask = (df_annot["start"] < window_end) & (df_annot["end"] > window_start)
    df_overlap = df_annot.loc[mask].copy()

    if df_overlap.empty:
        return "Unknown"

    df_overlap["overlap_start"] = df_overlap["start"].clip(lower=window_start)
    df_overlap["overlap_end"] = df_overlap["end"].clip(upper=window_end)
    df_overlap["overlap_seconds"] = (
        df_overlap["overlap_end"] - df_overlap["overlap_start"]
    ).dt.total_seconds()

    grouped = (
        df_overlap.groupby("location", as_index=False)["overlap_seconds"]
        .sum()
        .sort_values(["overlap_seconds", "location"], ascending=[False, True])
    )
    return grouped.iloc[0]["location"]


def build_hourly_location_pivot(df_annot):
    """Build a day x hour matrix from true interval overlap."""
    start_day = df_annot["start"].min().floor("D")
    end_day = df_annot["end"].max().floor("D")
    days = pd.date_range(start=start_day, end=end_day, freq="D")

    rows = []
    for day in days:
        row = {}
        for hour in range(24):
            window_start = day + pd.Timedelta(hours=hour)
            window_end = window_start + pd.Timedelta(hours=1)
            row[hour] = get_dominant_location(df_annot, window_start, window_end)
        rows.append(row)

    pivot = pd.DataFrame(rows, index=days.date)
    pivot = pivot.reindex(columns=range(24))
    return pivot


# ==========================
# Generate separate heatmaps for each participant
# ==========================

def create_location_heatmap(participant, df_annot, participant_name):
    """Create hourly heatmap with room colors"""
    pivot_labels = build_hourly_location_pivot(df_annot)

    locations = [loc for loc in LOCATION_ORDER if loc in set(pivot_labels.stack())]
    loc_map = {loc: i for i, loc in enumerate(locations)}
    pivot = pivot_labels.apply(lambda col: col.map(loc_map)).astype(float)

    # Create color list based on locations in data
    color_list = [LOCATION_COLORS.get(loc, "#bdbdbd") for loc in locations]
    cmap = ListedColormap(color_list)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 6))
    
    im = ax.imshow(pivot.T, aspect="auto", origin="lower", cmap=cmap)
    
    ax.set_yticks(range(24))
    ax.set_yticklabels([f"{h}:00" for h in range(24)])
    ax.set_xticks(range(len(pivot.index)))
    ax.set_xticklabels(pivot.index, rotation=45)
    
    # Create legend
    legend_patches = [
        mpatches.Patch(color=color_list[i], label=loc)
        for loc, i in loc_map.items()
    ]
    
    ax.legend(
        handles=legend_patches,
        title="Location",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=10
    )
    
    ax.set_title(f"{participant_name} – Daily Location Timeline (Hourly Mode)", 
                fontsize=14, weight='bold')
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Hour of day", fontsize=12)
    
    plt.tight_layout()
    
    output_path = os.path.join(
        RESULTS_DIR,
        f"{participant_name}_location_timeline.png"
    )
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    
    plt.close()
    
    return locations


# Create heatmaps for both participants
print("\nGenerating location heatmaps...")
print(f"\n{P1}:")
locs_A = create_location_heatmap(P1, df_A, P1)

print(f"\n{P2}:")
locs_B = create_location_heatmap(P2, df_B, P2)


# ==========================
# Combined visualization: Co-location with location context
# ==========================

# For combined view, show where they are together vs apart
# Color by location when together, gray when apart
common_start = max(df_A["start"].min(), df_B["start"].min()).floor("D")
common_end = min(df_A["end"].max(), df_B["end"].max()).floor("D")
common_days = pd.date_range(start=common_start, end=common_end, freq="D")

combined_rows = []
for day in common_days:
    row = {}
    for hour in range(24):
        window_start = day + pd.Timedelta(hours=hour)
        window_end = window_start + pd.Timedelta(hours=1)
        loc_a = get_dominant_location(df_A, window_start, window_end)
        loc_b = get_dominant_location(df_B, window_start, window_end)
        row[hour] = loc_a if loc_a == loc_b else "Apart"
    combined_rows.append(row)

pivot_combined_labels = pd.DataFrame(combined_rows, index=common_days.date)
pivot_combined = pivot_combined_labels.reindex(columns=range(24))

# Color palette for combined view
room_colors_combined = {
    "Bedroom": "#1f78b4",
    "Kitchen": "#6a3d9a",
    "Living": "#ff7f00",
    "Office": "#b15928",
    "Bathroom": "#e7298a",
    "Stairs": "#7fc97f",
    "Apart": "#d3d3d3",           # Light gray when apart
    "Unknown": "#cccccc",
}

locations_combined = [
    loc for loc in ["Bathroom", "Bedroom", "Kitchen", "Living", "Office", "Stairs", "Unknown", "Apart"]
    if loc in set(pivot_combined.stack())
]
loc_map_combined = {loc: i for i, loc in enumerate(locations_combined)}
pivot_combined = pivot_combined.apply(lambda col: col.map(loc_map_combined)).astype(float)

color_list_combined = [room_colors_combined.get(loc, "#cccccc") for loc in locations_combined]
cmap_combined = ListedColormap(color_list_combined)

# Plot combined view
fig, ax = plt.subplots(figsize=(14, 6))

im = ax.imshow(pivot_combined.T, aspect="auto", origin="lower", cmap=cmap_combined)

ax.set_yticks(range(24))
ax.set_yticklabels([f"{h}:00" for h in range(24)])
ax.set_xticks(range(len(pivot_combined.index)))
ax.set_xticklabels(pivot_combined.index, rotation=45)

legend_patches_combined = [
    mpatches.Patch(color=color_list_combined[i], label=loc)
    for loc, i in loc_map_combined.items()
]

ax.legend(
    handles=legend_patches_combined,
    title="Location Status",
    bbox_to_anchor=(1.02, 1),
    loc="upper left",
    fontsize=10
)

ax.set_title(f"{P1} & {P2} – Combined Location Timeline (Hourly Mode)\nColored by location when together, Gray when apart", 
            fontsize=14, weight='bold')
ax.set_xlabel("Date", fontsize=12)
ax.set_ylabel("Hour of day", fontsize=12)

plt.tight_layout()

output_path_combined = os.path.join(
    RESULTS_DIR,
    f"{P1}_{P2}_combined_location_timeline.png"
)

plt.savefig(output_path_combined, dpi=300, bbox_inches='tight')
print(f"\n✓ Saved: {output_path_combined}")

plt.close()

print("\n✓ All location heatmaps generated!")
