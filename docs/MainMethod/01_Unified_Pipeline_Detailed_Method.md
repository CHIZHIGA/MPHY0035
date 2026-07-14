# Unified Movement-Supported RSSI Pipeline

## Step-by-Step Method with Explanations

## 1. Aim

The aim is to apply one location-analysis framework to all datasets rather than
developing a separate algorithm for each case. RSSI remains the primary source
of room identity. Movement, sleep context, pressure, and missing-data patterns
are used to decide whether an RSSI-derived room change is plausible and whether
it can be corrected.

The central principle is:

> RSSI proposes the room; movement and behavioural context determine how much
> temporal stability or additional constraint should be applied.

The same workflow is used across collections. Dataset-specific information,
such as time zone, beacon-room mapping, known Bedroom, or floor mapping, is
declared in the dataset manifest rather than hidden in separate algorithms.

## 2. Workflow Overview

```text
1. Standardise all sensor streams to five-minute windows
                         |
2. Use ACC, or step fallback, to derive movement and low motion
                         |
3. Identify probable away periods from supported RSSI gaps
                         |
4. Separate the remaining indoor periods into sleep and awake states
                         |
5. Use metadata or repeated sleep evidence to identify Bedroom
                         |
6. Correct unstable RSSI rooms within supported sleep episodes
                         |
7. Fill only strongly supported RSSI gaps during sleep
                         |
8. Apply movement-adaptive trailing RSSI to awake indoor periods
                         |
             final room + behaviour + occupancy + evidence
```

Optional branches are added only when the required data are available:

- pressure-based floor constraint;
- two-person co-presence comparison; and
- post-hoc reference-label evaluation.

## 3. Step 1 — Data Pre-processing and Five-Minute Standardisation

### What is done

All input timestamps are converted to UTC and aligned to fixed,
non-overlapping five-minute windows. Local time is also retained for
interpretation. This produces one common timeline for RSSI, ACC, step count,
pressure, labels, and multiple participants.

For every beacon (b) in window (t), mean RSSI is calculated as

\[
\bar r_{b,t}=\frac{1}{n_{b,t}}\sum_i r_{b,t,i}.
\]

The beacon with the highest mean RSSI becomes the raw room proposal:

\[
b_t^{raw}=\arg\max_b \bar r_{b,t}.
\]

The pipeline also stores the second-strongest RSSI, the gap between the two
strongest beacons, sample count, available beacon count, and coverage.

Different datasets have different sampling rates. Therefore, the expected
sample count is estimated separately for each beacon from its median non-zero
five-minute count. A beacon-window is accepted only when it contains at least
20% of that typical count. Empty or low-coverage windows remain missing.

If only cumulative step count is available, it is converted to positive
increments before aggregation:

\[
\Delta c_i=\max(0,c_i-c_{i-1}).
\]

Negative changes are treated as counter resets, not negative movement.

The step exports often record an unchanged cumulative counter approximately
every 30 minutes during inactivity. If two consecutive counter observations are
identical and no more than 35 minutes apart, the intervening five-minute windows
are reconstructed as confirmed zero-step windows. If the count increases, the
timing of those steps within the gap is unknown, so intervening windows remain
missing. Equal-count gaps longer than 35 minutes also remain missing to avoid
turning a stopped counter or non-wear period into a long false low-motion bout.

### Why this is needed

Five-minute aggregation reduces sample-level radio noise and provides a common
unit across datasets with different sampling intervals. Keeping missing windows
explicit is important because interpolation could create a false indoor room or
hide a real outing. The five-minute window is therefore the minimum inference
unit for every later stage.

### Output

Each window contains a raw strongest-RSSI room, RSSI quality fields, aligned
movement data, wearable availability, UTC time, and local time.

## 4. Step 2 — Movement and Low-Motion Detection

### What is done

ACC is the preferred movement source. The three axes are combined into an
orientation-reduced magnitude:

\[
m_i=\sqrt{a_{x,i}^2+a_{y,i}^2+a_{z,i}^2}.
\]

The five-minute movement feature is the standard deviation of magnitude,
normalised by the recording-level median magnitude:

\[
x_t^{ACC}=\frac{SD(m_i:i\in t)}{median(m_i)}.
\]

At least ten ACC samples are required in a window. If ACC is unavailable, the
five-minute step increment from Step 1 is used instead.

The movement feature is log-transformed because it is positive and strongly
right-skewed:

\[
z_t=\log(x_t^{ACC})
\]

or (z_t=\log(1+x_t^{step})) for steps.

