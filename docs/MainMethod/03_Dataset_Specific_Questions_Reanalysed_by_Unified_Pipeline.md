# Dataset-Specific Questions Re-analysed by the Unified Pipeline

## 1. Purpose

The earlier project phases did not all ask the same immediate question. One
dataset was used to test whether movement identifies reliable RSSI periods,
another to describe two-person co-presence, another to test pressure-derived
floor changes, and the EF datasets to address two different night-time RSSI
failure modes. The Eighth Phase deliberately applies the same pipeline to all
parseable datasets.

This document therefore asks a different question from the general quantified
results:

> When the same movement-supported RSSI pipeline is applied to every dataset,
> how well can it answer the dataset-specific question that originally
> motivated each project phase?

For each collection, the comparison separates:

1. the original question raised in the work log or supervisor feedback;
2. the earlier dataset-specific method and finding;
3. the answer produced by the unified pipeline;
4. what is preserved, changed, or lost; and
5. what this reveals about generalisability.

The numerical unified results come from
[`cross_dataset_summary.csv`](../../Results/EighthPhase/cross_dataset_summary.csv)
and the session-level outputs under `Results/EighthPhase/`. The earlier
questions come from the phase work logs and
[`Emails_With_Supervisor.md`](../Emails_With_Supervisor.md).

## 2. Overview: Original Question Versus Unified Answer

| Collection | Original phase and main question | Unified answer quality | Main reason |
|---|---|---|---|
| Home_A001 | Phase 1: visualise annotated location, activity, and co-presence | Not testable | Annotation products are available, but parseable raw wearable and beacon streams are not |
| Home_A002 | Phase 2: does low movement identify more reliable RSSI location? | Partial | Movement resolves, but sleep and Bedroom evidence do not; almost no room correction is justified |
| Home_X001 | Phases 3–5: compare two people, algorithms, co-presence, and pressure | Mixed | Co-presence and adaptive RSSI are produced without labels; the revised blind pressure gate rejects a small same-floor pressure split as K=1 |
| DH Paris | Phase 5: compare location algorithms against reference labels | Mixed | Occupancy coverage improves, but room-level agreement is below the earlier dataset-tuned 4b result |
| DH PanoH | Phase 5: compare fixed and movement-adaptive RSSI against labels | Good but not uniformly better | Sleep and away are recovered; end-to-end agreement is high, while balanced room agreement remains below the earlier best fixed method |
| DH Strad | Phase 5: test whether 4b improves labelled room estimation | Partial | Awake smoothing and away work, but sleep remains unresolved and room-level balanced accuracy falls relative to the earlier 4b result |
| KM Mal | Phase 5: compare algorithms with reference location | Good, development-only | Sleep correction is strong and away increases coverage, but the away result is borderline and was inspected during method refinement |
| NewData80h | Phase 6: constrain RSSI by floor, identify stairs, sleep location, and meaningful transitions | Partial | Conservative floor constraint and sleep work; stair duration and normalised mobility metrics still require the specialised high-resolution module |
| EF-001 | Phase 7: correct implausible night-time room switching | Strong | The main phenomenon is reproduced with fewer transitions, although the unified rule is more conservative than the bespoke episode correction |
| EF-002 | Phase 7: recover beacon occlusion gaps during sleep | Strong | Supported sleep gaps are filled and the near-whole-night unsupported gap remains missing |
| KM PanH Nov22 | Additional Eighth Phase stress test: apply the complete framework to a longer unlabelled session | Strong descriptive result | Repeated sleep episodes provide enough evidence for correction and short gap recovery |
| KM PanH Nov28 | Additional short-session stress test | Appropriately unresolved | Three sleep candidates necessarily produce a singleton duration class |
| KM DEC PANAPT | Potential additional dataset | Not testable | Only unexported `SAMPLES.DAT` is available |

“Good” in this table does not mean independently validated accuracy. It means
that the pipeline provides a defensible answer to the original question with
appropriate evidence and uncertainty. A strong transition reduction in an
unlabelled collection remains plausibility evidence rather than proof of the
true room.

## 3. Phase 1 — Home_A001: From Annotation Visualisation to a Raw-Data Framework

### Original question

