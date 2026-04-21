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
# F
Describe the visualization task (objectives) ie: to visualize the two people in a simplified graphical representation of their home. Initially showing just their location, but in due course also showing their activity level / sleep too.
# G
you can do a simple estimate of activity from step-count. You can do something  like steps in 10 mins, and colour code the person by steps in that 10 min interval (this is subtraction from cumulative step count)
# H
you want a visualization that combines location and activity. You have not yet finished this, but you need to show progress trying to do this.
# I
You also need to describe plan to improve analysis of location by an algorithm you can write directly using combination of raw data from beacons (RSSI) and bracelet sensors (accelerometer).
# J
It is better to use the acceration magnitude than to use step count