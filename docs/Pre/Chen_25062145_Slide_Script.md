# Chen 25062145 — MSc/MRes Project Talk Speaker Script

## Presentation overview

- **Deck:** `Chen_25062145_Slide.pptx`
- **Main presentation:** Slides 1–15
- **Backup slides:** Slides 16–17; use only during questions
- **Target speaking time:** approximately 13 minutes 45 seconds
- **Hard limit:** 15 minutes
- **Question time:** 5 minutes

The wording below is a rehearsal script, not text to read mechanically. During delivery, look at the audience at the start and end of each slide, pause briefly after each headline result, and point to the relevant visual rather than describing every visible element.

---

## Slide 1 — From room signals to lived experience

**Target time: 0:20**

Good afternoon. My project focus on how wearable activity and room-level location evidence can be combined to give a more interpretable description of daily life at home. I developed and evaluated a unified pipeline that combines movement, RSSI and pressure and multiple-participant data.


**Transition:** I will begin with why location context matters clinically.

## Slide 2 — Activity counts need context

**Target time: 0:55**

Traditional assessments and patient reports are useful, but they can miss day-to-day variation. Wearable devices provide continuous activity measurements, but an activity count alone does not explain what the person was doing or where it occurred.

For example, the same two thousand steps could represent movement between a bedroom and kitchen, repeated stair use, or activity outside the home. Room-level context can therefore make wearable measurements more relevant to routine, mobility and independence. This is particularly valuable in ageing and long-term disease, where change in everyday function may be clinically meaningful.

**Transition:** Bluetooth beacons offer a practical source of this context, but their signals are imperfect.

## Slide 3 — BLE localisation is useful—but real homes are difficult

**Target time: 0:55**

A transparent baseline is to assign each time window to the room containing the strongest BLE(Bluetooth Low Energy) beacon.

However, RSSI(received signal strength indicator) is noisy. It changes with body position and the physical environment. A transition window may contain signals from several rooms, and in a multi-floor home a strong signal can arrive from the wrong floor. Missing RSSI creates a further problem: it may mean absence, sensor failure or simply lack of data.

Validation is also difficult. Continuous observation reduces realism, while diaries may be not accurate enough. The research gap is therefore not just improving a room label; it is combining evidence without hiding uncertainty.

## Slide 4 — Aim: move from room labels to behavioural evidence

**Target time: 0:50**

My aim was to combine wearable movement, BLE RSSI and environmental context to describe behaviour in the home.

The work had five connected objectives: first, align the sensor streams; second, establish a transparent RSSI baseline; third, add movement and floor context; fourth, translate location estimates into behavioural summaries such as co-presence and transitions; and fifth, evaluate each dataset using the strongest evidence.

The most important is that location is intermediate evidence. The final purpose is to describe patterns of lived experience, not simply to maximise room-classification accuracy.

## Slide 5 — Heterogeneous data require evidence-aware evaluation

**Target time: 0:55**

RSSI and either accelerometer or step data were required. Pressure, mutiple participant and reference labels were available only in some collections.

I therefore used different levels of evaluation. Without reference labels, I report transition stability, coverage and visual plausibility. With existing annotations, I report coverage, conditional accuracy, balanced accuracy, macro-F1 and end-to-end agreement. These are described as agreement rather than ground-truth accuracy, because the annotations are not always independent observation.

## Slide 6 — One auditable five-minute pipeline

**Target time: 1:05**

This is the final unified workflow. All available streams are aligned to non-overlapping five-minute windows in UTC, while local time is retained for interpretation.

RSSI features include the strongest and second-strongest beacon, signal separation and coverage. Accelerometer magnitude variability is the preferred movement feature, with step increments used as a fallback.

Movement states and the sleep, occupancy and reliable-pressure masks are then derived. These guide the movement-adaptive RSSI stage. The final timeline stores room, behaviour and occupancy separately, together with the correction reason and evidence source.

The central principle is that RSSI proposes location, while contextual evidence decides whether to accept, constrain or leave it unresolved.

## Slide 7 — Movement changes how RSSI is trusted

**Target time: 0:55**

Movement is not used as a direct room classifier. Instead, it controls how much recent RSSI history is trusted.

During low movement, an isolated strongest-beacon change is more likely to be radio instability than a true transition, so the method uses a longer trailing history—up to thirty minutes. At higher movement, genuine transitions are more plausible, so the history shortens to between five and fifteen minutes.

## Slide 8 — Room, behaviour and occupancy remain separate

**Target time: 0:55**

A key design decision was to keep room, behaviour and occupancy as separate outputs. A window may have strong evidence of main sleep while its room remains unknown, or it may be classified as probable away without assigning an indoor room.

The safeguards make this separation operational. Awake RSSI gaps are never interpolated. A short gap during a supported sleep episode is filled only when both neighbouring contexts support the same room. Pressure can constrain the candidate beacons only when the floor model and confidence checks pass.

## Slide 9 — The unified pipeline ran across 13 sessions without failure

**Target time: 0:50**

The unified pipeline processed ten collections and thirteen participant-sessions, and produced no pipeline failures.

Nine sessions used accelerometer movement and four used step fallback. Main sleep resolved in nine sessions; four remained unresolved because repeated-duration or room-support criteria were not met. Away-duration modelling resolved in all thirteen processed sessions.

## Slide 10 — Corrections were selective—not blanket smoothing

**Target time: 0:55**

Across all sessions, only 579 windows changed from the raw strongest-RSSI room.

Only 57 five-minute gaps were filled across the full run. Fifty-one were in EF-002 and six in KM PanH November 22. Most missing evidence therefore stayed missing. Reduced transition count is evidence of stability, but it is not by itself proof of improved accuracy.

