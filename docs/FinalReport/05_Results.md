# 5. Results

Writing status: write progressively as final outputs become stable.

This chapter should present results objectively before interpretation. Use figures and tables whenever they make the result easier to understand. Each results section should make clear which project objective it supports, while leaving the deeper interpretation of why the result matters to Chapter 6.

The results should follow the project progression but should be weighted by maturity and importance. Early visualisation and AA002 results should be concise and used to explain why the project moved toward raw RSSI and movement-aware methods. Home_X001 method development and labelled-data evaluation should receive more detailed figures, tables, and quantitative comparison because they represent the deeper final stages of the project. The Sixth Phase pressure-floor-aware analysis should be presented as the final extension from location estimation to interpretable behavioural metrics.

## 5.1 Overview of Results

TODO: Briefly introduce the results sequence:

- early annotation and visualisation outputs;
- AA002 raw-data RSSI and movement experiments;
- Home_X001 no-reference two-person co-presence and algorithm comparison;
- labelled-data reference evaluation;
- hybrid method exploratory result;
- pressure-floor-aware localisation and behavioural mobility metrics from the 80-hour two-floor dataset.

Suggested emphasis:

| Result section | Emphasis | Notes |
|---|---|---|
| Early visualisation | Low to moderate | Include one or two representative outputs only |
| AA002 exploration | Moderate | Use to explain agreement terminology and low-motion insight |
| Home_X001 no-reference analysis | High | Main two-person co-presence and method-development evidence |
| Labelled-data evaluation | High | Main quantitative evaluation evidence |
| Hybrid exploratory result | Moderate | Important as a final test, but report honestly if it does not improve 4b |
| Sixth Phase pressure-floor metrics | High | Shows the project moving beyond location labels to behavioural summaries |

The results should be connected to the objectives as follows:

| Objective | Evidence expected in Results | Main results sections | Interpretation deferred to Discussion |
|---|---|---|---|
| Objective 1: Preprocessing and alignment | Data availability summaries, aligned RSSI/activity/pressure/reference-label timelines, usable shared periods | 5.2, 5.4, 5.7, 5.9 | Whether the pipeline was sufficient to support reproducible cross-dataset analysis |
| Objective 2: RSSI-derived localisation baselines | Fixed-window or nearest/strongest-beacon outputs, agreement or labelled metrics, transition behaviour | 5.3, 5.5, 5.7 | Whether simple RSSI baselines are strong enough to act as credible reference methods |
| Objective 3: Movement-aware and floor-aware localisation | Low-motion threshold analysis, step-adaptive window choices, pressure-derived floor timelines, comparison with fixed RSSI methods | 5.3, 5.5, 5.6, 5.8, 5.9 | Whether movement and pressure information improves, stabilises, or helps interpret RSSI-derived estimates |
| Objective 4: Behavioural summaries | Co-presence states, stair transitions, sleep-location candidates, active room-transition rates | 5.2, 5.4, 5.5, 5.9 | Whether location estimates can support useful lived-experience summaries rather than only pointwise location labels |
| Objective 5: Evaluation under different evidence levels | Existing-annotation agreement, no-reference descriptive checks, labelled-data metrics, plausibility assessment | 5.3, 5.4, 5.7, 5.8, 5.9 | How much confidence can be placed in each result, given the available reference evidence |

## 5.2 Early Location and Activity Visualisation

Candidate outputs:

- `Results/A001/AA001_AB001_copresence_heatmap.png`
- `Results/A001/AA001_AB001_copresence_ratio.png`
- `Results/A001/AA001_activity_location_10min.gif`
- `Results/A002/AA002_activity_location_10min_compare_2023-07-17_first_frame.png`

TODO: Add one concise figure and explain how it motivated later raw-data analysis.

Objective link: this section mainly supports Objective 4 by showing the desired form of spatial and co-presence outputs, and Objective 1 by demonstrating the need for reliable alignment between activity and location timelines.

## 5.3 AA002 RSSI and Movement Experiments

Candidate figures:

![AA002 RSSI representation comparison](../../Results/A002/AA002_rssi_representation_metrics_comparison.png)

![AA002 step-count low-motion threshold comparison](../../Results/A002/AA002_step_low_motion_threshold_comparison.png)

