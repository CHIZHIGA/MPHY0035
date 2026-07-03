# 4. Methodology

Writing status: reorganised draft based on the 2026-06-29 supervisor feedback. Sections 4.1-4.5 are drafted; Section 4.6 remains partly reserved for the final labelled-data evaluation and hybrid method details.

This chapter describes the methods used to combine RSSI-derived room-level location, wearable movement data, and co-presence visualisation. The work developed over several project stages, but the chapter is organised by methodological logic rather than by work-log chronology. This structure follows the background and objectives: preprocessing multi-source sensor data, establishing interpretable RSSI baselines, adding movement-aware location estimation, exploring RSSI-vector methods, extending the analysis to co-presence, and evaluating methods according to the available reference evidence.

## 4.1 Data Sources and Preprocessing

The project used several related data sources across its development. Early work used existing annotation and activity files to establish how room-level behaviour could be visualised. Subsequent analyses used raw RSSI, step-count, and accelerometer data from wearable devices. Home_X001 provided a two-person no-reference dataset for SUBJECT/STUDY_PARTNER co-presence analysis. Later labelled datasets were introduced to support stronger reference-label evaluation.

The first preprocessing task was timestamp alignment. Annotation intervals, RSSI readings, step-count records, and accelerometer samples were converted into common time representations so that location and movement features could be compared within the same windows. For annotation-based visualisation, room labels were mapped onto fixed visualisation intervals using the label with the largest overlap or the dominant label within a window. For raw-data analysis, RSSI and movement features were calculated over fixed or adaptive time windows.

Metadata were used to map beacon identifiers to rooms where valid mappings were available. This mapping was essential because the raw RSSI files contained beacon identifiers rather than direct room labels. Beacons without valid room mappings were retained as unmapped or external signal sources rather than being forced into a room label. This conservative handling reduced the risk of creating false indoor room estimates.

RSSI preprocessing extracted beacon readings from the main RSSI fields and, where available, additional simultaneous beacon readings stored in auxiliary fields. For each time window, RSSI features included the strongest beacon, the strongest mapped location, the total RSSI sample count, the proportion of samples supporting the strongest beacon, and the gap between the strongest and second-strongest beacon. These features were used both for localisation and for assessing signal evidence.

Movement preprocessing used both step count and accelerometer-derived features. Cumulative step-count data were converted into step increments within time windows. Accelerometer data were summarised using acceleration magnitude:

```text
sqrt(acc_x^2 + acc_y^2 + acc_z^2)
```

The mean and variability of acceleration magnitude provided movement-intensity descriptors beyond step count alone. These movement features were not used as direct room labels; instead, they provided context for whether an RSSI estimate was likely to represent a stable location or a transition period.

The overall annotation-based visualisation workflow is summarised in Figure 4.1, the AA002 raw-data processing workflow is summarised in Figure 4.2, and the Home_X001 two-person alignment workflow is summarised in Figure 4.3. These figures show the development from processed annotation visualisation to raw multi-source sensor alignment.

![Figure 4.1. Annotation-based visualisation workflow](figures/figure_4_1_annotation_workflow.svg)

**Figure 4.1. Annotation-based visualisation workflow. Existing room annotations and activity outputs were aligned to regular time windows and converted into location timelines, simplified floor-plan displays, and early co-presence visualisations.**

![Figure 4.2. AA002 raw RSSI and movement processing workflow](figures/figure_4_2_aa002_processing.svg)

**Figure 4.2. Raw-data processing workflow for the AA002 exploratory analysis. RSSI readings were converted into windowed beacon features, movement signals were summarised from step count and accelerometer data, and algorithm outputs were compared with existing annotations as agreement rather than ground-truth accuracy.**

![Figure 4.3. Home_X001 data availability and two-person alignment](figures/figure_4_3_x001_alignment.svg)

**Figure 4.3. Home_X001 preprocessing and two-person alignment. Device metadata were used to identify SUBJECT and STUDY_PARTNER, the overlapping recording period was selected, and RSSI and movement features were aligned onto a shared timeline for descriptive no-reference analysis.**

## 4.2 Baseline RSSI-Derived Room Localisation

The baseline localisation approach used RSSI as the spatial signal. This followed the nearest-beacon or strongest-beacon principle: RSSI readings were grouped into time windows, the strongest beacon or strongest mapped location was identified, and the corresponding room label was assigned as the room-level estimate for that window.