The First Phase focused on how annotated locations and activities could be
represented: hourly room heatmaps, floorplan animations, two-person
co-presence, and the integration of activity level with location. The input was
primarily `annotator.json` and derived activity annotations, rather than a
reconstruction of location from raw RSSI and wearable signals. The original
work is summarised in [`1.Project_FirstPhase.md`](../1.Project_FirstPhase.md).

### Unified-pipeline result

Home_A001 is excluded from the Eighth Phase because the current workspace does
not contain parseable raw wearable and environmental beacon streams for this
collection. Feeding the existing annotation timeline into the pipeline would
not be a valid re-analysis: it would use a previous location estimate as if it
were a raw sensor input.

### What this comparison shows

The unified pipeline cannot replace the First Phase visualisation work. It
operates one level earlier, converting raw sensor evidence into room,
behaviour, and occupancy states. The First Phase remains useful as a downstream
presentation layer once those states exist. The exclusion is also an important
methodological result: a common algorithm cannot be claimed to generalise to a
dataset whose required raw inputs are unavailable.

## 4. Phase 2 — Home_A002: Does Low Movement Make RSSI More Trustworthy?

### Original question

Derek's initial raw-data question was whether RSSI and movement could be
combined so that low-step periods supplied more reliable room estimates. The
Second Phase compared strongest beacon with RSSI-vector representations,
tested step thresholds, and then tested fixed and adaptive RSSI windows. See
[`2.Project_SecondPhase_Work_Log.md`](../2.Project_SecondPhase_Work_Log.md).

The original findings were:

- strongest beacon was more interpretable and performed better than the full
  RSSI-vector signatures;
- strict low-step subsets had about 0.83 agreement with the existing
  annotation, but only about 41% coverage;
- the 10-minute fixed RSSI baseline slightly outperformed the first hard
  step-adaptive rule;
- the most useful movement result was uncertainty stratification: high-
  confidence windows had 0.845 annotation agreement, compared with 0.580 for
  low-confidence windows; and
- these numbers were annotation agreement, not ground-truth accuracy, because
  the annotation itself was partly derived from RSSI and contained non-room
  states.

### Unified-pipeline result

| Participant | Movement | Sleep candidates | Main sleep | Bedroom | Probable away | Changed windows | Transitions |
|---|---|---:|---|---|---:|---:|---:|
| AA002 | ACC, K=2 | 12 | unresolved | unresolved | 13 | 0 | 157→157 |
| AB002 | Step, K=2 | 16 | unresolved | unresolved | 16 | 1 | 194→194 |

AA002 demonstrates that low-motion detection can resolve without producing a
defensible sleep result. Its duration clustering contains an unsupported
singleton class. AB002 demonstrates a different step-specific failure: bounded
equal-count reconstruction reveals zero-step periods, but an abnormal
4,865-minute plateau forms a singleton extreme-duration class. It may represent
counter failure, non-wear, or a stationary device rather than sleep.

Bedroom cannot be inferred because there is no independent Bedroom metadata
and no resolved cross-night main-sleep evidence. The unified method therefore
does not use the old RSSI-derived annotation to supply a Bedroom label, which
would create circular evidence.

### Answer to the original question

The unified result supports the original conceptual answer but not a strong
room-correction result. Movement is useful for identifying low-motion context,
but low movement alone is not sufficient evidence to change a room. On this
relatively clean collection, only one awake window changes and the two-person
co-presence estimate changes from 69.58 to 69.67 hours.

The difference from the original method is informative. The Second Phase used
movement to select or score reliable subsets; the Eighth Phase asks for enough
evidence to produce a complete behavioural and room correction. The stricter
task exposes missing Bedroom metadata and step-counter failure modes that were
not central to the original confidence analysis.

## 5. Phases 3–5 — Home_X001: Two People, Co-presence, Adaptive RSSI, and Pressure

### Original questions

Home_X001 was introduced as a difficult two-person collection with the same
beacon configuration and no independent reference location. The work evolved
through several questions:

1. Are the two sensor streams usable over their approximately 170-hour shared
   period?
2. How much time are SUBJECT and STUDY_PARTNER in the same room, different
   rooms, or away?
3. How do 5-, 10-, and 30-minute RSSI windows differ?
4. Can step-adaptive windows retain temporal responsiveness while reducing
   noise during low movement?
