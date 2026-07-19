# Unified Pipeline: Quantified Results Across All Datasets

## 1. Scope and Reading Guide

This document reports the Eighth Phase unified pipeline without selecting only
successful examples. It covers all 13 processed sessions from ten collections,
including unresolved sleep, unchanged outputs, increased transition counts, and
optional branches that failed their evidence checks.

The source tables are:

- [`cross_dataset_summary.csv`](../../Results/EighthPhase/cross_dataset_summary.csv)
- [`dataset_capability_audit.csv`](../../Results/EighthPhase/dataset_capability_audit.csv)
- [`excluded_dataset_audit.csv`](../../Results/EighthPhase/excluded_dataset_audit.csv)
- [`pipeline_failures.csv`](../../Results/EighthPhase/pipeline_failures.csv)
- [`pipeline_parameters.json`](../../Results/EighthPhase/pipeline_parameters.json)

### Interpretation rules

- **Raw coverage** is the proportion of pipeline windows with at least one
  quality-controlled RSSI beacon.
- **Corrected coverage** is the proportion with a final room beacon. It can
  exceed raw coverage only through supported sleep-gap recovery.
- **Corrected windows** count any final beacon different from raw strongest
  RSSI, including pressure constraints, sleep locking, gap filling, and awake
  adaptive smoothing.
- **Transitions** are counted only between consecutive, non-missing five-minute
  room windows. A smaller number is useful evidence of stability but is not an
  accuracy measure.
- **Main sleep** means the duration-clustering checks were passed. A plausible
  long low-motion bout can still remain `sleep_unresolved` under the global
  safeguards.
- **Probable away** is a model-derived occupancy state, not confirmed absence.
- Label results are **agreement with reference annotations**, not ground-truth
  accuracy.

## 2. Overall Quantitative Summary

| Quantity | Result |
|---|---:|
| Processed collections | 10 |
| Processed participant-sessions | 13 |
| Five-minute windows | 25,513 |
| Approximate recorded time | 2,126.1 h |
| Pipeline failures | 0 |
| ACC sessions | 9 |
| Step-fallback sessions | 4 |
| Sessions with resolved main sleep | 9 |
| Selected main-sleep episodes | 61 |
| Sessions with resolved away clustering | 13 |
| Probable-away runs | 158 |
| Windows changed from raw strongest RSSI | 579 |
| Two-sided sleep-gap windows filled | 57 = 285 min |
| Weighted raw room coverage | 76.48% |
| Weighted corrected room coverage | 76.70% |
| Raw room transitions | 3,353 |
| Corrected room transitions | 2,961 |
| Overall transition change | −392 (−11.7%) |

The small overall coverage increase is intentional: the awake branch never
fills missing RSSI. Fifty-one of the 57 newly covered sleep windows are from
EF-002 and six are from KM PanH Nov22.

## 3. Session-Level Results Table

| Collection / session | Movement | K | Threshold | Main sleep | Probable away | Raw→corrected coverage | Changed windows | Sleep gap fill | Raw→corrected transitions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Home_A002 / AA002 | ACC | 2 | 0.02561 | unresolved | 13 runs, 41.58 h | 80.4%→80.4% | 0 | 0 | 157→157 |
| Home_A002 / AB002 | Step | 2 | 9.268 steps | unresolved | 16 runs, 23.83 h | 89.3%→89.3% | 1 | 0 | 194→194 |
| Home_X001 / Left wrist | ACC | 2 | 0.02058 | 7 episodes, 39.42 h | 8 runs, 60.42 h | 62.0%→62.0% | 85 | 0 | 346→284 |
| Home_X001 / Right wrist | ACC | 2 | 0.01409 | 10 episodes, 79.75 h | 10 runs, 23.08 h | 86.6%→86.6% | 26 | 0 | 495→470 |
| NewData80h / 559662 | ACC | 2 | 0.000936 | 3 episodes, 20.67 h | 3 runs, 7.67 h | 88.2%→88.2% | 7 | 0 | 117→113 |
| EF-001 | ACC | 2 | 0.01841 | 11 episodes, 100.33 h | 6 runs, 63.08 h | 68.4%→68.4% | 187 | 0 | 693→556 |
| EF-002 | ACC | 2 | 0.02126 | 12 episodes, 82.00 h | 23 runs, 33.08 h | 81.5%→82.9% | 67 | 51 | 543→513 |
| DH Paris | Step | 2 | 10.280 steps | 5 episodes, 22.08 h | 34 runs, 46.25 h | 62.4%→62.4% | 45 | 0 | 267→253 |
| DH PanoH | Step | 2 | 7.761 steps | 3 episodes, 15.92 h | 3 runs, 23.25 h | 69.6%→69.6% | 17 | 0 | 59→59 |
| DH Strad | Step | 2 | 8.414 steps | unresolved | 27 runs, 22.58 h | 69.9%→69.9% | 9 | 0 | 136→122 |
| KM Mal | ACC | 3 | 0.01542 | 4 episodes, 37.50 h | 4 runs, 20.17 h (borderline) | 69.6%→69.6% | 54 | 0 | 135→78 |
| KM PanH Nov22 | ACC | 2 | 0.02722 | 6 episodes, 53.33 h | 8 runs, 22.25 h | 72.0%→72.5% | 74 | 6 | 156→111 |
| KM PanH Nov28 | ACC | 3 | 0.01605 | unresolved | 3 runs, 7.17 h | 84.7%→84.7% | 7 | 0 | 55→51 |