## Slide 11 — End-to-end agreement improved in all four labelled datasets

**Target time: 1:05**

In the four labelled collections, end-to-end agreement improved after correction.

The mechanism matters. In the three DH datasets, much of the end-to-end gain came from explicitly representing probable-away periods and matching reference Out labels, rather than from room smoothing alone. KM Mal showed stronger room-level sleep correction.

The unified method did not beat every dataset-specific classifier on every conditional metric. Its advantage is broader: common state definitions, explicit missingness, correction provenance and comparable reporting. These values remain agreement with existing annotations, not independent ground truth.

## Slide 12 — Case study: only supported RSSI gaps were repaired

**Target time: 1:05**

EF-002 illustrates the conservative logic. The top row shows a noisy raw room sequence. The middle row identifies repeated main-sleep episodes, and the lower row classifies RSSI gaps according to their context.

Short gaps surrounded on both sides by consistent bedroom evidence were eligible for filling. This recovered 51 five-minute windows. By contrast, the long gap around the twenty-third—approximately seven hundred minutes—lacked sufficient two-sided evidence and remained missing.

Room transitions reduced from 543 to 513, but the more important result is the failure behaviour: the method repairs local gaps when the evidence is strong and refuses to invent a whole night of location when it is not.

## Slide 13 — Optional branches extend location into behaviour

**Target time: 1:05**

The same timeline supports two extensions closer to lived experience.

For the two-person Home_X001 collection, each participant was processed independently before their timelines were aligned. Corrected same-room time was 32.67 hours. Correction added 41 co-presence windows and removed 48, so it did not simply increase apparent togetherness. Without an independent reference, this is estimated co-presence, not verified social interaction.

In the two-floor 80-hour dataset, the pressure branch automatically recovered two stable beacon groups.  In the single-floor Home_X001 case, the same rules selected the K=1(means one floor). This demonstrates the robustness of the pressure branch.


## Slide 14 — Generalisability came with an explicit trade-off

**Target time: 1:00**

My interpretation of the unified method is therefore deliberately bounded: this is a useful and reproducible framework for exploratory home-behaviour analysis, but it is not yet a validated clinical system. The next validation should freeze the rules and test them across new labelled participants and home layouts.


## Slide 15 — Take-home message

**Target time: 0:40**

There are three take-home messages. First, room-level evidence gives wearable activity functional context. Second, interpretable fusion can stabilise RSSI while preserving uncertainty: unsupported evidence remains missing or unresolved. Third, the resulting timeline can support co-presence, floor and mobility summaries rather than ending at a room label.

The immediate next step is independent validation after freezing the pipeline rules. Thank you, and I am happy to take questions.

---

# Backup-slide guidance

## Slide 16 — Replication-critical thresholds

Do not present this slide during the timed talk. Use it if asked how thresholds were chosen, how sleep gaps were filled, or what makes the pressure branch conservative. Emphasise that thresholds are declared centrally and all failed checks return unresolved or inactive states.

## Slide 17 — Selected sources

Use this slide if asked about the clinical motivation, BLE localisation literature, prior validation work, or the basis for pressure-derived floor inference.

---

# Likely questions and concise answers

## Why did you choose five-minute windows?

Five minutes reduced sample-level RSSI noise while retaining sufficient temporal resolution for room-use, co-presence and routine summaries. It also provided a common inference unit across streams with different sampling patterns. High-resolution stair timing remains a separate downstream module because a five-minute grid is too coarse for event duration.

## Does reducing transitions demonstrate improved localisation?

No. Transition reduction is a stability diagnostic, not an accuracy metric. I interpret it together with coverage, correction provenance, RSSI evidence and reference-label agreement where labels are available.

## Why not use a supervised machine-learning model?

Independent labels were limited and heterogeneous. A supervised model would risk overfitting a small set of homes. I therefore prioritised transparent baselines and auditable rules. Supervised or semi-supervised models are a future extension once larger independently labelled datasets are available.

## Why do you say “agreement” rather than “accuracy”?

Some reference annotations may be algorithm-derived or otherwise not independent ground truth. “Agreement” accurately describes the comparison without overstating certainty. Even diary or observation labels have timing and realism limitations.

## Did the labelled data leak into prediction?

Labels are loaded only after prediction and parameter generation at runtime. However, some rules were refined after inspecting labelled development outputs, so the current labelled results are development-set evidence. A new frozen-rule validation set is required for an unbiased estimate.

## How can a per-session movement threshold be called generalisable?

The numerical threshold adapts because sensor scale and behaviour differ between recordings. What generalises is the fitting rule: the same transformation, candidate K values, silhouette requirement, minimum cluster support and failure behaviour are applied to every session.

## Why is probable away not simply missing RSSI?

Probable away is inferred only for repeated long all-beacon gaps outside selected sleep while the wearable stream remains available. Short, ambiguous or insufficiently repeated gaps remain unknown. It is still described as probable rather than confirmed absence.

## What is the main novelty?

The contribution is not a new BLE ranging model in isolation. It is an interpretable evidence hierarchy that combines RSSI, movement, missingness and optional pressure, retains correction provenance, separates room from behaviour and occupancy, and supports co-presence and behavioural summaries across heterogeneous home datasets.

## Can estimated co-presence be interpreted as social interaction?

No. It indicates that two independently estimated room states matched while both participants appeared indoors. Interaction requires independent behavioural or observational evidence.

## What would you do next?

I would freeze the current rules, evaluate them on additional independently labelled homes, add explicit uncertainty scores to probabilistic room estimates, and test whether richer accelerometer features improve transition detection without sacrificing interpretability.
