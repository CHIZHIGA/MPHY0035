# 5. Results

## 5.1 Dataset Scope and Capability Audit

The unified pipeline processed 13 participant-sessions from ten collections, comprising 25,513 five-minute windows or approximately 2,126 hours. Nine sessions used accelerometer-derived movement and four used step count as a fallback. Four sessions had reference annotations, four had both wearable and environmental pressure, and two collections contained two participants. The complete run produced no pipeline failures. The overall capability and processing audit is summarised in Figure 3.

![Figure 3: Overall capability and processing audit](figures/figure_5_1_capability_processing_audit.svg)

**Figure 3: Overall capability and processing audit for the unified pipeline.**

Two collections were excluded before analysis. Home_A001 contained processed annotation products but not the raw wearable and beacon streams required by the pipeline. KM_DEC_PANAPT contained an unexported `SAMPLES.DAT` container but no parseable sensor CSV files. These were input-capability exclusions rather than algorithmic failures.

## 5.2 Unified Movement and State Outputs

The same five-minute schema and evidence hierarchy were applied to every parseable session. Eleven sessions selected two movement states and two selected three states; no session selected four. Main sleep resolved in nine sessions and remained unresolved in four. Away-duration clustering resolved in all 13 sessions, although the resulting states remain `Probable away` rather than confirmed absence.

Figure 4 summarises the principal session-level outputs. Room coverage refers to windows with a room estimate and is distinct from the reference-evaluable coverage reported later.

![Figure 4: Session-level unified pipeline outputs](figures/figure_5_2_session_level_outputs.svg)

**Figure 4: Session-level outputs from the unified movement-supported RSSI pipeline.**

The unresolved outputs demonstrate the operation of the safeguards. AA002 and AB002 both produced valid movement clusters but did not provide sufficient repeated duration and Bedroom evidence for main-sleep correction. DH Strad and KM PanH Nov28 also remained sleep-unresolved because their candidate duration distributions did not satisfy the repeated-class criteria. No manual sleep label was substituted in these cases.

## 5.3 Room Correction, Missingness, and Stability

Across all sessions, 579 of 25,513 windows (2.27%) changed from the raw strongest-RSSI room. The number of transitions between consecutive observed room windows decreased from 3,353 to 2,961, a reduction of 392 transitions or 11.7%. Weighted room coverage increased only from 76.48% to 76.70%. This small change was expected because awake RSSI gaps were never filled.

Only 57 missing windows were assigned a room through two-sided sleep-gap support. Fifty-one occurred in EF-002 and six in KM PanH Nov22, equivalent to 285 minutes across the complete dataset. All other missing RSSI windows remained missing unless they were represented separately by an occupancy state such as `Probable away`.

The largest absolute transition reductions occurred in EF-001 (693 to 556), Home_X001 Left wrist (346 to 284), KM Mal (135 to 78), and KM PanH Nov22 (156 to 111). These reductions indicate that the corrected timelines were more stable, but they are not accuracy results. Their credibility depends on the associated movement, sleep-room, pressure, or reference evidence.

EF-001 and EF-002 show how the same hierarchy responded to different failure modes. In EF-001, supported main-sleep episodes reduced repeated room switching during low movement. In EF-002, short missing intervals were filled only when both surrounding 30-minute contexts supported the same sleep room. The long unsupported overnight gap remained missing. These outputs are shown in Figures 5 and 6.

![Figure 5: EF-001 raw and corrected room timeline](../../Results/EighthPhase/EF-001/EF-001/EF-001_2026/raw_vs_corrected_timeline.png)

**Figure 5: EF-001 raw and corrected room timeline during supported low-motion episodes.**

![Figure 6: EF-002 raw and corrected room timeline](../../Results/EighthPhase/EF-002/EF-002/EF-002_2026/raw_vs_corrected_timeline.png)

**Figure 6: EF-002 timeline showing supported sleep-gap recovery and retained missingness.**

The earlier EF-specific analyses reached the same qualitative conclusions with more dataset-specific rules. For EF-001, the bespoke method reduced transitions from 719 to 417, whereas the unified method reduced them from 693 to 556 under its own common window and episode definitions. For EF-002, the bespoke method filled 38 five-minute Bedroom-supported gap windows and the unified method filled 51; both retained the near-whole-night unsupported gap. The unified method was therefore more conservative for EF-001 while preserving the central result in both challenge datasets.

## 5.4 Agreement with Reference Annotations

Four collections were evaluated against reference annotations after prediction: DH Paris, DH PanoH, DH Strad, and KM Mal. Figure 7 separates room or occupancy prediction coverage from agreement on covered windows. `Probable away` was mapped to the reference `Out` category for this evaluation, so the increase in reference-evaluable coverage is not equivalent to an increase in indoor room coverage.

![Figure 7: Agreement with reference annotations](figures/figure_5_3_reference_agreement.svg)

**Figure 7: Agreement with reference annotations before and after unified correction.**

End-to-end agreement increased in all four labelled datasets. For the three DH collections, much of this increase came from assigning `Probable away` during reference `Out` periods. KM Mal showed the strongest indoor correction result: four room-supported main-sleep episodes and 54 changed windows reduced room transitions from 135 to 78, while conditional agreement increased from 86.2% to 94.4%.

Figures 8 and 9 show the confusion matrices for DH PanoH and KM Mal. DH PanoH represents a high-coverage step-fallback case, whereas KM Mal represents the strongest labelled example using the complete accelerometer-based state hierarchy.

