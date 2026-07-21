# 4. Methodology

## 4.1 Data Sources, Capability Audit, and Exclusions

The final methodological framework is a unified movement-supported RSSI pipeline applied to all wearable-and-beacon datasets. The central principle is that RSSI proposes the room, while movement, sleep and away state, pressure, and missingness determine whether that room estimate should be accepted, stabilised, constrained, or left unresolved. Earlier project phases developed individual ideas, including fixed RSSI windows, movement-adaptive RSSI, low-motion clustering, two-person co-presence, pressure-floor correction, and night-time RSSI correction; in the final method these are consolidated into one auditable five-minute workflow.

The complete workflow is summarised in Figure 1. Raw RSSI, movement, beacon identity or beacon-room information, optional pressure, optional additional metadata, optional second-participant data, and optional reference labels are converted into a common five-minute evidence table. The final timeline then keeps room, behaviour, and occupancy as separate outputs, with optional downstream analyses for co-presence, reference agreement, visual comparisons between raw and corrected data, and cross-dataset summaries.

![Figure 1: Overview of the unified movement-supported RSSI pipeline](figures/figure_4_1_unified_pipeline_overview.svg)

**Figure 1: Overview of the unified movement-supported RSSI pipeline.**

### Raw Inputs

This unified pipeline is specifically designed for datasets comprising data streams from wearable devices (whether raw or manually down-sampled) and data streams from environmental beacons. Its required inputs are timestamped RSSI observations and wearable movement data from accelerometer or step count. Beacon-to-room mapping is required for named room-level outputs, but datasets without such mapping can still be processed at beacon-identity level. Optional files and metadata include pressure data, reference labels, known Bedroom beacons, and floor mapping. Dataset-specific information is declared as metadata rather than hidden in separate scripts.

### Capability Audit

Before applying the method, each collection was audited for data capability. The audit recorded whether RSSI, accelerometer, step count, wearable pressure, environmental pressure, and reference labels were available. Thirteen participant-sessions from ten collections were processed. Home_A001 was excluded because only processed annotation products were available, without raw wearable and beacon streams. KM_DEC_PANAPT was excluded because the available SAMPLES.DAT container had not been exported to sensor CSV files. These exclusions are data-availability decisions, not algorithmic failures.

The pipeline outputs one result directory per collection and session, including the five-minute timeline, clustering audits, sleep and away summaries, raw-versus-corrected figures, and optional pressure, co-presence, or reference-label outputs. Cross-dataset audit files provide the formal record of processed sessions, exclusions, parameters, and failures.

The capability audit also defines the limits of interpretation for each collection. A session without reference labels can contribute descriptive stability and plausibility evidence, but not reference-label agreement. A session without dual pressure cannot activate the floor branch. A session without accelerometer data uses step count as a fallback movement source, but step-derived low motion is interpreted more conservatively than accelerometer-derived low motion. These distinctions are carried through to the results so that differences between datasets are not hidden behind a single output metric.


## 4.2 Unified Five-Minute Sensor Timeline

### Five-Minute Grid

All sensor streams are converted to UTC and aligned to fixed non-overlapping five-minute windows. The participant-local timestamp is also retained for interpretation, particularly for sleep and daily routine analysis. A five-minute window was selected as the common inference unit because it reduces sample-level radio noise while retaining enough temporal resolution for room-use and co-presence summaries.

### RSSI Preprocessing

For each beacon in each five-minute window, the mean RSSI and sample count are calculated. The raw room proposal is the room of the beacon with the highest quality-controlled mean RSSI. The pipeline also stores RSSI coverage, the number of available beacons, the second-strongest RSSI value, and the gap between the strongest and second-strongest beacon. Low-coverage and empty RSSI windows remain explicitly missing rather than being interpolated.

### Movement Preprocessing

Movement is aligned to the same five-minute grid. Accelerometer magnitude variability is the preferred movement feature. The three accelerometer axes are combined into magnitude, and the within-window standard deviation is normalised by the recording-level median magnitude. This feature captures wrist motion while reducing dependence on device orientation. At least ten accelerometer samples are required for a valid movement window.