One-dimensional K-means is tested with (K=2,3,4). A solution is accepted only
when every cluster contains at least 5% and at least 20 valid windows, and its
silhouette is at least 0.25. If several models are nearly equivalent, the
smaller K is selected.

Clusters are ordered from lowest to highest movement. Only the lowest cluster
is called low motion. Its upper boundary is the midpoint between the first two
cluster centres in log space. On the original ACC scale, this is their
geometric mean.

### Why ACC magnitude standard deviation is used

Raw magnitude includes an approximately constant gravity component. Its mean
can remain close to one during both quiet and active periods. Standard deviation
instead measures within-window fluctuation, which is more informative about
movement in these recordings. Combining the three axes also reduces dependence
on wrist orientation.

The threshold is estimated separately for each recording because sensor scale,
wear position, participant behaviour, and sampling differ. The algorithm is
unified because the same feature, clustering test, and boundary rule are used;
the numerical threshold does not need to be identical across datasets.

### Failure rule

If no K passes the size and silhouette checks, movement is marked unresolved.
The pipeline does not force a low-motion threshold.

## 5. Step 3 — Probable Away Detection

### What is done

A candidate away run requires:

- all environmental RSSI to be missing;
- at least one wearable stream to remain active; and
- the interval not to belong to selected main sleep.

The wearable-online condition distinguishes leaving the beacon environment from
a complete recording failure. Candidate gap durations are log-transformed and
split into two clusters. Away classification is accepted only when:

- at least six candidate gaps exist;
- each duration cluster contains at least two gaps;
- strong silhouette is at least 0.50; a borderline value from 0.45 to below
  0.50 is considered only with the remaining safeguards; and
- the long-duration centre is at least twice the short-duration centre for
  either tier.

The long-duration class is labelled `Probable away`. It is not called confirmed
absence. If the wearable is also missing, the state remains `Unknown`.

### Why sleep is checked before final away labelling

Conceptually, away periods are removed before indoor room analysis. In the
implementation, low-motion sleep candidates are identified before final away
labels are assigned. This prevents a sleep-related RSSI disappearance, such as
body occlusion of the wearable, from being classified as leaving home.

Only gaps outside selected main sleep are then eligible for the away-duration
model.

### Output

Away is stored as an occupancy state, not as a room. This keeps `Out`,
`Unknown`, and physical rooms conceptually separate.

## 6. Step 4 — Separating Indoor Sleep and Awake States

### What is done

Low-motion windows are connected across the full day. Up to 15 minutes of
intervening higher movement are allowed so that turning over or a short movement
does not split one long sleep period.

A low-motion candidate must:

- last at least 60 minutes; and
- contain at least 60% low-motion windows.

Candidate durations are log-transformed and clustered with (K=2) or (K=3).
The amount of evidence required depends on the fitted model. A two-cluster
solution requires at least four candidates, with at least two candidates in
each class. A three-cluster solution requires at least six candidates, again
with at least two in each class. This avoids applying a six-candidate rule to a
two-class problem that is already supported by a reproducible 2/2 split.

Silhouette values are interpreted in two tiers. A value of at least 0.50 is
`strong`. A value from 0.45 to below 0.50 is `borderline` and is accepted only
when every adjacent duration-cluster centre differs by at least 1.5 times.
Values below 0.45 are rejected. The longest-duration accepted cluster is
defined as main sleep, and the separation tier is retained in the audit.

No fixed night range, such as 18:00–10:00, is imposed. This allows the method to
identify irregular or daytime sleep from the participant's own duration
distribution.

### Why duration clustering is added

Low motion alone is not sleep. Quiet sitting, reading, or non-wear may also have
low ACC variability. Duration and continuity add behavioural context. Clustering
the candidate durations separates short quiet periods from the participant's
long recurring sleep-like episodes without selecting a boundary by eye.

### Failure rule

If the duration clusters are not sufficiently supported, the candidates remain
`sleep_unresolved`. The method does not automatically choose the longest episode
of each day.

## 7. Step 5 — Identifying Bedroom

### What is done

If metadata explicitly identify Bedroom beacons, that mapping is retained.
However, a known Bedroom does not force every sleep episode to be classified as
Bedroom; the episode still needs RSSI support.

If Bedroom is not known, a beacon can be inferred as Bedroom only when:

- it is the supported dominant beacon during main sleep on at least two
  different local nights; and
- its pooled dominance across those episodes is at least 60%.

### Why repeated nights are required

A single long episode may occur in another room or may be affected by temporary
RSSI failure. Requiring repeated dominance across nights provides stronger
evidence that the beacon represents the usual sleeping room.