This baseline was used in two ways. First, early visualisation work used already processed annotation or location outputs to establish how room-level behaviour could be displayed. Second, raw-data experiments recalculated location directly from RSSI features. The raw-data version was more important methodologically because it allowed RSSI-derived location estimates to be compared across different window lengths and later combined with movement features.

Fixed-window RSSI methods were tested using window lengths such as 5 minutes, 10 minutes, 15 minutes, and 30 minutes depending on the dataset. Shorter windows were more responsive to rapid changes but more sensitive to RSSI noise. Longer windows produced smoother location estimates but could hide short room transitions. This trade-off made fixed-window RSSI a useful baseline for evaluating movement-aware methods.

For each window, the method calculated not only the strongest mapped location but also supporting signal evidence. The main supporting features were RSSI sample count, strongest-beacon proportion, and strongest-second RSSI gap. These features helped distinguish windows with clear spatial evidence from windows where the RSSI signal was weak or ambiguous.

The fixed-window RSSI baseline workflow is shown in Figure 4.4.

![Figure 4.4. Fixed-window RSSI baseline method](figures/figure_4_5_fixed_rssi.svg)

**Figure 4.4. Fixed-window RSSI localisation baseline. RSSI samples were grouped into fixed time windows, the strongest mapped beacon location was selected for each participant, and the resulting room estimates were used to derive individual location and co-presence timelines.**

## 4.3 Movement-Aware Location Estimation

Movement-aware localisation was developed to make RSSI-derived location estimates more interpretable. The central idea was that movement provides temporal context for RSSI. Low movement suggests a stable period where longer RSSI windows may be appropriate, while higher movement may indicate room transitions where shorter windows or lower confidence are more appropriate.

AA002 was first used to explore this idea. Step count was used to identify low-motion windows, and RSSI location estimates were calculated for windows below selected step thresholds. This tested whether low-motion periods produced more stable RSSI signatures. The same dataset was also used to compare adaptive RSSI window rules, where the selected RSSI window length depended on movement and RSSI stability features.

RSSI stability features were included because movement alone is not sufficient to guarantee a reliable location estimate. A participant may be still while the RSSI signal remains ambiguous, for example because of beacon placement, body occlusion, or missing detections. Therefore, the adaptive-window experiments considered features such as the proportion of samples with the same strongest beacon and the RSSI gap between the strongest and second-strongest beacon.

The main movement-aware method later used in Home_X001 was the hierarchical step-adaptive RSSI algorithm. The cumulative step-count data were first regularised onto a 1-minute timeline, then step increments were aggregated into 1-minute, 5-minute, 10-minute, and 30-minute windows. For each timestamp, the method selected the longest RSSI window supported by low step count:

```text
if 30min steps <= threshold:
    use 30min RSSI
elif 10min steps <= threshold:
    use 10min RSSI
elif 5min steps <= threshold:
    use 5min RSSI
else:
    use 1min RSSI
```

The selected default threshold was:

```text
threshold = 10 steps
```

This threshold was interpreted as a low-motion stability threshold rather than as a strict stationary definition. RSSI was not interpolated across no-detection periods. If the selected RSSI window contained no RSSI evidence, the location estimate remained away or unmapped. This conservative rule avoided smoothing no-detection periods into artificial room estimates.

The hierarchical step-adaptive window selection rule is illustrated in Figure 4.5.

![Figure 4.5. Hierarchical step-adaptive RSSI window selection](figures/figure_4_6_step_adaptive.svg)

**Figure 4.5. Hierarchical step-adaptive RSSI method. Step count was used to select the RSSI window length, with longer windows used during low-motion periods and shorter windows used during more active periods; RSSI remained the spatial signal used to assign the room estimate.**

## 4.4 RSSI Vector and Low-Motion Clustering

In addition to strongest-beacon methods, the project explored whether RSSI vectors could capture repeatable signal states. A vector-based representation uses the pattern of RSSI evidence across multiple beacons rather than only the strongest beacon. This can preserve more spatial information, but it may also be more sensitive to missing values and signal instability.

Low-motion RSSI clustering was developed as an exploratory method. The method selected training windows where movement was low, using the criterion:

```text
30min steps <= 10
```

For these windows, RSSI vectors were constructed from active metadata-mapped home beacons. External, inactive, or unmapped beacons were excluded from the clustering features. Missing beacon values within valid RSSI windows were filled with a low RSSI value so that each window had a complete vector representation.

KMeans clustering was then fitted to the low-motion RSSI vectors. Candidate cluster numbers were compared, and the selected model balanced silhouette score with cluster-size stability. Each cluster was interpreted using its dominant beacon or dominant mapped location. The fitted model could then be applied to windows with RSSI evidence, while no-RSSI windows remained unmapped.