If accelerometer data are unavailable, cumulative step count is used as a fallback. Cumulative counts are converted to positive five-minute increments, with counter resets prevented from becoming negative movement. The step loader also reconstructs bounded zero-step plateaus: if two consecutive exported counter values are identical and no more than 35 minutes apart, the intervening five-minute windows are treated as confirmed zero-step windows. Increasing gaps and equal-count gaps longer than 35 minutes remain missing because the timing of movement or device state is uncertain.

### Missingness

At this stage, missingness is treated as evidence about the data stream rather than as a room. A five-minute window with no quality-controlled RSSI is not automatically classified as “away”, Bedroom, or the previous observed room. Later stages may interpret some missing runs as probable away or may fill a short sleep gap, but only after additional evidence checks have been applied.

## 4.3 Movement-Supported RSSI State Hierarchy

This section describes the movement-supported RSSI logic conceptually. Movement states are derived first, followed by sleep, occupancy, and reliable-pressure masks.

### Movement Clustering

The movement model is fitted separately for each recording using the same rule. The movement feature is log-transformed and clustered into two, three, or four ordered states. A candidate model is accepted only if its silhouette score is at least 0.25 and every cluster contains at least 5% and at least 20 valid windows. If several models are close, the smallest acceptable K within 0.02 of the best silhouette score is selected. Only the lowest movement state is called low motion, and its boundary is the midpoint between the two lowest cluster centres in log space.

### Awake RSSI Window Rule

The awake RSSI window lengths associated with each movement-state model are summarised in Table 1:

| Movement K | Trailing RSSI windows from lowest to highest movement |
|---:|---|
| 2 | 30 min, 5 min |
| 3 | 30 min, 10 min, 5 min |
| 4 | 30 min, 15 min, 10 min, 5 min |

**Table 1: The K of movement states controls the awake RSSI window length.**

These windows are trailing rather than centred, so awake inference uses current and past data only. The adaptive RSSI window is not allowed to cross recording sessions, RSSI gaps, sleep states, away states, trusted pressure-floor changes, or higher-movement boundaries. If the current awake window has no RSSI evidence, the room remains missing even if earlier RSSI exists.

This branch extends the earlier fixed-window and step-adaptive methods. Low movement supports longer RSSI histories because an isolated strongest-beacon change during a stable period is more likely to reflect radio instability than physical room movement. Higher movement uses shorter windows because genuine transitions are more plausible. Movement is therefore not used as a direct room classifier; it controls how strongly RSSI evidence is temporally stabilised.

The awake branch is deliberately different from sleep correction. Awake adaptive RSSI is causal and trailing: it can be calculated using current and previous evidence only. Sleep correction is retrospective because the complete low-motion episode must first be identified and tested. This distinction matters because the final pipeline is intended both as an analysis method and as a transparent description of what evidence was available at each decision point.

## 4.4 Behaviour and Occupancy Inference

The pipeline keeps room, behaviour, and occupancy as separate concepts. This avoids turning Away, Sleep, or Unknown into ambiguous room labels. The final timeline includes a raw RSSI room, corrected room, behaviour state, occupancy state, correction reason, and evidence source.

### Main-Sleep Identification

Low-motion windows are joined into candidate sleep episodes across the full day. Up to 15 minutes of interruption is allowed so that brief movement does not split one longer episode. A candidate must last at least 60 minutes and contain at least 60% low-motion windows. Candidate durations are log-transformed and clustered into two or three duration states. A two-cluster solution requires at least four candidates with at least two candidates per class; a three-cluster solution requires at least six candidates with at least two candidates per class.

The longest-duration accepted cluster is selected as main sleep. If the evidence checks fail, the output remains sleep-unresolved; the method does not force the longest daily episode to be sleep.

### Sleep-Room Evidence

