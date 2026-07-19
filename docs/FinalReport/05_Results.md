# 5. Results

This chapter presents the results of the unified movement-supported RSSI pipeline and compares it with earlier dataset-specific methods where those comparisons are informative. The purpose is not to show a chronological list of project phases. Instead, the results are organised around the final method: dataset capability, cross-dataset pipeline behaviour, correction provenance, reference-label agreement, dataset-specific challenge cases, and the tradeoff between generality and dataset-specific performance.

Unless independent reference labels are available, results are descriptive. Reduced transitions, smoother sleep-room timelines, or plausible co-presence summaries are treated as evidence of stability and interpretability, not proof of true room location.

## 5.1 Dataset Scope and Pipeline Audit

The unified pipeline processed 13 participant-sessions from ten collections. Across these sessions, the pipeline analysed 25,513 five-minute windows, equivalent to approximately 2,126 hours of recorded time. The full run produced no pipeline failures. Two collections were excluded because the required raw inputs were not available.

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

The excluded datasets are shown in Table 5.1. These are input-capability exclusions, not unresolved algorithm outputs.

**Table 5.1. Excluded datasets and reasons.**

| Collection | Reason |
|---|---|
| Home_A001 | Annotation-only; no parseable raw wearable sensor and beacon streams |
| KM_DEC_PANAPT | Only encrypted or unexported `SAMPLES.DAT` is available; no parseable sensor CSV |

The distinction between exclusion and unresolved state is important. `Excluded` means that the pipeline could not construct the required inputs. By contrast, `sleep_unresolved`, inactive pressure, or `Unknown` intervals are valid outputs when inputs exist but evidence is insufficient.

## 5.2 Overall Unified Pipeline Results

Table 5.2 summarises the session-level outputs. The same five-minute schema and evidence rules were applied across all parseable sessions.

**Table 5.2. Cross-dataset unified pipeline summary.**

| Collection / session | Movement | K | Main sleep | Probable away | Changed windows | Coverage raw -> corrected | Transitions raw -> corrected |
|---|---|---:|---|---:|---:|---:|---:|
| Home_A002 / AA002 | ACC | 2 | unresolved | 13 | 0 | 80.4% -> 80.4% | 157 -> 157 |
| Home_A002 / AB002 | Step | 2 | unresolved | 16 | 1 | 89.3% -> 89.3% | 194 -> 194 |
| EF-001 | ACC | 2 | 11 episodes | 6 | 187 | 68.4% -> 68.4% | 693 -> 556 |
| EF-002 | ACC | 2 | 12 episodes | 23 | 67 | 81.5% -> 82.9% | 543 -> 513 |
| DH Paris | Step | 2 | 5 episodes | 34 | 45 | 62.4% -> 62.4% | 267 -> 253 |
| DH PanoH | Step | 2 | 3 episodes | 3 | 17 | 69.6% -> 69.6% | 59 -> 59 |
| DH Strad | Step | 2 | unresolved | 27 | 9 | 69.9% -> 69.9% | 136 -> 122 |
| KM Mal | ACC | 3 | 4 episodes | 4 | 54 | 69.6% -> 69.6% | 135 -> 78 |
| KM PanH Nov22 | ACC | 2 | 6 episodes | 8 | 74 | 72.0% -> 72.5% | 156 -> 111 |
| KM PanH Nov28 | ACC | 3 | unresolved | 3 | 7 | 84.7% -> 84.7% | 55 -> 51 |
| Home_X001 / Left wrist | ACC | 2 | 7 episodes | 8 | 85 | 62.0% -> 62.0% | 346 -> 284 |
| Home_X001 / Right wrist | ACC | 2 | 10 episodes | 10 | 26 | 86.6% -> 86.6% | 495 -> 470 |
| NewData80h | ACC | 2 | 3 episodes | 3 | 7 | 88.2% -> 88.2% | 117 -> 113 |

Across all sessions, 579 five-minute windows changed from the raw strongest-RSSI room. Raw observed room transitions decreased from 3,353 to 2,961, a reduction of 392 transitions. Weighted room coverage changed only slightly, from 76.48% to 76.70%, because the awake branch does not fill missing RSSI. Newly covered room windows were rare and came only from evidence-supported sleep-gap filling.

The unresolved cases are part of the result. AA002 and AB002 had resolved movement models but unresolved sleep or Bedroom evidence. DH Strad and KM PanH Nov28 also remained sleep-unresolved because their candidate duration distributions did not meet the repeated-evidence rules. These failures show the intended conservative behaviour of the pipeline.

## 5.3 State Hierarchy and Correction Provenance

The pipeline changed rooms through several mechanisms: sleep episode-dominant correction, two-sided sleep-gap filling, awake movement-adaptive RSSI, and optional pressure-floor constraint. These mechanisms should not be interpreted as a single smoothing operation.

Two-sided sleep-gap filling was rare. Only 57 five-minute windows were filled across the full run: 51 in EF-002 and six in KM PanH Nov22. The remaining missing RSSI windows stayed missing. This is consistent with the methodological rule that awake gaps are never filled and sleep gaps require two-sided local room support.

