# 5. Results

Writing status: write progressively as final outputs become stable.

This chapter should present results objectively before interpretation. Use figures and tables whenever they make the result easier to understand.

The results should follow the project progression but should be weighted by maturity and importance. Early visualisation and AA002 results should be concise and used to explain why the project moved toward raw RSSI and movement-aware methods. Home_X001 method development and labelled-data evaluation should receive more detailed figures, tables, and quantitative comparison because they represent the deeper final stages of the project.

## 5.1 Overview of Results

TODO: Briefly introduce the results sequence:

- early annotation and visualisation outputs;
- AA002 raw-data RSSI and movement experiments;
- Home_X001 no-reference two-person co-presence and algorithm comparison;
- labelled-data reference evaluation;
- hybrid method exploratory result.

Suggested emphasis:

| Result section | Emphasis | Notes |
|---|---|---|
| Early visualisation | Low to moderate | Include one or two representative outputs only |
| AA002 exploration | Moderate | Use to explain agreement terminology and low-motion insight |
| Home_X001 no-reference analysis | High | Main two-person co-presence and method-development evidence |
| Labelled-data evaluation | High | Main quantitative evaluation evidence |
| Hybrid exploratory result | Moderate | Important as a final test, but report honestly if it does not improve 4b |

## 5.2 Early Location and Activity Visualisation

Candidate outputs:

- `Results/A001/AA001_AB001_copresence_heatmap.png`
- `Results/A001/AA001_AB001_copresence_ratio.png`
- `Results/A001/AA001_activity_location_10min.gif`
- `Results/A002/AA002_activity_location_10min_compare_2023-07-17_first_frame.png`

TODO: Add one concise figure and explain how it motivated later raw-data analysis.

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

## 5.6 Low-Motion RSSI Clustering and Signal Stability

Candidate figures:

![Low-motion cluster model selection](../../Results/X001/ForthPhase/X001_forthphase_low_motion_cluster_model_selection.png)

![Low-motion cluster RSSI profile heatmap](../../Results/X001/ForthPhase/X001_forthphase_low_motion_cluster_rssi_profile_heatmap.png)

![RSSI evidence and signal stability summary](../../Results/FifthPhase/RSSI_evidence_signal_stability_summary.png)

Candidate table:

| Method | Role/dataset | Selected k | Dominant locations | Key finding |
|---|---|---:|---|---|
| TODO | TODO | TODO | TODO | TODO |

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

## 5.8 Hybrid 4b and 4c Exploratory Result

Candidate figure:

![Hybrid vs 4b and 4c metrics](../../Results/FifthPhase/Point1_5/labelled_hybrid_vs_4b_4c_metrics.png)

Candidate table:

| Dataset | 4b balanced accuracy | Hybrid balanced accuracy | Override windows |
|---|---:|---:|---:|
| TODO | TODO | TODO | TODO |

## TODO Later

- Replace TODO values with final CSV-derived numbers.
- Choose only the strongest figures for the main report and move extra figures to appendices.
- Ensure every figure and table has a numbered caption in the final compiled report.
- Avoid over-interpreting results in this chapter; save interpretation for Discussion.
- Avoid giving all stages equal space; let later and more mature analyses carry the main evidence.