![AA002 adaptive step-window location comparison](../../Results/A002/AA002_adaptive_step_window_location_comparison.png)

Candidate table:

| Method | Agreement/accuracy metric | Balanced metric | Interpretation |
|---|---:|---:|---|
| TODO | TODO | TODO | TODO |

Important wording:

- If using `annotator.json`, describe results as agreement with existing annotations, not true ground-truth accuracy.

Objective link: this section supports Objective 1 by testing aligned RSSI and movement data, Objective 2 by evaluating baseline RSSI representations, Objective 3 by motivating low-motion and adaptive-window methods, and Objective 5 by distinguishing annotation agreement from independent accuracy.

## 5.4 Home_X001 Data Availability and Two-Person Co-Presence

Candidate figures:

![Home_X001 data availability timeline](../../Results/X001/ThirdPhase/X001_data_availability_timeline.png)

![Home_X001 left/right movement comparison](../../Results/X001/ThirdPhase/X001_left_right_movement_comparison.png)

![Home_X001 co-presence summary](../../Results/X001/ForthPhase/X001_forthphase_copresence_summary.png)

Candidate table:

| Co-presence state | Hours | Percentage of shared time |
|---|---:|---:|
| Same estimated location | TODO | TODO |
| Different estimated locations | TODO | TODO |
| SUBJECT home only | TODO | TODO |
| STUDY_PARTNER home only | TODO | TODO |
| Both away or unmapped | TODO | TODO |

Objective link: this section supports Objective 1 by defining the usable shared observation period, Objective 4 by presenting estimated co-presence states, and Objective 5 by framing Home_X001 as descriptive no-reference evidence.

## 5.5 Fixed-Window and Step-Adaptive RSSI Methods

Candidate figures:

![Fixed RSSI window co-presence comparison](../../Results/X001/ForthPhase/X001_forthphase_fixed_rssi_window_copresence_comparison.png)

![Step-adaptive RSSI window distribution](../../Results/X001/ForthPhase/X001_forthphase_hierarchical_step_adaptive_window_distribution.png)

![Step-adaptive RSSI comparison](../../Results/X001/ForthPhase/X001_forthphase_hierarchical_step_adaptive_comparison.png)

Candidate table:

| Method | Same estimated location | Different estimated locations | Mean RSSI confidence | Location transitions |
|---|---:|---:|---:|---:|
| Fixed RSSI 5min | TODO | TODO | TODO | TODO |
| Fixed RSSI 10min | TODO | TODO | TODO | TODO |
| Fixed RSSI 30min | TODO | TODO | TODO | TODO |
| Step-adaptive RSSI | TODO | TODO | TODO | TODO |

Objective link: this section supports Objective 2 through fixed-window RSSI baselines, Objective 3 through movement-aware window selection, and Objective 4 through the effect of method choice on two-person co-presence summaries.

## 5.6 Low-Motion RSSI Clustering and Signal Stability

Candidate figures:

![Low-motion cluster model selection](../../Results/X001/ForthPhase/X001_forthphase_low_motion_cluster_model_selection.png)

![Low-motion cluster RSSI profile heatmap](../../Results/X001/ForthPhase/X001_forthphase_low_motion_cluster_rssi_profile_heatmap.png)

![RSSI evidence and signal stability summary](../../Results/FifthPhase/RSSI_evidence_signal_stability_summary.png)

Candidate table:

| Method | Role/dataset | Selected k | Dominant locations | Key finding |
|---|---|---:|---|---|
| TODO | TODO | TODO | TODO | TODO |

Objective link: this section supports Objective 3 by testing whether low-motion RSSI vectors provide stable signal states, and Objective 5 by showing why clustering outputs require cautious interpretation unless independent labels are available.

## 5.7 Labelled-Data Algorithm Evaluation

Candidate figures:

![Labelled algorithm metrics summary](../../Results/FifthPhase/Point1_5/labelled_algorithm_metrics_summary.png)

![Balanced accuracy by dataset](../../Results/FifthPhase/Point1_5/labelled_algorithm_balanced_accuracy_by_dataset.png)

![Per-location recall heatmap](../../Results/FifthPhase/Point1_5/labelled_per_location_recall_heatmap.png)