5. Does low-motion RSSI clustering add useful information?
6. Can pressure add floor information?

These questions are documented in
[`3.Project_X001_Work_Log.md`](../3.Project_X001_Work_Log.md),
[`4.Project_ForthPhase_Work_Log.md`](../4.Project_ForthPhase_Work_Log.md), and
[`5.Project_FifthPhase_Work_Log.md`](../5.Project_FifthPhase_Work_Log.md).

The earlier fixed-window analysis showed the expected responsiveness/stability
trade-off. Five-minute RSSI produced 791 and 777 transitions for the two
participants, whereas 30-minute RSSI produced 126 and 130. Estimated same-room
time stayed in the range of approximately 18–20 hours across those fixed
methods. The step-adaptive method linked smoothing to movement, but the
low-motion clustering and hybrid override did not demonstrate a labelled
accuracy improvement.

### Unified-pipeline result

| Participant | Main sleep | Room-supported sleep | Probable away | Changed windows | Raw→corrected transitions |
|---|---:|---:|---:|---:|---:|
| Left / SUBJECT | 7 episodes, 39.42 h | 4 | 8 | 85 | 346→284 |
| Right / STUDY_PARTNER | 10 episodes, 79.75 h | 10 | 10 | 26 | 495→470 |

On the shared five-minute timeline:

- raw same-room time is 33.25 hours;
- corrected same-room time is 32.67 hours;
- 41 same-room windows are added and 48 are removed; and
- the result is not a one-directional operation that simply makes the two
  people appear together more often.

The absolute co-presence hours should not be directly equated with the earlier
18–20 hour estimates. The input parser, quality control, five-minute grid,
missing-state definition, room mapping, and correction logic have all changed.
This sensitivity is itself a result: co-presence is a downstream metric and can
change materially when the upstream room and missingness definitions change.

### Blind pressure false-floor test

The pressure audit finds visually stable K=2 candidates in both X001 sessions,
but their centre separations are only 0.231 and 0.233 hPa and their silhouettes
are 0.720 and 0.685. Beacons at different mounting heights on one floor, plus
fixed sensor offsets, can create exactly this kind of stable small separation.

The revised blind rule requires at least 0.30 hPa and silhouette 0.75 and is
explicitly allowed to select K=1. It therefore rejects both X001 candidates and
pressure changes no room decisions. The known single-floor description is used
only after inference to confirm that this blind rejection is sensible; it is
not supplied to the algorithm.

### Answer to the original questions

The pipeline answers the descriptive co-presence and adaptive RSSI questions,
but it cannot determine which output is more accurate because no reference
labels exist. X001 is nevertheless a useful negative control: statistical
pressure clustering alone is insufficient, while the floor-scale blind gate
correctly leaves the optional branch inactive. The strongest valid conclusions
remain the audited changes in stability and co-presence, not an accuracy claim.

![Home_X001 left unified timeline](../../Results/EighthPhase/Home_X001/LEFT_WRIST/LEFT_WRIST_2026/raw_vs_corrected_timeline.png)

![Home_X001 right unified timeline](../../Results/EighthPhase/Home_X001/RIGHT_WRIST/RIGHT_WRIST_2026/raw_vs_corrected_timeline.png)

## 6. Phase 5 — Labelled Collections: Does One Method Retain Room Accuracy?

### Original question

The Fifth Phase introduced reference location diaries and asked which of the
fixed, step-adaptive, cluster, and hybrid methods agreed best with annotated
location. The earlier comparison found that 4b step-adaptive RSSI was often
among the best methods, but not uniformly better than fixed RSSI. Cluster-only
4c was consistently weaker in balanced accuracy.

The closest earlier results and the current unified results are summarised
below. They are not identical evaluation protocols: the earlier analysis used
its own windowing and evaluable reference rows, while the unified method uses a
canonical five-minute grid, explicit `Away`/`Unknown`, coverage reporting, and
end-to-end accuracy that counts missing predictions as errors.