Bedroom evidence is handled separately. If metadata identify Bedroom beacons, that evidence is retained, but it does not override contradictory RSSI. If Bedroom is not known, the same beacon must dominate supported main-sleep episodes on at least two different local nights with at least 60% pooled support before it is inferred as Bedroom.

Within a selected main-sleep episode, observed RSSI is locked to the episode-dominant room only when that room accounts for at least 60% of observed windows. If the dominant room is not Bedroom, the episode remains a supported non-Bedroom sleep episode rather than being forced to Bedroom. Step-derived sleep has an additional safeguard: because zero steps indicate no walking rather than wrist stillness, a step-derived sleep episode can change spatial output only when its supported dominant room is Bedroom.

Missing RSSI gaps are filled only inside a room-supported main-sleep episode and only when the preceding and following 30-minute contexts both contain observations and both support the episode-dominant room in at least two thirds of observed windows. One-sided, conflicting, sparse, and near-whole-night gaps remain missing. Awake RSSI gaps are never filled.

### Away / Unknown

Probable away is inferred after sleep candidates have been derived. Outside selected main sleep, a continuous all-beacon RSSI gap is eligible for away analysis only while the wearable stream remains available. Candidate gap durations are log-transformed and split into two classes. The long-duration class is labelled Probable away only when there is enough repeated evidence and the duration separation passes the silhouette and centre-ratio checks. It is not described as confirmed absence.

### Final Timeline States

The final state hierarchy is summarised in Table 2. Separating these columns is a key methodological decision because the same time window may have strong evidence for one state but weak evidence for another. For example, a window can be behaviourally classified as main sleep while its room remains missing, or it can be classified as probable away without assigning any indoor room.

| Column | Role in the pipeline | Example states or values |
|---|---|---|
| Raw RSSI room | Initial strongest-beacon room proposal | Bedroom, Kitchen, unmapped, missing |
| Corrected room | Final room estimate after supported correction | Raw room, sleep-dominant room, pressure-constrained room, missing |
| Behaviour state | Interprets movement context | Awake, main sleep, sleep unresolved, movement unresolved |
| Occupancy state | Interprets presence or data absence | Indoor observed, indoor inferred during sleep, probable away, unknown |
| Correction reason | Records why the final room differs from raw RSSI | Raw unchanged, awake adaptive RSSI, sleep episode dominance, sleep gap support, pressure constraint |

**Table 2: Main state columns retained in the final five-minute timeline.**

## 4.5 Optional Branches and Derived Outputs

### Pressure Support

Pressure is used only when both wearable and environmental beacon pressure are available. Environmental beacon pressure offsets are tested for stable floor-scale groups, but the method is allowed to select a K=1 null model if no reliable multi-floor structure is present. Automatic grouping requires at least two beacons per group, at least 100 overlapping windows, silhouette at least 0.75, adjacent group separation of at least 0.30 hPa, and separation greater than three within-group MADs. These safeguards are needed because beacon mounting height and fixed sensor offsets can create stable pressure subgroups within one floor.

When a pressure model passes, wearable pressure is used to estimate the participant's floor. Only high-confidence floor estimates, at least 0.75, can constrain RSSI to same-floor beacons, and a floor change also requires movement support. Pressure is therefore a conservative vertical constraint on RSSI, not an independent room classifier. Low-confidence or unsupported conflicts leave raw RSSI unchanged.

Algorithmically, the pressure branch first estimates relative environmental pressure offsets by subtracting the within-window median pressure across beacons. It then tests K=2 and K=3 one-dimensional KMeans models on the median beacon offsets. A model is accepted only when every group contains enough beacons, the silhouette criterion is met, and the group separation is large enough to be consistent with a floor-scale difference rather than sensor mounting height. When accepted, wearable pressure is calibrated against the raw RSSI winner's environmental pressure group, and only trusted floor estimates restrict RSSI to same-floor beacons.

### Two-Person Co-Presence

Two-person collections are handled by first processing each participant independently. The final timelines are then aligned on the shared five-minute UTC grid and compared to calculate raw and corrected same-room time, added and removed co-presence windows, and co-presence stratified by awake, sleep, away, and unknown state. One participant's location is never used to correct the other participant.