The ACC thresholds are recording-specific outputs of the same log-clustering
rule. Their numerical variation is expected and should not be interpreted as
different algorithms.

## 4. Home_A002: Two Participants With Conservative Step Reconstruction

### 4.1 Quantification

| Participant | Windows | Movement | Low-motion result | Sleep candidates | Main sleep | Corrected windows | Transitions |
|---|---:|---|---|---:|---|---:|---:|
| AA002 | 2,689 | ACC, K=2 | resolved | 12 | unresolved duration clustering | 0 | 157→157 |
| AB002 | 2,955 | Step, K=2 | resolved | 16 | unresolved | 1 | 194→194 |

AA002 contains long low-motion candidates, but the duration model did not pass
the global cluster checks. For AB002, bounded equal-count step reconstruction
added 1,136 confirmed zero-step windows and produced 16 candidates. One
candidate lasted 4,865 minutes, consistent with a stopped counter, non-wear, or
device left stationary rather than one sleep episode. Because this extreme bout
formed an unsupported singleton duration class, sleep remained unresolved. Only
one awake room window changed.

The one awake change added one co-presence window:

| Stratum | Overlap windows | Raw same-room | Corrected same-room | Raw hours | Corrected hours |
|---|---:|---:|---:|---:|---:|
| All | 2,688 | 835 | 836 | 69.58 | 69.67 |
| Awake | 2,075 | 835 | 836 | 69.58 | 69.67 |
| Away | 560 | 0 | 0 | 0 | 0 |
| Unknown | 53 | 0 | 0 | 0 | 0 |

Full metrics: [`copresence_AA002_AB002_metrics.csv`](../../Results/EighthPhase/Home_A002/copresence_AA002_AB002_metrics.csv).

### 4.2 Figures

![Home_A002 AA002 raw and corrected timeline](../../Results/EighthPhase/Home_A002/AA002/AA002_2023/raw_vs_corrected_timeline.png)

*AA002 take-home message: the long low-motion regions are visible, but the
conservative duration rules leave sleep unresolved and the room output
unchanged.*

![Home_A002 AA002 movement and sleep clustering](../../Results/EighthPhase/Home_A002/AA002/AA002_2023/movement_sleep_clustering.png)

*AA002 diagnostic: ACC movement clustering resolves, whereas sleep-duration
clustering is not accepted.*

![Home_A002 AB002 raw and corrected timeline](../../Results/EighthPhase/Home_A002/AB002/AB002_2023/raw_vs_corrected_timeline.png)

*AB002 take-home message: reconstructed zero-step plateaus reveal low-motion
candidates, but the abnormal multi-day plateau is rejected and no sleep-room
correction is forced.*

![Home_A002 AB002 movement and sleep clustering](../../Results/EighthPhase/Home_A002/AB002/AB002_2023/movement_sleep_clustering.png)

*AB002 diagnostic: this session demonstrates both the benefit of reconstructing
bounded zero-step plateaus and the need for counter-stuck protection.*

## 5. Home_X001: Two Participants and a Blind Pressure Null Result

### 5.1 Quantification