| Dataset | Earlier best method: accuracy / balanced accuracy | Unified corrected coverage | Unified conditional accuracy / balanced accuracy | Unified end-to-end accuracy |
|---|---:|---:|---:|---:|
| DH Paris | 4b: 0.889 / 0.766 | 96.6% | 0.641 / 0.670 | 0.619 |
| DH PanoH | Raw 30-min had best balanced accuracy: 0.881 / 0.742; raw 5-min accuracy was 0.931 | 99.0% | 0.905 / 0.660 | 0.896 |
| DH Strad | 4b: 0.945 / 0.875 | 93.4% | 0.878 / 0.692 | 0.820 |
| KM Mal | 4b accuracy 0.930; raw 15-min best balanced accuracy 0.841 | 90.9% | 0.944 / 0.812 | 0.858 |

### 6.1 DH Paris

The original question was whether movement-adaptive RSSI improves labelled
room estimation. The earlier 4b result was already strong. The unified pipeline
now identifies five step-derived main-sleep episodes and 34 probable-away runs,
and changes 45 awake room windows. Four sleep episodes have supported
non-Bedroom RSSI winners, mainly Bathroom. Because zero steps cannot distinguish
sleep from quiet sitting or a stationary device, the unified rule refuses to
lock a step-derived sleep episode unless its dominant room is Bedroom.

This is a reasonable safeguard, but the unified room-level conditional
accuracy is lower than the earlier dataset-tuned 4b result. The end-to-end gain
from raw 0.281 to corrected 0.619 is strongly influenced by increased occupancy
coverage and reference `Out`, not only better indoor rooms. The pipeline answers
a broader occupancy-and-location question, but it is not the best-performing
Paris-specific room classifier.

### 6.2 DH PanoH

Five reconstructed zero-step candidates form a strong 2/3 duration split with
silhouette 0.640. Three Bedroom-supported main-sleep episodes produce 17 sleep
room corrections; three probable-away runs provide most of the reference
coverage increase. End-to-end agreement reaches 0.896.

The earlier fixed 30-minute method still has higher balanced room agreement
than the unified result. The unified advantage is different: it supplies
behaviour, occupancy, missingness, and provenance in one output rather than
optimising only the observed room labels. The unchanged transition count
59→59 also shows that changing individual labels does not necessarily make a
timeline globally smoother.

### 6.3 DH Strad

The earlier 4b method gave the best room-level result in the first labelled
batch. In the unified pipeline, four sleep candidates form a 1/3 split, so the
singleton class is rejected and sleep remains unresolved. Nine awake adaptive
changes reduce transitions from 136 to 122, while 27 probable-away runs improve
end-to-end reference coverage.

This is a partial answer rather than a success over the earlier method. The
unified output is more explicit about occupancy and missingness, but its
balanced room agreement is substantially lower than the earlier 4b result.
Strad demonstrates the performance cost of common safeguards and common
parameters.

### 6.4 KM Mal

KM Mal is the strongest labelled example for the complete state hierarchy. Four
ACC-derived main-sleep episodes are all room-supported; 39 sleep and 15 awake
room corrections reduce transitions from 135 to 78. Seven away candidates give
silhouette 0.489 and duration centres of approximately 144 and 298 minutes. The
2.07 centre ratio allows four runs to be accepted as `borderline` probable
away.

Conditional accuracy rises to 0.944, although balanced accuracy 0.812 is
slightly below the earlier best result. End-to-end agreement reaches 0.858
because the pipeline also recognises reference `Out`. Because the borderline
range was introduced while inspecting this diagnostic, KM Mal must be treated
as a sensitivity/development result rather than independent validation of the
0.45 boundary.

### Cross-labelled interpretation

The labelled datasets show that “best overall pipeline” and “best room
classifier on one dataset” are not the same objective. The unified method is
stronger at expressing the complete state hierarchy and at refusing
unsupported inference. The earlier tuned 4b or fixed windows can retain higher
balanced room accuracy on some datasets. A report should therefore show both
conditional room metrics and end-to-end metrics rather than selecting whichever
single number appears largest.

## 7. Phase 6 — NewData80h: Floor, Stairs, Sleep Location, and Room Transitions

### Original questions

The 80-hour two-floor-home analysis asked whether pressure could constrain RSSI
to the correct floor, whether ACC supported floor changes, and whether the
result could quantify stair use, sleep location, and meaningful room
transitions. The original work is in
[`6.Project_SixthPhase_0705_To_Derek.md`](../6.Project_SixthPhase_0705_To_Derek.md)
and
[`6.Project_SixthPhase_0706_To_Derek.md`](../6.Project_SixthPhase_0706_To_Derek.md).