This method was treated as exploratory. A cluster label was interpreted as a repeated RSSI signal state, not as an independently verified room label. This distinction is important because a cluster may be dominated by one room-like RSSI pattern even when the current strongest-beacon evidence is ambiguous. For this reason, clustering was used to investigate RSSI structure and possible support for movement-aware methods, rather than as the primary room-level localisation method.

The low-motion RSSI clustering workflow is summarised in Figure 4.6.

![Figure 4.6. Low-motion RSSI clustering workflow](figures/figure_4_7_clustering_workflow.svg)

**Figure 4.6. Low-motion RSSI clustering workflow. Low-motion windows were used to train RSSI-vector clusters, which were then interpreted as repeated signal states and applied to windows with RSSI evidence while no-RSSI periods remained unmapped.**

## 4.5 Co-Presence and Integrated Visualisation

Co-presence analysis extended individual room-level localisation to two-person home behaviour. This was particularly important for Home_X001, where metadata identified the two device folders as SUBJECT and STUDY_PARTNER. The goal was to describe whether the two people appeared to be in the same estimated room, in different estimated rooms, or whether one or both were away or unmapped.

For each time window, each person was classified as estimated in home if a valid mapped room location was available. If the strongest RSSI evidence was unmapped, external, or missing, that person was treated conservatively as away or unmapped. The two individual states were then combined into the five co-presence categories defined in Table 4.1.

**Table 4.1. Co-presence state definitions used for Home_X001 no-reference analysis.**

| Co-presence state | Definition |
|---|---|
| Same estimated location | Both people were estimated in home and assigned to the same mapped room |
| Different estimated locations | Both people were estimated in home but assigned to different mapped rooms |
| SUBJECT home only | SUBJECT had a mapped home location and STUDY_PARTNER was away or unmapped |
| STUDY_PARTNER home only | STUDY_PARTNER had a mapped home location and SUBJECT was away or unmapped |
| Both away or unmapped | Neither person had a mapped home location |

The co-presence classification logic is shown in Figure 4.7. These categories were used consistently across fixed-window RSSI, step-adaptive RSSI, clustering, and later hybrid analyses.

![Figure 4.7. Co-presence classification logic](figures/figure_4_4_copresence_logic.svg)

**Figure 4.7. Co-presence classification logic for Home_X001. Individual RSSI-derived location states for SUBJECT and STUDY_PARTNER were combined into five descriptive co-presence categories used consistently across algorithms.**

Integrated visualisations were then created to inspect individual location estimates, co-presence states, and movement context on the same time axis. Multi-day figures displayed separate aligned rows for co-presence, SUBJECT location, and STUDY_PARTNER location. Location was encoded by colour, while step-count-derived activity was represented by line width. Later figures used a midday-to-midday layout so that overnight periods were not split at midnight, making implausible night-time room switching easier to identify.

The integrated timeline layout is shown schematically in Figure 4.8.

![Figure 4.8. Integrated multi-day timeline design](figures/figure_4_8_timeline_design.svg)

**Figure 4.8. Integrated multi-day timeline design for no-reference algorithm comparison. Co-presence, SUBJECT location, and STUDY_PARTNER location were displayed on aligned daily timelines, with colour encoding location state and line width providing movement context.**

## 4.6 Evaluation Strategy

Writing status: partly reserved for completion after the fifth phase is stable.

The evaluation strategy depended on the type of reference evidence available. For AA002, comparisons with `annotator.json` were treated as agreement with existing annotations, because the annotation file was not an independent manually verified ground-truth source. For Home_X001, there were no independent reference labels, so the analysis was descriptive and focused on RSSI-derived estimates, stability, transition frequency, co-presence summaries, pairwise agreement, and visual plausibility.

For labelled datasets with diary or reference location labels, stronger quantitative evaluation can be used. The final version of this section should describe the labelled dataset manifest, reference-label alignment, compared algorithms, and metrics including accuracy, balanced accuracy, confusion matrix, per-location recall, pairwise agreement, and positive/negative agreement.

TODO later:

- Complete the labelled-data evaluation description after the fifth phase is stable.
- Add the final hybrid 4b + 4c method if it remains in the final report.
- Summarise validation checks, including non-empty output checks, timestamp checks, metadata role checks, and co-presence duration checks.
- Clarify final terminology for "accuracy", "agreement with existing annotations", and "RSSI-derived estimates".
