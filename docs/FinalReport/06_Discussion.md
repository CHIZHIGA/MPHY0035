# 6. Discussion

Writing status: partly stable, but should be finalised after Results.

This chapter should interpret the results and connect them back to the research questions and literature.

The discussion should recognise the whole project progression, but with increasing emphasis on the later stages. Early work should be discussed mainly as foundation and motivation. The most detailed interpretation should focus on the mature RSSI and movement-fusion methods, no-reference co-presence analysis, and labelled-data evaluation.

## 6.1 Summary of Main Findings

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

## 6.2 Interpretation of Movement-Aware Localisation

Discuss:

- Movement is not used directly as a room label.
- Movement helps decide when RSSI evidence is likely to be stable.
- Low-motion periods can justify longer RSSI windows.
- Active periods may require shorter windows to avoid hiding transitions.
- Threshold choice is a trade-off between stability and responsiveness.

## 6.3 Interpretation of Low-Motion Clustering

Discuss:

- Clustering uses richer RSSI vectors than strongest-beacon methods.
- Clusters can reveal repeated signal states.
- Cluster dominant locations may be biased by training data distribution.
- Applying clusters to all windows can over-generalise stable low-motion states.
- Hybrid use of clustering as a conservative support component is conceptually safer, but current evidence may not show improvement over 4b.

## 6.4 Co-Presence and Behavioural Interpretation

Discuss:

- Co-presence analysis appeared first as an annotation-based visualisation concept and later became an RSSI-derived two-person analysis for Home_X001.
- Two-person timelines allow estimation of same-location and different-location periods.
- Without independent labels, co-presence values are descriptive RSSI-derived estimates.
- Night-time consistency can be used as a qualitative validation cue.
- Visualisations help identify algorithm disagreements and suspicious transitions.

## 6.5 Evaluation and Metrics

Discuss:

- Accuracy and balanced accuracy are appropriate for labelled datasets.
- Balanced accuracy is important when room labels are imbalanced.
- Pairwise agreement helps compare algorithms even when independent reference labels are unavailable.
- For no-reference datasets, stability, transition frequency, signal evidence, and visual consistency are more appropriate than accuracy.

## 6.6 Limitations

Important limitations:

- Not all datasets have independent ground-truth room labels.
- Earlier annotation files may be algorithm-derived and should not be treated as independent manual truth.
- RSSI is noisy and sensitive to environment and body position.
- Step count may miss non-walking activity.
- Accelerometer features were explored but may need deeper integration.
- Floor-plan geometry was simplified in early visualisations.
- Results may not generalise to all homes or participants.

## 6.7 Implications

Discuss:

- Interpretable RSSI and movement fusion is practical for exploratory home behaviour analysis.
- The work provides a reproducible workflow for comparing methods across datasets.
- The approach can support future studies with stronger labels, more participants, and richer sensor fusion.

## TODO Later

- Link each discussion point to a specific figure or table in Results.
- Add citations to compare findings with literature.
- Ensure limitations are honest but not self-undermining.
- Avoid letting the discussion become only a final-stage labelled-data interpretation; include how earlier stages shaped the final methods.
- Also avoid giving early prototype work equal weight with the final analyses; explain it as foundation rather than as the main evidence.