The bespoke Sixth Phase method found:

- 55/848 windows where raw strongest RSSI disagreed with the pressure floor;
- a direct floor override changed 54 windows;
- raw RSSI floor switches reduced from 75 to 30 after pressure correction;
- 28 stair-transition candidates, including 17 pressure-valid refined events;
- mean ascent and descent durations of 1.13 and 0.78 minutes;
- `3E05` as the leading sleep/Bedroom candidate, representing 94.1% of the
  fixed-night low-motion candidate minutes; and
- 95 room transitions, of which 83 were ACC-supported, equivalent to 6.04
  supported transitions per awake hour.

### Unified-pipeline result

The unified method identifies three strong K=2 main-sleep episodes totalling
20.67 hours. All three are Bedroom-supported. It identifies three probable-away
runs and changes seven room windows: five through pressure and two through sleep
room evidence. Overall transitions reduce from 117 to 113.

The automatic model recovers the documented beacon pairing—1933 with CA59 and
3E05 with D7FD—without reading the earlier floor mapping. The five pressure
changes are much fewer than the earlier 54 because the
unified pressure branch requires high floor confidence and movement support
instead of correcting nearly every pressure/RSSI disagreement. This is a
clear comparison between a diagnostic “brute-force” rule and a conservative
general-purpose constraint.

The configured mapping identifies `3E05` as Bedroom using the participant
feedback that became available after the original inference. Therefore, the
unified result should not be presented as a new independent discovery of the
Bedroom. What it does show is that the general all-day duration clustering
selects repeated long episodes consistent with that known room, without using
the original fixed 18:00–10:00 search range.

### What the unified pipeline does not reproduce

The current Eighth Phase pressure branch operates at five-minute resolution and
uses floor as a constraint on room selection. It does not reconstruct the
10%–90% high-resolution pressure ramp, calculate ascent/descent durations, or
produce stair counts and transitions per awake hour. Those are specialised
behavioural metrics downstream of the common location timeline.

The appropriate relationship is therefore:

```text
unified pipeline
    -> auditable five-minute movement, floor, occupancy, sleep and room state
    -> specialised stair-event and mobility-metric module
```

The unified method partially answers the Sixth Phase question. It generalises
the conservative floor and sleep components, but it cannot yet replace the
specialised stair and normalised room-transition analysis.

![NewData80h unified timeline](../../Results/EighthPhase/NewData80h/559662/559662_80h/raw_vs_corrected_timeline.png)

## 8. Phase 7 — EF-001: Implausible Night-Time Room Switching

### Original question

EF-001 was selected because the strongest RSSI beacon repeatedly moved to
adjacent rooms during sleep even though movement remained very low. The
original question was whether movement could distinguish those radio changes
from plausible physical room transitions. See
[`7.Project_SeventhPhase_Work_Log.md`](../7.Project_SeventhPhase_Work_Log.md).

The bespoke Seventh Phase method used an EF-specific ACC threshold of 0.023,
identified 12 main-sleep candidates, and assigned one episode-dominant room to
all observed windows in each selected episode. It reduced overall transitions
from 719 to 417 and low-motion transitions from 252 to 4. Across the 12
episodes, 253/287 raw transitions occurred during low motion.

### Unified-pipeline result

The unified method independently chooses an ACC low-motion boundary of 0.0184
and a three-class sleep-duration model with centres around 86, 236, and 543
minutes. It selects 11 main-sleep episodes, of which six have at least 60%
room dominance. It changes 155 sleep windows and 32 awake windows, reducing
overall transitions from 693 to 556, a 19.8% reduction. Missing RSSI remains
missing.

### Original versus unified interpretation

The main finding survives: many raw night-time room changes are not supported
by movement, and an episode-level room hypothesis removes a substantial part of
that instability. The numerical improvement is smaller because the unified
method:

- estimates its own recording-specific movement model rather than using 0.023;
- requires at least 60% episode room dominance;
- does not force weak or absent room evidence;
- uses causal trailing movement-adaptive RSSI outside main sleep; and
- preserves the same safeguards used for every collection.

EF-001 is therefore the strongest example of successful generalisation. The
pipeline reproduces the original failure mode and correction direction without
copying the exact threshold or guaranteeing one room for every long episode.