Transition reduction was strongest in sessions with resolved sleep and strong room support. KM Mal reduced transitions from 135 to 78, EF-001 from 693 to 556, KM PanH Nov22 from 156 to 111, and Home_X001 Left wrist from 346 to 284. However, transition reduction is not itself an accuracy metric. It is useful stability evidence only when interpreted alongside coverage, correction source, RSSI evidence, and reference labels where available.

EF-001 and EF-002 illustrate two different RSSI failure modes and were important in shaping the final state hierarchy. EF-001 mainly involved implausible room switching during long low-motion periods, so the pipeline changed observed sleep windows to the episode-dominant room when the 60% dominance rule passed. EF-002 involved RSSI gaps during sleep, so the pipeline filled only short gaps supported by both preceding and following 30-minute contexts. The near-whole-night unsupported gap in EF-002 remained missing.

Figure 5.1 and Figure 5.2 show representative unified outputs for these two cases.

![Figure 5.1. EF-001 raw and corrected timeline](../../Results/EighthPhase/EF-001/EF-001/EF-001_2026/raw_vs_corrected_timeline.png)

**Figure 5.1. EF-001 raw and corrected timeline. The unified pipeline reduces implausible night-time switching during supported low-motion episodes while leaving unsupported evidence unchanged.**

![Figure 5.2. EF-002 raw and corrected timeline](../../Results/EighthPhase/EF-002/EF-002/EF-002_2026/raw_vs_corrected_timeline.png)

**Figure 5.2. EF-002 raw and corrected timeline. Short sleep gaps with two-sided room context are recovered, while the unsupported near-whole-night RSSI absence remains missing.**

## 5.4 Reference-Label Agreement

Four labelled collections were evaluated after prediction: DH Paris, DH PanoH, DH Strad, and KM Mal. Results are described as agreement with reference annotations rather than ground-truth accuracy. Table 5.3 reports both covered-window metrics and end-to-end agreement so that coverage changes are visible.

**Table 5.3. Reference-label agreement before and after unified correction.**

| Dataset | Coverage raw -> corrected | Conditional accuracy raw -> corrected | Balanced accuracy raw -> corrected | Macro-F1 raw -> corrected | End-to-end agreement raw -> corrected |
|---|---:|---:|---:|---:|---:|
| DH Paris | 62.8% -> 96.6% | 44.7% -> 64.1% | 48.4% -> 67.0% | 34.2% -> 47.9% | 28.1% -> 61.9% |
| DH PanoH | 62.7% -> 99.0% | 89.7% -> 90.5% | 54.6% -> 66.0% | 51.4% -> 64.2% | 56.3% -> 89.6% |
| DH Strad | 69.9% -> 93.4% | 82.9% -> 87.8% | 49.8% -> 69.2% | 45.7% -> 65.9% | 57.9% -> 82.0% |
| KM Mal | 66.3% -> 90.9% | 86.2% -> 94.4% | 60.2% -> 81.2% | 49.0% -> 77.2% | 57.1% -> 85.8% |

End-to-end agreement improved in all four labelled datasets. The mechanism differed by dataset. In the three DH collections, much of the gain came from representing `Probable away` and matching reference `Out` periods rather than from room smoothing alone. KM Mal showed stronger room-level correction, with four room-supported sleep episodes and 54 changed windows.

The comparison with earlier dataset-specific methods shows the cost of unification. The earlier 4b or fixed-window methods sometimes achieved higher room-level metrics because they were tuned to a narrower objective. Table 5.4 summarises the closest earlier comparison.

**Table 5.4. Earlier dataset-specific labelled results compared with the unified pipeline.**

| Dataset | Earlier strongest method and metric | Unified corrected conditional accuracy / balanced accuracy | Unified end-to-end agreement |
|---|---:|---:|---:|
| DH Paris | 4b: 0.889 accuracy / 0.766 balanced accuracy | 0.641 / 0.670 | 0.619 |
| DH PanoH | Raw 30-min: 0.881 accuracy / 0.742 balanced accuracy; raw 5-min accuracy 0.931 | 0.905 / 0.660 | 0.896 |
| DH Strad | 4b: 0.945 accuracy / 0.875 balanced accuracy | 0.878 / 0.692 | 0.820 |
| KM Mal | 4b accuracy 0.930; raw 15-min best balanced accuracy 0.841 | 0.944 / 0.812 | 0.858 |

These comparisons show that the unified pipeline is not always the best dataset-specific room classifier. Its advantage is broader: it reports room, behaviour, occupancy, missingness, correction provenance, and unresolved states in one common framework.

![Figure 5.3. DH PanoH reference confusion matrices](../../Results/EighthPhase/Labelled_DH_PanoH/DH/DH_PanoH_2023/reference_confusion_matrix.png)

**Figure 5.3. DH PanoH raw and corrected reference confusion matrices. The corrected output reaches high end-to-end agreement, while conditional and balanced metrics are reported separately to avoid hiding missingness or class imbalance.**