| Participant | Main-sleep episodes | Room-supported episodes | Automatic pressure result | Changed windows by source | Transitions |
|---|---:|---:|---:|---|---:|
| Left wrist | 7 | 4 | K=1; pressure inactive | 73 sleep + 12 awake | 346→284 |
| Right wrist | 10 | 10 | K=1; pressure inactive | 19 sleep + 7 awake | 495→470 |

The blind audit still finds K=2 candidate groups, but now distinguishes
clusterability from floor-scale evidence. Left and right candidate separations
are only 0.231 and 0.233 hPa, with silhouettes 0.720 and 0.685. Both fail the
revised requirements of at least 0.30 hPa and silhouette 0.75, so K=1 is
selected without using the known single-floor metadata. Pressure therefore
changes no room window. This is consistent with the interpretation that
same-floor mounting height or stable sensor offsets produced the smaller
groups.

With the false pressure constraint removed, both participants now show fewer
transitions. This remains a stability result rather than an accuracy claim
because X001 has no independent room reference labels.

### 5.2 Co-presence

| Stratum | Overlap windows | Raw same-room | Corrected same-room | Added | Removed | Raw→corrected hours |
|---|---:|---:|---:|---:|---:|---:|
| All | 2,052 | 399 | 392 | 41 | 48 | 33.25→32.67 |
| Awake | 586 | 162 | 163 | 3 | 2 | 13.50→13.58 |
| Sleep | 628 | 237 | 229 | 38 | 46 | 19.75→19.08 |
| Away | 738 | 0 | 0 | 0 | 0 | 0→0 |
| Unknown | 100 | 0 | 0 | 0 | 0 | 0→0 |

The method is not biased toward creating co-presence: it added 41 and removed
48 same-room windows. Full metrics:
[`copresence_LEFT_WRIST_RIGHT_WRIST_metrics.csv`](../../Results/EighthPhase/Home_X001/copresence_LEFT_WRIST_RIGHT_WRIST_metrics.csv).

### 5.3 Figures

![Home_X001 left wrist raw and corrected timeline](../../Results/EighthPhase/Home_X001/LEFT_WRIST/LEFT_WRIST_2026/raw_vs_corrected_timeline.png)

*Left-wrist take-home message: the blind pressure gate selects K=1, and the
remaining sleep and awake corrections reduce transitions from 346 to 284.*

![Home_X001 left wrist movement and sleep clustering](../../Results/EighthPhase/Home_X001/LEFT_WRIST/LEFT_WRIST_2026/movement_sleep_clustering.png)

*Left-wrist diagnostic: seven main-sleep episodes are selected, but only four
have at least 60% room dominance.*

![Home_X001 right wrist raw and corrected timeline](../../Results/EighthPhase/Home_X001/RIGHT_WRIST/RIGHT_WRIST_2026/raw_vs_corrected_timeline.png)

*Right-wrist take-home message: all ten main-sleep episodes have room support;
after the false pressure grouping is rejected, transitions reduce from 495 to
470.*

![Home_X001 right wrist movement and sleep clustering](../../Results/EighthPhase/Home_X001/RIGHT_WRIST/RIGHT_WRIST_2026/movement_sleep_clustering.png)

*Right-wrist diagnostic: the session has a well-populated long-duration sleep
class, while its pressure candidate remains an audited but rejected K=2 model.*

## 6. NewData80h: K=2 Sleep Resolution and Automatic Floor Grouping

### 6.1 Quantification

| Metric | Result |
|---|---:|
| Windows | 961 = 80.08 h |
| Movement | ACC, K=2, threshold 0.000936 |
| Valid sleep candidates | 5 |
| Main sleep | 3 episodes, 20.67 h; strong K=2 separation |
| Probable away | 3 runs, 7.67 h |
| Pressure grouping | automatic K=2; silhouette 0.865; separation 0.381 hPa |
| Pressure-trusted windows | 472 |
| Windows changed | 5 pressure + 2 sleep = 7 |
| Transitions | 117→113 |

The five low-motion candidates split into two short bouts and three longer
bouts. K=2 has silhouette 0.762, class sizes 2/3, and centres of approximately
148 and 411 minutes, so it passes the K-specific evidence rule as a strong
solution. The three longer bouts are selected as main sleep; all three are
Bedroom-supported. K=3 remains rejected because it contains a singleton class.