![EF-001 unified raw versus corrected timeline](../../Results/EighthPhase/EF-001/EF-001/EF-001_2026/raw_vs_corrected_timeline.png)

## 9. Phase 7 — EF-002: RSSI Occlusion During Sleep

### Original question

EF-002 represented a different night-time failure. Turning in bed could obscure
all beacon signals, producing RSSI gaps rather than only an incorrect adjacent
room. The original method filled a gap only when the preceding and following
30-minute contexts both supported Bedroom by at least two thirds.

The bespoke analysis filled 15 short Bedroom-supported gaps, corresponding to
38 five-minute windows or 190 minutes. A roughly 700-minute near-full-night gap
had conflicting or insufficient local support and remained missing. The
transition count was effectively unchanged, 586→587, because the aim was gap
recovery rather than general smoothing.

### Unified-pipeline result

The unified ACC and duration models select 12 main-sleep episodes totalling 82
hours; 11 have supported room evidence. It fills 51 five-minute sleep-gap
windows using the same two-sided context principle, changes 12 observed sleep
room windows and four awake windows, and reduces transitions from 543 to 513.
Room coverage increases from 81.50% to 82.94%.

The approximately 710-minute episode with almost no RSSI remains unsupported:
its two observed windows provide only 50% dominant-room support. The pipeline
does not use cross-night Bedroom knowledge to fabricate an entire missing
night.

### Original versus unified interpretation

The central conservative decision is preserved, while the exact number of
filled windows changes because the unified quality filter, movement threshold,
episode boundaries, and gap segmentation are not identical to the bespoke
analysis. Unlike the original gap-only method, the common pipeline also applies
episode correction and awake trailing RSSI, explaining why its transition
count decreases.

EF-002 demonstrates that one framework can respond differently to a different
RSSI failure mode: the same state hierarchy that locks observed unstable sleep
rooms in EF-001 fills only locally supported missing values in EF-002.

![EF-002 unified raw versus corrected timeline](../../Results/EighthPhase/EF-002/EF-002/EF-002_2026/raw_vs_corrected_timeline.png)

## 10. KM PanH Nov22 and Nov28: Evidence-Length Stress Test

These sessions were not the centre of a separate earlier phase question and do
not currently have an independent reference file in the manifest. Their role in
the unified analysis is therefore a stress test of whether identical rules
respond sensibly to different recording lengths.

| Session | Sleep candidates | Main sleep | Room-supported | Corrections | Transitions |
|---|---:|---|---:|---|---:|
| Nov22 | 10 | 6 episodes, 53.33 h | 5 | 65 sleep + 6 gap + 3 awake | 156→111 |
| Nov28 | 3 | unresolved | — | 7 awake | 55→51 |

Nov22 supplies repeated evidence and receives the full sleep, gap-recovery,
away, and awake treatment. Nov28 cannot form two duration classes with at least
two episodes each, so sleep remains unresolved even though its K=2 silhouette
appears high. This is a useful negative control: the pipeline does not force a
sleep result merely because a short recording contains one long episode.

## 11. KM DEC PANAPT: Input-Capability Boundary

KM DEC PANAPT is excluded because only an unexported `SAMPLES.DAT` container is
available. It cannot be processed by the current adapters. As with Home_A001,
this is a data-capability exclusion rather than an algorithmic unresolved state.

The distinction matters:

- `excluded` means the pipeline cannot construct its required inputs;
- `movement_unresolved` means inputs exist but activity clusters are not
  reliable;
- `sleep_unresolved` means movement resolves but repeated duration evidence is
  insufficient; and
- `Unknown` means a particular time interval lacks enough evidence.

## 12. What Types of Question Does the Unified Pipeline Answer Well?

### 12.1 Strong capability: implausible switching during sustained low motion

EF-001 and KM Mal show that repeated strongest-beacon switching can be reduced
when a long low-motion episode has a dominant room. This is the clearest use of
movement as contextual evidence rather than as a room predictor.

### 12.2 Strong capability: short, context-supported sleep gaps

EF-002 and KM PanH Nov22 show that missing RSSI can be recovered without a
general interpolation rule. The pipeline requires two-sided local room evidence
and leaves long or one-sided gaps missing.