The automatic Bedroom result, any manual mapping, and the source of that mapping
are retained separately for audit.

## 8. Step 6 — Correcting RSSI During Supported Sleep

### What is done

Within each selected main-sleep episode, the pipeline counts the observed
five-minute strongest beacons. If one beacon accounts for at least 60% of
observed windows, it becomes the episode-dominant room:

\[
p_e=\frac{\text{windows won by dominant beacon}}
          {\text{all observed RSSI windows in episode}}.
\]

When $p_e \ge 0.60$, all observed windows in that sleep episode are assigned to
the dominant room. If the dominant room is not Bedroom, it remains a supported
non-Bedroom sleep episode rather than being forced to Bedroom.

Step-derived sleep uses an additional conservative rule. Zero steps indicate
absence of walking, but cannot distinguish sleep from quiet sitting or a device
left stationary. A step-derived episode is therefore allowed to lock rooms or
fill RSSI gaps only when its supported dominant room is Bedroom. A step-derived
non-Bedroom episode may still be reported as a behavioural sleep candidate, but
its spatial result remains unchanged.

### Why episode-level correction is used

A 30- or 60-minute moving RSSI vote can still change when observations enter or
leave the window. During a long low-motion sleep episode, repeated room changes
without corresponding movement are more plausibly caused by beacon competition,
body occlusion, or radio propagation than by genuine movement between rooms.

The complete episode therefore becomes the temporal evidence unit. The 60%
dominance rule prevents this strong correction when the episode's room evidence
is genuinely mixed.

## 9. Step 7 — Filling Supported RSSI Gaps During Sleep

### What is done

Only a missing run inside a room-supported main-sleep episode can be filled.
For each gap, the preceding and following 30-minute contexts are examined.
Both sides must:

- contain at least one observed RSSI window; and
- support the episode-dominant beacon in at least two thirds of their observed
  windows.

If both conditions pass, the gap is filled with the episode-dominant room and
marked `sleep_gap_two_sided_room_support`.

### What remains missing

The gap is not filled when support is one-sided, conflicting, too sparse, or
when almost the whole sleep episode lacks RSSI. This preserves the distinction
between evidence-supported recovery and an assumed Bedroom label.

Awake RSSI gaps are never filled. A participant may genuinely move during an
awake gap, so historical room evidence is insufficient.

## 10. Step 8 — Movement-Adaptive RSSI During Awake Indoor Periods

### What is done

The awake branch extends the Fourth and Fifth Phase step-adaptive RSSI method,
but uses the movement states derived in Step 2. Lower movement uses a longer
RSSI history; higher movement uses a shorter history:

| Selected movement K | Windows from lowest to highest movement |
|---:|---|
| 2 | 30, 5 minutes |
| 3 | 30, 10, 5 minutes |
| 4 | 30, 15, 10, 5 minutes |

The window is trailing and updated every five minutes. Only current and past
RSSI are used. RSSI is averaged separately for each beacon over the eligible
history, and the strongest mean becomes the corrected awake room.

The history is not allowed to cross:

- a session or time discontinuity;
- an RSSI gap;
- sleep or away;
- a trusted pressure-floor change; or
- a movement state higher than the current state.

If the current awake window has no RSSI, the room remains missing regardless of
earlier observations.

### Why movement changes the window length

During low movement, a sudden strongest-beacon change is less likely to reflect
real room movement, so a longer history suppresses isolated RSSI fluctuations.
During high movement, genuine room changes are plausible, so the method uses
only the current five-minute evidence and avoids excessive smoothing.

The trailing design avoids using future data and is therefore compatible with
online awake-room inference. Sleep correction remains retrospective because the
complete episode duration must first be observed.

## 11. Optional Extra Work

### 11.1 Pressure-based floor constraint

Pressure is considered only when both wearable pressure and environmental
beacon pressure exist. Relative beacon-pressure offsets are tested for two or
three stable groups, but the algorithm is also allowed to retain the K=1 null
model: no resolved floor structure. Automatic grouping requires at least 100
overlap windows, at least two beacons per group, silhouette at least 0.75, at
least 0.30 hPa between adjacent group centres, and separation greater than
three times within-group variability.

The 0.30 hPa criterion deliberately distinguishes statistical pressure groups
from floor-scale evidence. Beacons on the same floor can be mounted at
different heights and can have stable sensor zero-point offsets. Those effects
may create highly repeatable clusters, but a repeatable cluster is not
automatically a floor. If the separation or silhouette criterion fails, the
K=1 null model is selected, the candidate K=2/3 diagnostics are retained in the
audit, and pressure does not alter RSSI.