Without a floor override, the blind pressure model groups 1933 with CA59 and
3E05 with D7FD, matching the earlier independently documented two-floor
mapping up to arbitrary cluster labels. Its 0.381 hPa centre separation and
0.865 silhouette pass the revised gate. Although 472 windows pass pressure
confidence, only five raw strongest-beacon decisions change, demonstrating
that pressure acts as a constraint rather than a general replacement for RSSI.

### 6.2 Figures

![NewData80h raw and corrected timeline](../../Results/EighthPhase/NewData80h/559662/559662_80h/raw_vs_corrected_timeline.png)

*Take-home message: the pressure constraint changes five windows and supported
sleep changes two more, reducing four transitions in total.*

![NewData80h movement and sleep clustering](../../Results/EighthPhase/NewData80h/559662/559662_80h/movement_sleep_clustering.png)

*Diagnostic: five candidates are sufficient for a reproducible K=2 split with
two short and three long episodes; no singleton class is accepted.*

## 7. EF-001: Correcting Implausible Switching During Low Motion

### 7.1 Quantification

| Metric | Result |
|---|---:|
| Windows | 3,593 |
| Movement | ACC, K=2, threshold 0.01841 |
| Sleep candidates | 18 |
| Main-sleep episodes | 11, totalling 100.33 h |
| Room-supported main-sleep episodes | 6 of 11 |
| Changed windows | 187 |
| Sleep episode-dominant corrections | 155 |
| Awake adaptive corrections | 32 |
| Sleep gaps filled | 0 |
| Transitions | 693→556, −137 (−19.8%) |

The dominant-room rule was not applied indiscriminately: five of the eleven
main-sleep episodes failed the 60% room-support threshold. The 137-transition
reduction is therefore concentrated in supported episodes and a small number of
awake adaptive corrections. Coverage is unchanged because no missing sleep gap
met the two-sided rule.

### 7.2 Figures

![EF-001 raw and corrected timeline](../../Results/EighthPhase/EF-001/EF-001/EF-001_2026/raw_vs_corrected_timeline.png)

*Take-home message: supported long low-motion episodes form longer stable room
segments, reducing consecutive observed room changes by 19.8% while unsupported
episodes and gaps are retained.*

![EF-001 movement and sleep clustering](../../Results/EighthPhase/EF-001/EF-001/EF-001_2026/movement_sleep_clustering.png)

*Diagnostic: the unified model selects K=2 movement states and a K=3 duration
model with centres near 86, 236, and 543 minutes.*

## 8. EF-002: Evidence-Supported Sleep-Gap Recovery

### 8.1 Quantification

| Metric | Result |
|---|---:|
| Windows | 3,552 |
| Movement | ACC, K=2, threshold 0.02126 |
| Sleep candidates | 24 |
| Main-sleep episodes | 12, totalling 82.00 h |
| Room-supported main-sleep episodes | 11 of 12 |
| Changed windows | 67 |
| Two-sided sleep-gap fill | 51 windows = 255 min |
| Sleep episode-dominant corrections | 12 |
| Awake adaptive corrections | 4 |
| Room coverage | 81.5%→82.9%, +1.44 percentage points |
| Transitions | 543→513, −30 (−5.5%) |
| Pressure branch | disabled: no stable multi-floor grouping |

EF-002 is the only session with substantial sleep-gap recovery. The rule filled
51 windows supported by matching 30-minute contexts. It did not fill the nearly
710-minute episode with almost no RSSI: only two windows were observed and the
dominant share was 50%, below the 60% episode support requirement.

### 8.2 Figures

![EF-002 raw and corrected timeline](../../Results/EighthPhase/EF-002/EF-002/EF-002_2026/raw_vs_corrected_timeline.png)

*Take-home message: short internal RSSI losses with two-sided room support are
recovered, whereas the unsupported near-whole-night absence remains missing.*

![EF-002 movement and sleep clustering](../../Results/EighthPhase/EF-002/EF-002/EF-002_2026/movement_sleep_clustering.png)

*Diagnostic: a two-class duration solution separates approximately 90-minute
short bouts from approximately 390-minute main-sleep bouts.*

## 9. Labelled Collections: Reference-Annotation Agreement

### 9.1 Metrics across all four labelled datasets