### 12.3 Moderate capability: awake room stabilisation

The causal trailing RSSI windows reduce transitions in several datasets, but
the effect is not uniformly positive. Home_X001 Right increases its transition
count, and labelled room metrics do not always outperform the earlier tuned 4b
method.

### 12.4 Useful but metric-sensitive capability: probable away

Away inference substantially improves end-to-end agreement in the labelled
datasets because reference `Out` is no longer treated as a missing room. This
is a legitimate occupancy result, but it must be separated from indoor room
accuracy. KM Mal also shows why borderline away results require explicit audit
and later independent validation.

### 12.5 Descriptive capability only: two-person co-presence without labels

The pipeline produces consistent raw and corrected co-presence definitions,
but it cannot validate them in Home_X001 or Home_A002. Co-presence hours are
sensitive to room quality control, missingness, and pressure constraints.

### 12.6 Incomplete capability: pressure and specialised mobility

NewData80h shows that pressure can provide a conservative vertical constraint.
Home_X001 shows why statistical pressure groups require a floor-scale minimum
separation and a K=1 null outcome. The unified output does not yet quantify
high-resolution stair durations or transitions per awake hour.

### 12.7 Deliberate failure capability: insufficient evidence

AA002, AB002, DH Strad, KM PanH Nov28, Home_A001, and KM DEC PANAPT fail for
different and identifiable reasons. These negative results are part of the
method, not missing successes. The common audit distinguishes sensor
unavailability, counter failure, singleton clusters, short recordings, and
unsupported room inference.

## 13. What Changed From the Earlier Dataset-Specific Methods?

| Earlier approach | Unified approach | Consequence |
|---|---|---|
| Dataset-specific movement thresholds | Same clustering rule, recording-specific fitted threshold | More comparable logic, but exact earlier thresholds and episode counts are not reproduced |
| Fixed or centred smoothing chosen for one dataset | Five-minute base grid; causal trailing awake windows; offline complete sleep episodes | Clearer separation between real-time-compatible awake inference and offline sleep correction |
| Long window could smooth across uncertain context | No crossing of session, RSSI gap, sleep/away, floor, or higher-movement boundaries | Lower risk of inventing continuity, sometimes less smoothing |
| Missing RSSI sometimes treated as away/unmapped | Room, occupancy, behaviour, and missingness are separate fields | Better end-to-end interpretation and less conflation of `Out` with sensor failure |
| Labels used to compare and refine algorithms | Predictions generated before labels are loaded; metrics reported after | Reduced direct leakage at runtime, although DH and KM refinement results remain development evidence |
| Pressure corrected nearly every floor mismatch in the 80-hour diagnostic | Pressure only constrains trusted, movement-supported windows | Far fewer changes; better conservatism but reduced sensitivity |
| Specialised stair and behavioural scripts | Common state and room timeline only | Easier cross-dataset comparison, but extra behavioural modules are still required |

## 14. Main Methodological Finding

The central contribution is not that one algorithm produces the largest metric
for every dataset. It is that one auditable state hierarchy can expose how
different RSSI problems require different forms of sensor support:

- movement suppresses implausible room changes during stable episodes;
- local room context supports short sleep-gap recovery;
- pressure can constrain vertical location when blind floor-scale grouping and
  wearable evidence both pass conservative checks;
- wearable continuity helps distinguish probable away from total recording
  loss; and
- insufficient evidence remains unresolved rather than being converted into a
  confident room.

The re-analysis also identifies the cost of unification. A common method can be
less accurate than a dataset-tuned window and can reject plausible
short-recording sleep. Optional branches also need explicit null outcomes, as
demonstrated by the pressure K=1 result in X001. These are not reasons to
abandon the unified pipeline.
They define where capability metadata, external context, specialised downstream
modules, and independent validation are still needed.

The most defensible report conclusion is therefore:

> A unified movement-supported RSSI pipeline can address several distinct
> indoor-location failure modes using the same evidence hierarchy, but its
> benefit is challenge-dependent. It performs best when movement or local room
> context directly contradicts implausible RSSI behaviour; it is less reliable
> when recordings are short, step counters are ambiguous, floor structure is
> unknown, or the target is a specialised behavioural metric rather than a
> five-minute room state.