![Figure 8: DH PanoH reference confusion matrices](../../Results/EighthPhase/Labelled_DH_PanoH/DH/DH_PanoH_2023/reference_confusion_matrix.png)

**Figure 8: DH PanoH reference agreement before and after unified correction.**

![Figure 9: KM Mal reference confusion matrices](../../Results/EighthPhase/Labelled_KM_Mal/KM/KM_Mal_2023/reference_confusion_matrix.png)

**Figure 9: KM Mal reference agreement before and after unified correction.**

The closest earlier labelled comparisons are shown in Figure 10. These are not identical evaluation protocols: the earlier methods used their own windowing and evaluable rows, whereas the unified method used a canonical five-minute grid, explicit occupancy states, and coverage-aware reporting.

![Figure 10: Earlier dataset-specific labelled results compared with the unified pipeline](figures/figure_5_4_dataset_specific_comparison.svg)

**Figure 10: Earlier dataset-specific labelled results compared with the unified pipeline.**

The unified pipeline did not exceed the earlier dataset-specific method on every room-level metric. Its corrected conditional accuracy was highest for KM Mal, but balanced accuracy remained slightly below the earlier best result. In DH Paris, DH PanoH, and DH Strad, the earlier 4b or fixed-window method retained higher room-level agreement on at least one reported metric. The unified outputs instead added common occupancy, behaviour, missingness, and correction-provenance states.

These labelled results are development-set evidence. The bounded step-plateau reconstruction and step-derived Bedroom safeguard were refined after inspection of DH outputs, and the borderline away rule was inspected in KM Mal. Although reference labels were not loaded during prediction, independent validation would require freezing these rules and applying them to a separate labelled collection.

## 5.5 Optional Branches and Lived-Experience Outputs

### Two-Person Co-Presence

The two-person branch produced co-presence summaries for Home_A002 and Home_X001 after each participant had been processed independently. Home_A002 changed by only one same-room window because the individual room estimates were almost unchanged. In Home_X001, corrected same-room time decreased from 33.25 to 32.67 hours. Forty-one same-room windows were added and 48 were removed, showing that correction did not operate by simply increasing apparent co-presence.

| Collection / stratum | Overlap windows | Raw same-room hours | Corrected same-room hours | Added windows | Removed windows |
|---|---:|---:|---:|---:|---:|
| Home_A002 / all | 2,688 | 69.58 | 69.67 | 1 | 0 |
| Home_X001 / all | 2,052 | 33.25 | 32.67 | 41 | 48 |
| Home_X001 / awake | 586 | 13.50 | 13.58 | 3 | 2 |
| Home_X001 / sleep | 628 | 19.75 | 19.08 | 38 | 46 |

**Table 3: Raw and corrected same-room time in the two-person collections.**

These values describe estimated same-room occupancy, not verified social interaction. Home_X001 has no independent room labels, so the result provides a time-resolved behavioural summary and a correction audit rather than an accuracy estimate.

### Pressure and Floor Context

The dual-pressure branch activated only for NewData80h. Its automatic model grouped beacons `1933` with `CA59` and `3E05` with `D7FD`, matching the documented two-floor pairing. The K=2 model had a silhouette score of 0.865 and a group separation of approximately 0.381 hPa. Although 472 windows had trusted pressure evidence, the floor constraint changed only five room windows; sleep-room evidence changed two more. Overall room transitions decreased from 117 to 113.

The NewData80h output is shown in Figure 11. The earlier bespoke pressure analysis changed 54 windows and reduced raw RSSI floor switches from 75 to 30. The unified branch was less sensitive because it required both high floor confidence and movement support. It therefore reproduced the floor grouping as a conservative five-minute constraint but did not replace the specialised high-resolution stair and mobility analysis.

![Figure 11: NewData80h raw and corrected timeline](../../Results/EighthPhase/NewData80h/559662/559662_80h/raw_vs_corrected_timeline.png)

**Figure 11: NewData80h timeline with conservative pressure-supported floor correction.**

Pressure remained inactive in EF-002 and both Home_X001 sessions. EF-002 did not produce stable multi-floor grouping. In Home_X001, the two candidate pressure groups had separations of approximately 0.231 and 0.233 hPa and silhouette scores of 0.720 and 0.685. Both failed the predefined floor-scale thresholds, so the K=1 null outcome was retained. This was consistent with the known single-floor setting, but that contextual knowledge was not supplied to the pressure model.

### Behavioural Summaries

The common timeline generated 61 selected main-sleep episodes and 158 probable-away runs, together with room-transition and co-presence summaries. NewData80h also produced three Bedroom-supported main-sleep episodes totalling 20.67 hours. These outputs show that room estimates could be translated into candidate sleep location, away periods, floor context, mobility transitions, and together/apart patterns while retaining the evidence source for each state.

## 5.6 Principal Findings Linked to the Study Objectives

The first objective was met at the processing level: a common capability audit and five-minute schema ran across ten collections and 13 participant-sessions without failure. For the second and third objectives, the movement-supported hierarchy reduced observed room transitions by 11.7% while preserving missingness and explicit unresolved states.

For the fourth objective, the final timelines supported sleep, probable-away, room-transition, pressure-floor, and two-person co-presence summaries. For the fifth, corrected end-to-end agreement exceeded raw agreement in all four labelled datasets, while no-reference results remained descriptive. The unified pipeline was not the strongest room classifier for every dataset, but provided a common auditable framework; independent validation remains outstanding.