| Dataset | Coverage raw→corrected | Conditional accuracy raw→corrected | Balanced accuracy raw→corrected | Macro-F1 raw→corrected | End-to-end agreement raw→corrected |
|---|---:|---:|---:|---:|---:|
| DH Paris | 62.8%→96.6% | 44.7%→64.1% | 48.4%→67.0% | 34.2%→47.9% | 28.1%→61.9% |
| DH PanoH | 62.7%→99.0% | 89.7%→90.5% | 54.6%→66.0% | 51.4%→64.2% | 56.3%→89.6% |
| DH Strad | 69.9%→93.4% | 82.9%→87.8% | 49.8%→69.2% | 45.7%→65.9% | 57.9%→82.0% |
| KM Mal | 66.3%→90.9% | 86.2%→94.4% | 60.2%→81.2% | 49.0%→77.2% | 57.1%→85.8% |

The first three collections use step movement. Reconstructing bounded
equal-count counter plateaus resolved sleep in DH Paris and DH PanoH; DH Strad
retained a singleton duration class. Their large corrected reference coverage
gains still primarily arise because resolved `Probable away` intervals are
compared with reference `Out`. Five-minute room coverage remains unchanged, and
54 awake room windows change across the three datasets.

DH Paris also demonstrates why step-derived spatial correction is restricted.
Four sleep episodes had a supported non-Bedroom RSSI winner, mainly Bathroom,
while the reference annotation was Bedroom. Locking those episodes to Bathroom
reduced sleep agreement. The final rule therefore retains the behavioural sleep
state but allows step-derived room locking only when the supported dominant room
is Bedroom.

Because this rule was refined after inspecting the DH annotations, the updated
DH metrics are development-set agreement rather than independent validation.
The runtime still loads labels only after prediction, but an unbiased test now
requires freezing the revised rule and applying it to a separate labelled
collection.

KM Mal has ACC and resolved sleep. Its seven away candidates give silhouette
0.489 and centres of 144 and 298 minutes, a ratio of 2.07. This is accepted and
explicitly audited as borderline rather than strong. Consequently, its
reference coverage now includes four `Probable away` intervals and should not
be interpreted as a room-smoothing result alone. Because the narrow borderline
range was added while reviewing this separation diagnostic, the resulting KM
agreement is a sensitivity/development result, not an independent validation
of the 0.45 boundary.

### 9.2 DH Paris

| Metric | Result |
|---|---:|
| Windows | 1,689 |
| Movement | Step, K=2; 392 zero-step windows reconstructed |
| Main sleep | 5 episodes, 22.08 h |
| Probable away | 34 runs, 46.25 h |
| Awake room corrections | 45 |
| Sleep room corrections | 0; non-Bedroom step episodes retained unchanged |
| Transitions | 267→253 |

![DH Paris raw and corrected timeline](../../Results/EighthPhase/Labelled_DH_Paris/DH/DH_Paris_2024/raw_vs_corrected_timeline.png)

*Take-home message: plateau reconstruction reveals recurring night-time
zero-step episodes, while the conservative Bedroom rule prevents a supported
but reference-inconsistent Bathroom lock.*

![DH Paris movement and sleep clustering](../../Results/EighthPhase/Labelled_DH_Paris/DH/DH_Paris_2024/movement_sleep_clustering.png)

*Diagnostic: step movement resolves into two ordered states and 13 candidates;
the longer duration class contains five main-sleep episodes.*

![DH Paris raw and corrected reference confusion matrices](../../Results/EighthPhase/Labelled_DH_Paris/DH/DH_Paris_2024/reference_confusion_matrix.png)

*Agreement result: end-to-end reference agreement rises from 28.1% to 61.9%,
with coverage and class balance reported so that the effect of `Out` is visible.*

### 9.3 DH PanoH

| Metric | Result |
|---|---:|
| Windows | 1,012 |
| Movement | Step, K=2; 223 zero-step windows reconstructed |
| Main sleep | 3 episodes, 15.92 h; strong K=2 separation |
| Probable away | 3 runs, 23.25 h |
| Sleep room corrections | 17 |
| Transitions | 59→59 |

![DH PanoH raw and corrected timeline](../../Results/EighthPhase/Labelled_DH_PanoH/DH/DH_PanoH_2023/raw_vs_corrected_timeline.png)

*Take-home message: three Bedroom-supported sleep episodes now contribute 17
room corrections; probable away remains the main source of coverage gain.*

