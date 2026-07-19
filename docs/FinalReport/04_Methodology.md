# 4. Methodology

This chapter describes the final methodological framework used in the project: a unified movement-supported RSSI pipeline applied to all parseable wearable-and-beacon datasets. Earlier project phases developed and tested individual ideas, including fixed RSSI windows, movement-adaptive RSSI, low-motion clustering, two-person co-presence, pressure-floor correction, and night-time RSSI correction. In the final method these ideas are consolidated into one auditable five-minute workflow. Earlier methods are therefore treated as development context and comparison baselines rather than as separate main algorithms.

The central principle of the pipeline is that RSSI proposes the room, while movement, sleep and away state, pressure, and missingness determine whether that room estimate should be accepted, stabilised, constrained, or left unresolved. The method is intentionally conservative: it does not force sleep, Bedroom, away, floor, or room labels when the required evidence is absent.

## 4.1 Data Sources, Capability Audit, and Exclusions

The unified pipeline was designed for datasets containing raw wearable and environmental beacon streams. Its required inputs are timestamped RSSI observations, wearable movement data from accelerometer or step count, beacon-room metadata, and optional pressure and reference-label files. Dataset-specific information such as timezone, beacon-room mapping, known Bedroom beacons, and floor mapping is declared as metadata rather than hidden in separate scripts.

Before applying the method, each collection was audited for data capability. The audit recorded whether RSSI, accelerometer, step count, wearable pressure, environmental pressure, and reference labels were available. Thirteen participant-sessions from ten collections were processed. Home_A001 was excluded because only processed annotation products were available, without parseable raw wearable and beacon streams. KM_DEC_PANAPT was excluded because the available `SAMPLES.DAT` container had not been exported to parseable sensor CSV files. These exclusions are data-availability decisions, not algorithmic failures.

The pipeline outputs one result directory per collection and session, including the five-minute timeline, clustering audits, sleep and away summaries, raw-versus-corrected figures, and optional pressure, co-presence, or reference-label outputs. Cross-dataset audit files provide the formal record of processed sessions, exclusions, parameters, and failures.

## 4.2 Unified Five-Minute Sensor Timeline

All sensor streams are converted to UTC and aligned to fixed non-overlapping five-minute windows. The participant-local timestamp is also retained for interpretation, particularly for sleep and daily routine analysis. A five-minute window was selected as the common inference unit because it reduces sample-level radio noise while retaining enough temporal resolution for room-use and co-presence summaries.

For each beacon in each five-minute window, the mean RSSI and sample count are calculated. The raw room proposal is the room of the beacon with the highest quality-controlled mean RSSI. The pipeline also stores RSSI coverage, the number of available beacons, the second-strongest RSSI value, and the gap between the strongest and second-strongest beacon. Low-coverage and empty RSSI windows remain explicitly missing rather than being interpolated.

Movement is aligned to the same five-minute grid. Accelerometer magnitude variability is the preferred movement feature. The three accelerometer axes are combined into magnitude, and the within-window standard deviation is normalised by the recording-level median magnitude. This feature captures wrist motion while reducing dependence on device orientation. At least ten accelerometer samples are required for a valid movement window.

If accelerometer data are unavailable, cumulative step count is used as a fallback. Cumulative counts are converted to positive five-minute increments, with counter resets prevented from becoming negative movement. The step loader also reconstructs bounded zero-step plateaus: if two consecutive exported counter values are identical and no more than 35 minutes apart, the intervening five-minute windows are treated as confirmed zero-step windows. Increasing gaps and equal-count gaps longer than 35 minutes remain missing because the timing of movement or device state is uncertain.

This preprocessing creates a single table for each session containing raw RSSI room proposal, movement feature, movement source, wearable availability, pressure where available, local time, and explicit missingness.

## 4.3 Movement-Supported RSSI State Hierarchy

The movement model is fitted separately for each recording using the same rule. The movement feature is log-transformed and clustered into two, three, or four ordered states. A candidate model is accepted only if its silhouette score is at least 0.25 and every cluster contains at least 5% and at least 20 valid windows. If several models are close, the smallest acceptable K within 0.02 of the best silhouette is selected. Only the lowest movement state is called low motion, and its boundary is the midpoint between the two lowest cluster centres in log space.

The selected number of movement states controls the awake RSSI window length:

| Movement K | Trailing RSSI windows from lowest to highest movement |
|---:|---|
| 2 | 30 min, 5 min |
| 3 | 30 min, 10 min, 5 min |
| 4 | 30 min, 15 min, 10 min, 5 min |

These windows are trailing rather than centred, so awake inference uses current and past data only. The adaptive RSSI window is not allowed to cross recording sessions, RSSI gaps, sleep states, away states, trusted pressure-floor changes, or higher-movement boundaries. If the current awake window has no RSSI evidence, the room remains missing even if earlier RSSI exists.

This branch extends the earlier fixed-window and step-adaptive methods. Low movement supports longer RSSI histories because an isolated strongest-beacon change during a stable period is more likely to reflect radio instability than physical room movement. Higher movement uses shorter windows because genuine transitions are more plausible. Movement is therefore not used as a direct room classifier; it controls how strongly RSSI evidence is temporally stabilised.

## 4.4 Behaviour and Occupancy Inference

The pipeline keeps room, behaviour, and occupancy as separate concepts. This avoids turning `Away`, `Sleep`, or `Unknown` into ambiguous room labels. The final timeline includes a raw RSSI room, corrected room, behaviour state, occupancy state, correction reason, and evidence source.