Candidate table:

| Dataset | Best method by balanced accuracy | Accuracy | Balanced accuracy |
|---|---|---:|---:|
| DH Paris | TODO | TODO | TODO |
| DH PanoH | TODO | TODO | TODO |
| DH Strad | TODO | TODO | TODO |
| KM Mal | TODO | TODO | TODO |

Objective link: this section supports Objective 2 and Objective 3 through quantitative method comparison, and Objective 5 by using reference-label metrics where stronger labels are available.

## 5.8 Hybrid 4b and 4c Exploratory Result

Candidate figure:

![Hybrid vs 4b and 4c metrics](../../Results/FifthPhase/Point1_5/labelled_hybrid_vs_4b_4c_metrics.png)

Candidate table:

| Dataset | 4b balanced accuracy | Hybrid balanced accuracy | Override windows |
|---|---:|---:|---:|
| TODO | TODO | TODO | TODO |

Objective link: this section supports Objective 3 by testing whether clustering can improve or support the movement-aware method, and Objective 5 by reporting the hybrid result honestly even if it does not outperform the simpler method.

## 5.9 Pressure-Floor-Aware Localisation and Behavioural Metrics

Candidate figures:

![Cleaned pressure and floor timeline](../../Results/SixthPhase/NewData80h/new80h_pressure_cleaned_and_floor_timeline_aligned.png)

![ACC support for pressure-derived floor shifts](../../Results/SixthPhase/NewData80h/new80h_pressure_floor_acc_support_timeline.png)

![Raw versus pressure-floor-aware RSSI timeline](../../Results/SixthPhase/NewData80h/new80h_raw_vs_pressure_floor_bruteforce_rssi_two_line_timeline.png)

![Pressure-derived stair events](../../Results/SixthPhase/QuantifiedMetrics/new80h_stair_events_timeline.png)

![Low-motion sleep-location candidate timeline](../../Results/SixthPhase/QuantifiedMetrics/new80h_sleep_candidate_timeline.png)

![ACC-supported room transitions](../../Results/SixthPhase/QuantifiedMetrics/new80h_room_transition_acc_support_timeline.png)

Candidate pressure/floor table:

| Metric | Value | Interpretation |
|---|---:|---|
| Pressure-inferred 1F time | TODO | TODO |
| Pressure-inferred 2F time | TODO | TODO |
| Pressure-derived floor shifts | TODO | TODO |
| ACC-supported floor shifts | TODO | TODO |
| Raw RSSI cross-floor switches | TODO | TODO |
| Pressure-floor-aware RSSI switches | TODO | TODO |

Candidate behavioural metrics table:

| Behavioural metric | Main result | Interpretation |
|---|---:|---|
| Stair-transition candidates | TODO | Pressure-derived ascent/descent candidates |
| Pressure-valid refined stair events | TODO | Candidate subset with plausible pressure ramp and duration |
| Mean ascent duration | TODO | Preliminary descriptive mobility metric |
| Mean descent duration | TODO | Preliminary descriptive mobility metric |
| Dominant sleep-location candidate beacon | TODO | Low-motion night-time long-stay candidate |
| ACC-supported room transitions per awake hour | TODO | Active-period room-transition rate |

Important wording:

- Treat pressure as the main floor-level signal, RSSI as the room or beacon proximity signal, and ACC as supporting movement evidence.
- Describe stair, sleep-location, and room-transition outputs as preliminary descriptive behavioural metrics, not independently verified clinical outcomes.
- Avoid claiming validated sleep or verified stair use unless independent labels become available.

Objective link: this section supports Objective 1 through pressure/RSSI/ACC alignment, Objective 3 through floor-aware sensor fusion, Objective 4 through behavioural metrics derived from location timelines, and Objective 5 through cautious no-reference interpretation.

## TODO Later

- Replace TODO values with final CSV-derived numbers.
- Choose only the strongest figures for the main report and move extra figures to appendices.
- Ensure every figure and table has a numbered caption in the final compiled report.
- Ensure each results subsection explicitly states which objective(s) it provides evidence for.
- Avoid over-interpreting results in this chapter; save interpretation for Discussion.
- Avoid giving all stages equal space; let later and more mature analyses carry the main evidence.