![DH PanoH movement and sleep clustering](../../Results/EighthPhase/Labelled_DH_PanoH/DH/DH_PanoH_2023/movement_sleep_clustering.png)

*Diagnostic: five candidates form a strong two-class 2/3 split, with centres of
approximately 85 and 314 minutes and silhouette 0.640.*

![DH PanoH raw and corrected reference confusion matrices](../../Results/EighthPhase/Labelled_DH_PanoH/DH/DH_PanoH_2023/reference_confusion_matrix.png)

*Agreement result: conditional accuracy reaches 90.5% and end-to-end agreement
89.6%; the distinction between these metrics prevents missingness from being
hidden.*

### 9.4 DH Strad

| Metric | Result |
|---|---:|
| Windows | 1,155 |
| Movement | Step, K=2; 214 zero-step windows reconstructed |
| Main sleep | unresolved |
| Probable away | 27 runs, 22.58 h |
| Awake room corrections | 9 |
| Transitions | 136→122 |

![DH Strad raw and corrected timeline](../../Results/EighthPhase/Labelled_DH_Strad/DH/DH_Strad_2023/raw_vs_corrected_timeline.png)

*Take-home message: nine awake adaptive changes reduce 14 observed room
transitions, while long gaps are represented separately as probable away.*

![DH Strad movement and sleep clustering](../../Results/EighthPhase/Labelled_DH_Strad/DH/DH_Strad_2023/movement_sleep_clustering.png)

*Diagnostic: four candidates are present, but K=2 produces a 1/3 split. The
singleton class is rejected even though the overall silhouette is high.*

![DH Strad raw and corrected reference confusion matrices](../../Results/EighthPhase/Labelled_DH_Strad/DH/DH_Strad_2023/reference_confusion_matrix.png)

*Agreement result: macro-F1 rises from 45.7% to 65.9% and end-to-end agreement
from 57.9% to 82.0%.*

### 9.5 KM Mal

| Metric | Result |
|---|---:|
| Windows | 1,091 |
| Movement | ACC, K=3 |
| Main sleep | 4 episodes, 37.50 h; all room-supported |
| Away | 4 runs, 20.17 h; borderline silhouette 0.489 |
| Changed windows | 54 = 39 sleep + 15 awake |
| Transitions | 135→78, −42.2% |

![KM Mal raw and corrected timeline](../../Results/EighthPhase/Labelled_KM_Mal/KM/KM_Mal_2023/raw_vs_corrected_timeline.png)

*Take-home message: episode and awake room corrections reduce transitions by
42.2%; four separately inferred probable-away periods increase occupancy-state
coverage but do not fill room RSSI.*

![KM Mal movement and sleep clustering](../../Results/EighthPhase/Labelled_KM_Mal/KM/KM_Mal_2023/movement_sleep_clustering.png)

*Diagnostic: a K=3 ACC model and K=2 duration model identify four supported
main-sleep episodes.*

![KM Mal raw and corrected reference confusion matrices](../../Results/EighthPhase/Labelled_KM_Mal/KM/KM_Mal_2023/reference_confusion_matrix.png)

*Agreement result: conditional accuracy increases from 86.2% to 94.4% and
macro-F1 from 49.0% to 77.2%. The coverage increase to 90.9% is primarily the
new borderline probable-away classification.*

## 10. KM NOV23 PanH: Two Sessions of Different Length

### 10.1 Quantification

| Session | Windows | Sleep candidates | Main sleep | Room-supported | Corrected sources | Coverage | Transitions |
|---|---:|---:|---:|---:|---|---:|---:|
| Nov22 | 1,373 | 10 | 6 episodes, 53.33 h | 5 | 65 sleep + 6 gap + 3 awake | 72.0%→72.5% | 156→111 |
| Nov28 | 595 | 3 | unresolved | — | 7 awake | 84.7%→84.7% | 55→51 |

The longer Nov22 session contains enough candidates to resolve main sleep and
shows a 28.8% transition reduction. Six supported gap windows add 30 minutes of
room coverage. The shorter Nov28 session has only three candidates and remains
unresolved under the same rule; its seven changes come only from awake adaptive
RSSI.

### 10.2 Figures

![KM PanH Nov22 raw and corrected timeline](../../Results/EighthPhase/KM_NOV23_PanH/KM/KM_PanH_Nov22/raw_vs_corrected_timeline.png)