Wearable pressure is then calibrated against environmental pressure. Only a
high-confidence floor estimate, at least 0.75, can restrict RSSI to beacons in
the inferred floor group. An inferred floor transition also needs movement
support. Low confidence or unsupported floor changes leave RSSI unchanged.

This makes pressure a conservative constraint on candidate beacons, not an
independent room classifier. A manual floor mapping is allowed only when it is
declared and recorded as an override.

### 11.2 Two-person collections

Each participant is processed independently on the same five-minute UTC grid.
The two final timelines are then compared to calculate raw and corrected
same-room time, added and removed co-presence windows, and separate results for
awake, sleep, away, and unknown periods.

One participant's location is never used to correct the other participant. The
dual-person branch evaluates how the individual corrections alter inferred
co-presence.

### 11.3 Reference-labelled collections

Reference labels are loaded only after the complete prediction timeline and all
parameters have been produced. This prevents label leakage into movement,
sleep, away, Bedroom, pressure, or room correction.

Runtime separation does not by itself create an independent validation set.
The bounded step-plateau and step-derived Bedroom restriction were refined
after inspecting the labelled DH collections. Those collections must therefore
be described as development-set agreement for this revision. Unbiased
validation requires freezing the rule and applying it to a separate collection.

The evaluation reports:

- prediction coverage;
- conditional accuracy on covered windows;
- balanced accuracy;
- macro-F1;
- end-to-end accuracy, with missing and `Unknown` counted as incorrect; and
- raw and corrected confusion matrices.

The result is described as agreement with reference annotations rather than
ground-truth accuracy. When `Probable away` is compared with reference `Out`,
that coverage gain is reported separately from RSSI room smoothing.

## 12. Final Output and Evidence Provenance

The final five-minute timeline keeps three concepts separate:

- `occupancy_state`: indoor observed, indoor inferred during sleep, probable
  away, or unknown;
- `behaviour_state`: awake, main sleep, unresolved sleep, away, or unresolved
  movement; and
- `corrected_room`: the final room when spatial evidence exists.

Each row also retains the raw and corrected beacon, movement source and state,
low-motion threshold, sleep episode, pressure status, adaptive window length,
RSSI coverage, correction reason, and evidence source.

This provenance is essential because the same final room may have been:

- directly observed from raw strongest RSSI;
- selected after a pressure-floor constraint;
- stabilised by a sleep episode;
- filled from two-sided sleep context; or
- selected by the awake movement-adaptive window.

Every collection receives its own result directory containing the five-minute
timeline, clustering audits, sleep and away summaries, raw-versus-corrected
timeline, and optional pressure, two-person, or reference-label results. A
cross-dataset summary then compares the same metrics across collections.

## 13. Main Safeguards

The following rules prevent the pipeline from increasing apparent coverage by
making unsupported assumptions:

1. Low-motion threshold derivation is consistent, but the numerical threshold
   is fitted separately for each recording.
2. Failed movement, sleep, away, or pressure models remain unresolved or
   inactive.
3. Main sleep is not forced from clock time or the longest daily period.
4. A known Bedroom does not override contradictory episode RSSI.
5. Sleep room locking requires at least 60% observed dominance.
6. Step-derived sleep can change spatial output only when the supported
   dominant room is Bedroom.
7. Sleep-gap filling requires two-sided evidence.
8. Awake missing RSSI is never filled.
9. Adaptive windows cannot cross gaps, states, sessions, or trusted floors.
10. Pressure has no effect when its audit conditions fail.
11. Labels and other participants are never used during prediction.
12. Dataset-specific overrides must be declared and retain their provenance.
13. `Away`, `Sleep`, and `Unknown` are never disguised as room names.

## 14. Limitations

Low ACC variability is not specific to sleep, and the movement clusters do not
have supervised activity labels. Five-minute windows cannot resolve very short
movements or exact transition times. Episode-level sleep correction is an
offline method. In unlabelled collections, fewer implausible transitions and
greater sleep-room stability are plausibility evidence, not proof of true room
location. Pressure groups may also reflect sensor calibration differences and
therefore require careful audit.

## 15. Implementation

The implementation is in [`src/EighthPhase`](../../src/EighthPhase/README.md).
The unified entry point is:

```bash
MPLCONFIGDIR=/tmp/matplotlib PYTHONPATH=src \
  /home/czg/miniforge3/envs/0249_env/bin/python \
  src/EighthPhase/run_pipeline.py --dataset all
```

The common parameters are exported to
[`pipeline_parameters.json`](../../Results/EighthPhase/pipeline_parameters.json).