![Figure 5.4. KM Mal reference confusion matrices](../../Results/EighthPhase/Labelled_KM_Mal/KM/KM_Mal_2023/reference_confusion_matrix.png)

**Figure 5.4. KM Mal raw and corrected reference confusion matrices. KM Mal provides the strongest labelled example of the complete state hierarchy, but the borderline away rule means this remains development-set evidence rather than independent validation.**

## 5.5 Dataset-Specific Challenge Results

The unified pipeline was also assessed against the original dataset-specific questions that motivated earlier phases. This comparison is useful because a general method should preserve the main scientific answer where possible, while making clear what is lost relative to specialised scripts.

**EF-001: implausible night-time switching.** The bespoke Seventh Phase method used an EF-specific ACC threshold and reduced overall transitions from 719 to 417, with low-motion transitions reduced from 252 to 4. The unified pipeline selected its own ACC threshold, selected 11 main-sleep episodes, and reduced transitions from 693 to 556. The improvement is smaller because the unified rule requires 60% room dominance and does not force weak episodes. The central finding survives: much night-time switching was not movement-supported.

**EF-002: sleep-related RSSI occlusion.** The bespoke analysis filled 38 five-minute Bedroom-supported gap windows and left the roughly 700-minute unsupported gap missing. The unified pipeline filled 51 five-minute windows using the same two-sided context principle and again left the near-whole-night gap missing. It also applied the common episode and awake correction rules, reducing transitions from 543 to 513.

**NewData80h: pressure-floor constraint.** The bespoke Sixth Phase pressure analysis changed 54 windows and reduced raw RSSI floor switches from 75 to 30. The unified pressure branch automatically recovered the documented two-floor beacon grouping, but changed only five strongest-beacon windows by pressure and seven windows overall. This difference is expected: the unified branch requires high pressure confidence and movement support. It generalises the conservative floor constraint, but does not replace the specialised high-resolution stair-event and mobility-metric module.

![Figure 5.5. NewData80h raw and corrected timeline](../../Results/EighthPhase/NewData80h/559662/559662_80h/raw_vs_corrected_timeline.png)

**Figure 5.5. NewData80h raw and corrected timeline. The unified pressure branch recovers the two-floor grouping but changes only a small number of high-confidence windows, acting as a conservative constraint rather than a broad pressure override.**

**Home_X001: two-person no-reference co-presence and pressure null result.** Home_X001 remains descriptive because no independent room labels are available. Corrected same-room time changed from 33.25 to 32.67 hours. The method added 41 same-room windows and removed 48, showing that correction did not simply increase co-presence. The pressure audit found visually stable K=2 candidates, but their separations of approximately 0.231 and 0.233 hPa and silhouettes of 0.720 and 0.685 failed the floor-scale gate. The K=1 null outcome therefore left pressure inactive, which is consistent with the known single-floor context.

**Home_A002: movement evidence without enough room-correction evidence.** AA002 and AB002 both resolved movement states, but sleep and Bedroom evidence remained unresolved. AA002 changed no room windows and AB002 changed one. This is a useful negative result: movement detection alone is not sufficient to justify spatial correction.

## 5.6 Generalisability Versus Dataset-Specific Performance

The unified pipeline generalised in the sense that the same schema and evidence hierarchy ran across all 13 parseable sessions without failure. It handled ACC and step-based movement, resolved sleep in nine sessions, inferred probable away in all processed sessions, and produced comparable room, behaviour, occupancy, and correction-provenance outputs.

The strongest generalisation was observed when movement or local room context directly contradicted implausible RSSI behaviour. EF-001 and EF-002 are especially important because the final sleep-room and sleep-gap safeguards were partly shaped by the problems they exposed. Together with KM Mal and KM PanH Nov22, they show that the same state hierarchy can reduce unsupported night-time switching or recover short supported RSSI gaps. The pressure branch also generalised partially: it recovered the two-floor grouping in NewData80h while correctly selecting K=1 for Home_X001.

The method did not generalise cleanly in every respect. A single numerical movement threshold did not transfer across recordings, so thresholds were fitted per session using the common clustering rule. Short recordings or singleton duration classes remained sleep-unresolved. Step absence was useful but weaker than ACC because zero steps can indicate quiet sitting, non-wear, or a stationary device. The unified pipeline also underperformed earlier dataset-tuned room classifiers on several labelled metrics.

This tradeoff is central to the final result. A dataset-specific method can be more accurate for one narrow room-classification task. The unified pipeline sacrifices some of that specialised performance to gain auditability, common state definitions, explicit missingness, unresolved outputs, optional pressure and co-presence branches, and comparable cross-dataset reporting. For this project, that tradeoff is valuable because the aim is not only to assign rooms, but to translate wearable and environmental beacon data into interpretable summaries of patient lived experience.

## TODO Later

- Select the final subset of figures for the submitted report and move extra diagnostics to the appendices.
- Add final figure and table numbering after the report format is fixed.
- Re-check all numerical values after the last full Eighth Phase run.
- Align the final Discussion with the generalisability and dataset-specific performance tradeoff reported here.