*Nov22 take-home message: supported sleep episodes, one short context-supported
gap recovery, and three awake changes reduce transitions by 28.8%.*

![KM PanH Nov22 movement and sleep clustering](../../Results/EighthPhase/KM_NOV23_PanH/KM/KM_PanH_Nov22/movement_sleep_clustering.png)

*Nov22 diagnostic: six episodes are selected from a well-populated duration
distribution.*

![KM PanH Nov28 raw and corrected timeline](../../Results/EighthPhase/KM_NOV23_PanH/KM/KM_PanH_Nov28/raw_vs_corrected_timeline.png)

*Nov28 take-home message: the shorter recording receives only seven causal awake
corrections; sleep is not forced.*

![KM PanH Nov28 movement and sleep clustering](../../Results/EighthPhase/KM_NOV23_PanH/KM/KM_PanH_Nov28/movement_sleep_clustering.png)

*Nov28 diagnostic: three candidates can only form a 1/2 K=2 split, so the
singleton class is rejected.*

## 11. Cross-Dataset Findings

### 11.1 What generalised

1. A fixed five-minute schema and the same audited clustering logic ran on all
   13 parseable sessions without failure.
2. ACC was available in nine sessions; all four remaining sessions used the
   step fallback without changing the downstream schema.
3. Main sleep resolved in nine sessions and remained unresolved in four. This
   demonstrates consistent failure behaviour rather than guaranteed output.
4. The largest transition reductions occurred in KM Mal (−42.2%), KM PanH
   Nov22 (−28.8%), and EF-001 (−19.8%). These are sessions with resolved sleep
   and substantial episode correction.
5. Supported sleep-gap recovery was rare and concentrated: 51 windows in
   EF-002 and six in KM PanH Nov22. Awake RSSI missingness was never filled.
6. The revised blind pressure gate selects K=1 for both Home_X001 sessions but
   automatically recovers the documented two-floor beacon grouping in
   NewData80h. EF-002 had both pressure streams but failed stable grouping, so
   pressure had no effect.
7. Reference agreement improved in all four labelled collections, but the
   mechanism differed: probable-away/`Out` mapping dominated the three DH
   datasets. KM Mal also gained coverage from a conservatively accepted
   borderline away model, so its room and occupancy effects are reported
   separately.

### 11.2 What did not generalise cleanly

1. A single numerical ACC threshold did not generalise; the common log-space
   derivation produced session thresholds from 0.000936 to 0.02722.
2. Short recordings can support K=2 when at least four candidates form two
   repeated classes, as in NewData80h. KM PanH Nov28 remains unresolved because
   three candidates necessarily produce a singleton class.
3. Transition reduction is not guaranteed: AB002 and DH PanoH remain unchanged,
   even though the same inference schema is applied.
4. Bounded equal-count step reconstruction improved movement coverage and
   resolved five main-sleep episodes in DH Paris and three in DH PanoH. DH
   Strad's four candidates form a 1/3 split, while AB002 retains an abnormal
   multi-day plateau; both correctly remain unresolved. Step absence therefore
   contains useful sleep context but is not equivalent to ACC low motion.
5. Unlabelled stability improvements remain plausibility evidence rather than
   verified room accuracy.

## 12. Excluded Data and Failure Audit

| Collection | Status | Reason |
|---|---|---|
| Home_A001 | Excluded | Annotation-only; no parseable raw wearable and beacon streams |
| KM DEC PANAPT | Excluded | Only encrypted/unexported `SAMPLES.DAT`; no parseable sensor CSV |

The exclusions are data-availability decisions, not algorithmic failures. The
processed-run failure file contains only its header, confirming zero failed
sessions.

## 13. Report-Ready Overall Conclusion

Across 25,513 five-minute windows from 13 sessions, the unified framework
changed 579 raw strongest-beacon decisions and reduced consecutive observed room
transitions from 3,353 to 2,961 (11.7%). It identified 61 main-sleep episodes in
nine sessions and recovered 57 five-minute sleep gaps only when two-sided room
context supported the episode-dominant room. The remaining awake RSSI gaps were
preserved. All four labelled datasets improved in end-to-end reference
agreement, although the large gains in the DH datasets were mainly associated
with probable-away intervals matching reference `Out`. The results therefore
support a common evidence-based framework, while also showing why missingness,
unresolved states, correction provenance, and dataset capability must be
reported alongside room stability.