Low-motion windows are joined into candidate sleep episodes across the full day. Up to 15 minutes of interruption is allowed so that brief movement does not split one longer episode. A candidate must last at least 60 minutes and contain at least 60% low-motion windows. Candidate durations are log-transformed and clustered into two or three duration states. A two-cluster solution requires at least four candidates with at least two candidates per class; a three-cluster solution requires at least six candidates with at least two candidates per class. The longest-duration accepted cluster is selected as main sleep. If the evidence checks fail, the output remains `sleep_unresolved`; the method does not force the longest daily episode to be sleep.

Bedroom evidence is handled separately. If metadata identify Bedroom beacons, that evidence is retained, but it does not override contradictory RSSI. If Bedroom is not known, the same beacon must dominate supported main-sleep episodes on at least two different local nights with at least 60% pooled support before it is inferred as Bedroom.

Within a selected main-sleep episode, observed RSSI is locked to the episode-dominant room only when that room accounts for at least 60% of observed windows. If the dominant room is not Bedroom, the episode remains a supported non-Bedroom sleep episode rather than being forced to Bedroom. Step-derived sleep has an additional safeguard: because zero steps indicate no walking rather than wrist stillness, a step-derived sleep episode can change spatial output only when its supported dominant room is Bedroom.

Missing RSSI gaps are filled only inside a room-supported main-sleep episode and only when the preceding and following 30-minute contexts both contain observations and both support the episode-dominant room in at least two thirds of observed windows. One-sided, conflicting, sparse, and near-whole-night gaps remain missing. Awake RSSI gaps are never filled.

Probable away is inferred after sleep candidates have been derived. Outside selected main sleep, a continuous all-beacon RSSI gap is eligible for away analysis only while the wearable stream remains available. Candidate gap durations are log-transformed and split into two classes. The long-duration class is labelled `Probable away` only when there is enough repeated evidence and the duration separation passes the silhouette and centre-ratio checks. It is not described as confirmed absence.

## 4.5 Optional Branches and Derived Outputs

Pressure is used only when both wearable and environmental beacon pressure are available. Environmental beacon pressure offsets are tested for stable floor-scale groups, but the method is allowed to select a K=1 null model if no reliable multi-floor structure is present. Automatic grouping requires at least two beacons per group, at least 100 overlapping windows, silhouette at least 0.75, adjacent group separation of at least 0.30 hPa, and separation greater than three within-group MADs. These safeguards are needed because beacon mounting height and fixed sensor offsets can create stable pressure subgroups within one floor.

When a pressure model passes, wearable pressure is used to estimate the participant's floor. Only high-confidence floor estimates, at least 0.75, can constrain RSSI to same-floor beacons, and a floor change also requires movement support. Pressure is therefore a conservative vertical constraint on RSSI, not an independent room classifier. Low-confidence or unsupported conflicts leave raw RSSI unchanged.

Two-person collections are handled by first processing each participant independently. The final timelines are then aligned on the shared five-minute UTC grid and compared to calculate raw and corrected same-room time, added and removed co-presence windows, and co-presence stratified by awake, sleep, away, and unknown state. One participant's location is never used to correct the other participant.

The same output schema also supports behavioural summaries. These include main-sleep episodes, sleep-room support, probable-away runs, corrected room coverage, room transition counts, and co-presence duration. Specialised stair-event duration and normalised mobility metrics from the 80-hour pressure analysis are treated as downstream modules: the unified pipeline supplies the auditable five-minute room, floor, movement, and behaviour state, but high-resolution stair timing requires an additional analysis layer.

## 4.6 Evaluation and Comparison Strategy

Evaluation depends on the available evidence. In no-reference datasets, results are descriptive and are evaluated through audit trails, transition counts, correction provenance, RSSI coverage, visual plausibility, and consistency with known dataset capability. These outputs are not presented as true accuracy.

For datasets with reference labels, labels are loaded only after the complete prediction timeline and all model parameters have been generated. The evaluation reports prediction coverage, conditional accuracy on covered windows, balanced accuracy, macro-F1, end-to-end agreement, and confusion matrices. End-to-end agreement counts missing or unknown predictions as incorrect, so coverage changes cannot be hidden. Results are described as agreement with reference annotations rather than ground-truth accuracy.

The report also compares the unified pipeline with earlier dataset-specific methods. The earlier 4b movement-adaptive method and selected fixed-window methods provide labelled-data baselines. The bespoke 80-hour pressure method provides a comparison for the conservative pressure branch. The bespoke EF-001 and EF-002 night-time analyses provide challenge-specific comparisons for unstable observed sleep rooms and sleep-related RSSI gaps. These comparisons are used to assess generalisability, not to claim that the unified method is optimal for every dataset.

Some labelled results are development-set evidence. The bounded step-plateau reconstruction and the step-derived Bedroom restriction were refined after inspecting DH labelled outputs, and the borderline away rule was inspected in KM Mal. The final report therefore distinguishes runtime label separation from independent validation: the pipeline does not load labels during prediction, but unbiased validation requires freezing the rules and applying them to a separate labelled collection.

## 4.7 Use of AI-Assisted Coding Tools

AI-assisted coding tools were used to support code drafting, debugging, refactoring, figure planning, documentation structure, and report organisation. They were not treated as an automatic source of scientific conclusions. Analysis decisions, script execution, output inspection, interpretation, and final responsibility remained with the student.

The main challenge was that AI-generated code or text can appear plausible while using incorrect paths, unsuitable assumptions, over-confident interpretations, or data formats that do not match the repository. For this reason, generated changes were checked against the actual project structure and validated using output files, row counts, timestamp ranges, audit tables, figures, and consistency checks. Further detail on AI-assisted development and verification is placed in Appendix E.
