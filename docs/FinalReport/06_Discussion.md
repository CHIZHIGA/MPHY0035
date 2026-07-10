# 6. Discussion

Writing status: partly stable, but should be finalised after Results.

This chapter should interpret the results and connect them back to the research questions, objectives, clinical context, and literature.

The discussion should recognise the whole project progression, but with increasing emphasis on the later stages. Early work should be discussed mainly as foundation and motivation. The most detailed interpretation should focus on the mature RSSI and movement-fusion methods, no-reference co-presence analysis, labelled-data evaluation, and the pressure-floor-aware extension from location estimates to behavioural metrics.

## 6.1 Objective-Based Interpretation Framework

The discussion should be organised around the five project objectives rather than only around the order in which analyses were completed. This ensures that each result is interpreted in relation to the scientific purpose of the project.

| Objective | Results to interpret | Interpretation question | Important caution |
|---|---|---|---|
| Objective 1: Preprocessing and alignment | Data availability, timestamp alignment, RSSI/activity/pressure/reference-label integration | Did the processing workflow create a reliable basis for comparing location, movement, floor context, and reference labels across datasets? | Missing data, shared-period restrictions, pressure artefacts, and metadata quality affect all downstream analyses |
| Objective 2: RSSI-derived localisation baselines | Nearest/strongest-beacon and fixed-window RSSI outputs | How well do transparent RSSI baselines perform, and what do they contribute relative to more complex BLE localisation methods in the literature? | Baselines may be strong, but RSSI remains noisy and environment-dependent |
| Objective 3: Movement-aware and floor-aware localisation | Low-motion analysis, step-adaptive RSSI, clustering, hybrid methods, pressure-derived floor context | Do movement and pressure information help interpret RSSI stability, transitions, window selection, or cross-floor ambiguity? | Movement and pressure should be treated as contextual support or constraints, not as direct room labels |
| Objective 4: Behavioural summaries | Home_X001 co-presence, stair transitions, sleep-location candidates, active room-transition rates | Do location estimates support meaningful higher-level descriptions of lived experience in the home? | Co-presence, sleep-location, and stair metrics remain estimated behaviours unless independently verified |
| Objective 5: Evaluation under different evidence levels | Existing-annotation agreement, no-reference checks, labelled-data metrics, plausibility assessment | What kind of confidence is justified for each dataset and method? | Agreement, descriptive plausibility, and reference-label accuracy are different levels of evidence |

## 6.2 Summary of Main Findings

TODO: Summarise the final findings after Results are fixed.

Likely findings:

- The project developed iteratively from annotation-based visualisation to raw-data localisation, two-person no-reference analysis, and labelled-data evaluation.
- Early floor-plan and co-presence visualisations were useful for defining what spatial behaviour outputs should communicate, but the later project focus moved toward raw-data RSSI and movement-based localisation.
- The AA002 work showed why existing annotations should be treated carefully and helped reframe early performance values as agreement rather than ground-truth accuracy.
- RSSI strongest-beacon methods provide a strong and interpretable baseline.
- Step count is useful as movement context and as a way to select RSSI window length, especially during low-motion periods.
- Step-adaptive RSSI is usually among the strongest or most interpretable methods, but it may not always outperform fixed-window RSSI.
- Low-motion RSSI clustering identifies repeatable signal states, but cluster-derived room labels should be treated cautiously.
- Labelled datasets provide stronger evaluation than no-reference datasets.
- Home_X001 remains useful for descriptive co-presence analysis, not accuracy evaluation.
- The pressure-floor-aware Sixth Phase work shows how the sensor-fusion pipeline can move beyond pointwise location estimation toward behavioural summaries such as stair transitions, sleep-location candidates, and active room-transition rates.

## 6.3 Interpretation of Objective 1: Data Integration and Preprocessing

Discuss:

- Whether the preprocessing workflow successfully aligned raw RSSI, movement data, metadata, and available labels.
- Whether pressure data were cleaned and aligned sufficiently to support floor-level inference in the two-floor dataset.
- How data availability affected the analyses that were possible in each dataset.
- Why shared time periods were important for two-person analysis.
- How preprocessing decisions shaped the reliability of later localisation and co-presence results.
- Which parts of the workflow became reusable across datasets.

## 6.4 Interpretation of Objective 2: RSSI-Derived Baseline Localisation

Discuss:

- How nearest-beacon or strongest-beacon baselines relate to prior BLE localisation methods.
- Whether fixed-window RSSI methods provided transparent and competitive baseline estimates.
- How window length affected stability and responsiveness.
- Why baseline RSSI methods remain valuable even when more complex movement-aware or clustering methods are explored.
- How the results compare cautiously with prior literature, recognising differences in homes, deployment conditions, and reference labels.

## 6.5 Interpretation of Objective 3: Movement-Aware and Floor-Aware Localisation

Discuss:

- Movement is not used directly as a room label.
- Movement helps decide when RSSI evidence is likely to be stable.
- Low-motion periods can justify longer RSSI windows.
- Active periods may require shorter windows to avoid hiding transitions.
- Threshold choice is a trade-off between stability and responsiveness.
- Pressure is not used as a room label, but it can provide a vertical-location constraint in a multi-floor home.
- Pressure-floor gating can reduce cross-floor RSSI ambiguity by selecting RSSI evidence from the pressure-inferred floor.
- ACC support for pressure-derived floor changes provides credibility that floor shifts reflect movement rather than only pressure artefacts.

## 6.6 Interpretation of Low-Motion Clustering and Hybrid Methods

Discuss:

- Clustering uses richer RSSI vectors than strongest-beacon methods.
- Clusters can reveal repeated signal states.
- Cluster dominant locations may be biased by training data distribution.
- Applying clusters to all windows can over-generalise stable low-motion states.
- Hybrid use of clustering as a conservative support component is conceptually safer, but current evidence may not show improvement over 4b.

## 6.7 Interpretation of Objective 4: Co-Presence and Behavioural Representation

Discuss:

- Co-presence analysis appeared first as an annotation-based visualisation concept and later became an RSSI-derived two-person analysis for Home_X001.
- Two-person timelines allow estimation of same-location and different-location periods.
- Without independent labels, co-presence values are descriptive RSSI-derived estimates.
- Night-time consistency can be used as a qualitative validation cue.
- Visualisations help identify algorithm disagreements and suspicious transitions.
- The Sixth Phase extends the same logic from location visualisation to behavioural metrics: floor changes become stair-transition candidates, long low-motion night periods become sleep-location candidates, and active-period beacon changes become room-transition rates.
- These metrics are valuable because they are closer to functional behaviour than raw sensor streams, but they should be described as preliminary descriptive measures unless validated against independent observation or participant report.

## 6.8 Interpretation of Objective 5: Evaluation and Evidence Strength

Discuss:

- Accuracy and balanced accuracy are appropriate for labelled datasets.
- Balanced accuracy is important when room labels are imbalanced.
- Pairwise agreement helps compare algorithms even when independent reference labels are unavailable.
- For no-reference datasets, stability, transition frequency, signal evidence, and visual consistency are more appropriate than accuracy.
- Direct observation can provide detailed reference labels but may reduce realism and feasibility in private homes.
- Self-report or diary labels are useful but may have recall errors and coarse timing.
- Qualitative plausibility assessment by people familiar with the data can support credibility when independent labels are limited.
- For pressure-floor behavioural metrics, internal consistency checks are especially important: pressure ramps should match ascent/descent direction, stair durations should be plausible, and room-transition metrics should be normalised by active or awake time.

## 6.9 Limitations

Important limitations:

- Not all datasets have independent ground-truth room labels.
- Earlier annotation files may be algorithm-derived and should not be treated as independent manual truth.
- RSSI is noisy and sensitive to environment and body position.
- Step count may miss non-walking activity.
- Pressure is useful for floor inference but can contain artefacts, offsets, or environmental pressure changes that require careful cleaning.
- Accelerometer features were explored but may need deeper integration.
- Floor-plan geometry was simplified in early visualisations.
- Sixth Phase behavioural metrics were derived from a single 80-hour two-floor dataset and should be treated as preliminary.
- Results may not generalise to all homes or participants.

## 6.10 Implications

Discuss:

- Interpretable RSSI and movement fusion is practical for exploratory home behaviour analysis.
- Pressure-floor-aware RSSI shows how additional environmental sensor context can make location estimates more behaviourally meaningful in multi-floor homes.
- The work provides a reproducible workflow for comparing methods across datasets.
- The approach can support future studies with stronger labels, more participants, richer sensor fusion, and behavioural metrics such as stair use, sleep-location routines, and active room-transition rates.

## 6.11 Reflection on AI-Assisted Development

Writing status: placeholder to be completed near final submission.

Discuss:

- AI-assisted coding tools were useful for accelerating implementation, debugging, restructuring scripts, planning figures, and organising report drafts.
- The main challenge was that generated suggestions could be plausible but wrong, especially when they assumed file paths, column names, data formats, or evaluation labels that did not match the actual project.
- Effective use required small, well-defined tasks; inspection of existing code and documentation before editing; careful version control; and repeated validation using concrete outputs rather than trusting generated code.
- Problems overcome during the project included correcting path assumptions, distinguishing existing annotation agreement from ground-truth accuracy, preventing over-interpretation of no-reference analyses, and ensuring that figures and tables were linked back to the objectives.
- The use of AI tools should be presented transparently as development support, while making clear that the student remained responsible for scientific judgement, code verification, result interpretation, and final writing.

## TODO Later

- Link each discussion point to a specific figure or table in Results.
- For each objective, cite the specific results sections, figures, and tables that provide evidence.
- Add citations to compare findings with literature.
- Finalise the AI-assisted development reflection after the final code and report workflow are stable.
- Ensure limitations are honest but not self-undermining.
- Avoid letting the discussion become only a final-stage labelled-data interpretation; include how earlier stages shaped the final methods.
- Also avoid giving early prototype work equal weight with the final analyses; explain it as foundation rather than as the main evidence.