The co-presence branch therefore occurs after individual inference. A window is counted as corrected co-presence only when both participants have known corrected rooms, both are treated as indoor, and their corrected rooms match. Co-presence is also stratified by behaviour and occupancy state so that sleep-related same-room time, awake same-room time, away periods, and unknown intervals are not conflated.

### Final Timeline and Downstream Outputs

The same output schema also supports behavioural summaries. These include main-sleep episodes, sleep-room support, probable-away runs, corrected room coverage, room transition counts, and co-presence duration. Specialised stair-event duration and normalised mobility metrics from the 80-hour pressure analysis are treated as downstream modules: the unified pipeline supplies the auditable five-minute room, floor, movement, and behaviour state, but high-resolution stair timing requires an additional analysis layer. The unified pipeline keeps only the conservative five-minute floor constraint in the main method.

## 4.6 Evaluation and Comparison Strategy

### Reference Agreement

Evaluation depends on the available evidence. In no-reference datasets, results are descriptive and are evaluated through audit trails, transition counts, correction provenance, RSSI coverage, visual plausibility, and consistency with known dataset capability. These outputs are not presented as true accuracy.

For datasets with reference labels, labels are loaded only after the complete prediction timeline and all model parameters have been generated. The evaluation reports prediction coverage, conditional accuracy on covered windows, balanced accuracy, macro-F1, end-to-end agreement, and confusion matrices. End-to-end agreement counts missing or unknown predictions as incorrect, so coverage changes cannot be hidden. Results are described as agreement with reference annotations rather than independently verified accuracy.

For labelled datasets, Probable away is mapped to the reference Out category during evaluation, but this mapping is reported separately from indoor room correction. Coverage is the proportion of labelled windows with an evaluable prediction. Conditional accuracy, balanced accuracy, and macro-F1 are calculated only on covered labelled windows. End-to-end agreement is calculated across all labelled windows after missing predictions are treated as Unknown.

### Comparator Methods

The unified pipeline is also compared with earlier dataset-specific methods: The earlier movement-adaptive method and selected fixed-window methods provide labelled-data baselines. The bespoke 80-hour pressure method provides a comparison for the conservative pressure branch. The bespoke EF-001 and EF-002 night-time analyses provide challenge-specific comparisons for unstable observed sleep rooms and sleep-related RSSI gaps. These comparisons are used to assess generalisability, not to claim that the unified method is optimal for every dataset.

Some labelled results are development-set evidence. The bounded step-plateau reconstruction and the step-derived Bedroom restriction were refined after inspecting DH labelled outputs, and the borderline away rule was inspected in KM Mal. The final report therefore distinguishes runtime label separation from independent validation: the pipeline does not load labels during prediction, but unbiased validation requires freezing the rules and applying them to a separate labelled collection.

Earlier methods are included in the evaluation only when they clarify what is gained or lost by generalisation. For example, a dataset-tuned movement-adaptive method may achieve higher room accuracy on a labelled dataset, while the unified pipeline may provide stronger provenance, occupancy interpretation, and unresolved-state handling. Similarly, the bespoke 80-hour pressure method may be more sensitive to floor mismatches, while the unified pressure branch is more conservative and portable. These comparisons are used to interpret method scope rather than to select a single universally best algorithm.

## 4.7 Safeguards

The pipeline includes explicit failure behaviour. If movement clustering fails, movement remains unresolved. If duration clustering does not provide enough repeated evidence, sleep remains unresolved. If pressure grouping does not satisfy floor-scale criteria, the K=1 null outcome is selected and pressure has no effect. If reference labels are unavailable, the dataset contributes descriptive evidence only. These outcomes are reported rather than repaired manually. Main safeguards are summarised in Figure 2.

![Figure 2: Replication-critical safeguards used by the unified pipeline](figures/figure_4_2_replication_safeguards.svg)

**Figure 2: Replication-critical safeguards used by the unified pipeline.**
