# A. `plot_location_from_annotation.py`

## Objective

Visualise a single participant’s daily location pattern over time.

## What it does

* Loads annotation data (`annotator.json`)
* Constructs a **10-second resolution time series**
* Maps location labels onto the timeline
* Aggregates into **hourly dominant location (mode)**
* Converts into a **day × hour matrix**
* Plots a **categorical heatmap**

## Output

* `*_location_timeline.png`

## Key contribution

* Provides the **baseline temporal representation of location**
* Forms the foundation for all later analysis

---

# B. `plot_AB002_2023_07_17_floorplan.py`

## Objective

Map a participant’s daily behaviour onto a **spatial floorplan representation**.

## What it does

* Extracts one day of data
* Computes **hourly dominant room**
* Defines a simplified home layout:

  * Bedroom / Kitchen / Living / Office
* Plots location per hour on a **2D floorplan**
* Outside locations shown separately

## Output

* 24 hourly frames (PNG)

## Key contribution

* Converts **time-based data → spatial behaviour**
* Bridges raw data and intuitive visualisation

---

# C. `floorplan_copresence_gif.py`

## Objective

Visualise **co-presence of two participants over a single day**.

## What it does

* Loads both participants’ annotations
* Computes hourly locations
* Plots both individuals on the same floorplan
* Encodes co-presence:

  * Same room → green
  * Different → red
* Generates a **GIF animation**

## Output

* `*_copresence.gif`

## Key contribution

* First **interaction-level visualisation**
* Shows when two people are together

---

# D. `floorplan_copresence_week_gif.py`

## Objective

Extend co-presence visualisation to a **longer time period with presentation-quality output**.

## What it does

* Processes a multi-day range (e.g., one week)
* Computes hourly co-presence
* Enhances visualisation:

  * Room highlighting when together
  * Night-time dimming (0–6)
  * Status labels (TOGETHER / SEPARATE)
  * Time annotation
* Generates continuous GIF

## Output

* `*_week_copresence.gif`

## Key contribution

* Captures **long-term behavioural patterns**
* Suitable for **poster / demo**

---

# E. `plot_copresence_heatmap.py`

## Objective

Provide **quantitative analysis of co-presence behaviour**.

## What it does

* Aligns both participants on a common timeline
* Defines co-presence condition
* Computes:

  * **Hourly co-presence proportion**
  * **Daily co-presence ratio**
* Visualises:

  * Heatmap (day × hour)
  * Line plot (daily trend)

## Output

* `*_copresence_heatmap.png`
* `*_copresence_ratio.png`

## Key contribution

* Moves from visualisation → **statistical analysis**
* Enables behavioural comparison across days

---

# F. Visualisation Objective

## Objective

To visualise two participants within a simplified graphical representation of their home environment, enabling intuitive understanding of their daily spatial behaviour and interaction patterns.

## Current Implementation

The project has progressed **step by step**, beginning with location-only visualisation and then extending toward richer behavioural context.

### Stage 1: Location-only visualisation

* A **floorplan-based representation** that maps each participant’s room-level location over time
* A **co-presence visualisation**, showing whether two participants are in the same room at each time step
* A **temporal animation (GIF)** that illustrates how both individuals move and interact across a day or multiple days

These earlier components allow:

* Clear observation of **movement patterns within the home**
* Identification of **shared vs separate activities**
* Exploration of **daily behavioural routines**

In the current codebase, the earlier two-person floorplan view is now preserved as a dedicated **location-only script**, so the original co-presence visualisation remains available as a separate milestone.

### Stage 2: Initial location + activity extension

The system has now been extended with an initial **location + activity prototype for AA001**.

## Current Progress

1. **Earlier two-person floorplan work preserved**

   * Keeps the original idea of showing **AA001 and AB001 together on the same floorplan**
   * Focuses on **location only**, without activity encoding
   * Retains co-presence status (`TOGETHER` / `SEPARATE`) as an interpretable interaction cue
   * Serves as the baseline visual milestone before adding activity information

2. **AA001 location + activity integration completed**

   * Uses `annotator.json` for room-level location
   * Uses `auto_activity_level_20231102_094535.json` for `activityLevel`
   * Aligns both data sources onto **10-minute visualisation frames**
   * Resolves frame labels by selecting the category with the **largest temporal overlap**
   * Encodes:
     * **Location** by marker position on the floorplan
     * **Activity level** by marker colour

3. **Output now includes**

   * A preserved two-person **location-only** floorplan GIF
   * A GIF showing AA001 moving through the home over time with activity colour encoding
   * A static first-frame image suitable for reports or poster drafts
   * On-frame annotations for:
     * time
     * location
     * activity level
     * activity legend

4. **Current limitation**

   * Activity-enhanced visualisation is currently implemented for **AA001 only**
   * The second participant is still represented in the preserved **location-only** version
   * A full two-person activity visualisation can be added later once matching activity data becomes available

---

# G
you can do a simple estimate of activity from step-count. You can do something  like steps in 10 mins, and colour code the person by steps in that 10 min interval (this is subtraction from cumulative step count)
# H
you want a visualization that combines location and activity. You have not yet finished this, but you need to show progress trying to do this.
# I
You also need to describe plan to improve analysis of location by an algorithm you can write directly using combination of raw data from beacons (RSSI) and bracelet sensors (accelerometer).
# J
It is better to use the acceration magnitude than to use step count
