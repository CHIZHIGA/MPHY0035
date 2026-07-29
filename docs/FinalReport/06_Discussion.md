# 6. Discussion

## 6.1 Interpretation Against the Aim and Objectives

The aim of this project was to develop and evaluate methods that combine wearable movement, RSSI-derived environmental beacon data, and available environmental context to estimate home location and produce more interpretable descriptions of lived experience. The results support this aim at the level of an auditable analytical framework rather than a clinically validated monitoring system. The main contribution is not a new BLE positioning principle, but a common evidence hierarchy in which RSSI proposes location while movement, behavioural state, pressure, and missingness determine how that proposal is interpreted.

The relationship between the five objectives and the principal results is summarised in Figure 12. This structure is used throughout the discussion so that technical performance is interpreted in relation to the intended clinical and behavioural application.

![Figure 12: Principal results interpreted against the study objectives](figures/figure_6_objectives_summary.svg)

**Figure 12: Interpretation of the principal results against the study objectives.**

## 6.2 Common Processing and Interpretable RSSI Baselines

The first objective was achieved at the processing level. The pipeline handled separate and combined RSSI formats, ACC and step-derived movement, optional pressure, optional reference annotations, and two-person collections within one output structure. This is important for real-world home sensing, where missing modalities are likely and a method that requires every sensor would exclude much of the available evidence. The two excluded collections also clarify the boundary of this claim: the framework is portable across parseable raw datasets, but it cannot reconstruct unavailable or unexported sensor streams.

The five-minute timeline provided a practical common unit for room use, sleep, away, and co-presence. It reduced sample-level RSSI variability and allowed modalities with different sampling rates to be compared. However, it also limits temporal precision. A short room visit, stair movement, or rapid transition may be merged into one window. The framework is therefore better suited to daily patterns and room-level behaviour than to precise path reconstruction or stair-event timing.

The strongest-RSSI proposal addressed the second objective by providing a transparent baseline. Strongest-beacon methods are simpler than fingerprinting or coordinate-based indoor positioning, but require less calibration and make each decision easier to audit [5]. This was appropriate because the project sought interpretable room and behavioural summaries rather than centimetre-level position. The results also showed why the baseline must remain visible: corrections affected only 2.27% of windows, so most final room estimates still came directly from RSSI. Keeping the raw proposal alongside the corrected output prevents the added state hierarchy from obscuring the underlying radio evidence.

## 6.3 Movement-Supported Location and Behavioural States

The third objective asked whether movement and pressure could improve the interpretation of RSSI stability and transitions. The overall 11.7% reduction in observed room transitions indicates that the state hierarchy removed some short-lived changes that were unsupported by movement or stable behavioural context. The effect was not uniform, as shown in Figure 13. KM Mal and KM PanH Nov22 had the largest proportional reductions, whereas AA002, AB002, and DH PanoH were almost unchanged.

![Figure 13: Reduction in observed room transitions by session](figures/figure_6_1_transition_reduction.svg)

**Figure 13: Reduction in observed room transitions after correction; transition reduction is a stability measure, not an accuracy measure.**

This variation is informative. A common numerical movement threshold did not transfer across recordings, but the common clustering rule selected recording-specific low-motion boundaries. Most sessions resolved to two movement states and two resolved to three, suggesting that a low/high distinction was usually sufficient at the five-minute scale. ACC provided richer evidence of stillness than step count. Zero steps only indicate no detected walking and can also represent sitting, device non-wear, or sparse export. The conservative restriction on step-derived sleep therefore reduced the risk of converting quiet non-Bedroom periods into spatial corrections.

EF-001 and EF-002 demonstrate that movement support should not be treated as one generic smoothing rule. In EF-001, repeated observed-room switching during long low-motion episodes was reduced by selecting a supported episode-dominant room. In EF-002, the main issue was missing RSSI rather than switching, and only short gaps with two-sided local support were recovered. Retaining the near-whole-night unsupported gap was as important as filling the shorter gaps. It showed that the pipeline could preserve uncertainty instead of converting all low-motion missingness into Bedroom.

The small increase in overall room coverage, from 76.48% to 76.70%, reinforces this interpretation. The method primarily changed how observed evidence was stabilised; it did not attempt to create continuous location records. Likewise, unresolved sleep in four sessions should not be interpreted only as failure. These outputs reveal where repeated duration or room evidence was insufficient. The cost is lower completeness, but the benefit is that confidence is not manufactured by a forced label.

## 6.4 From Room Estimates to Lived-Experience Context

The fourth objective extended location into behavioural summaries. Across the processed data, the pipeline identified 61 main-sleep episodes and 158 probable-away runs and produced room-transition, pressure-floor, and co-presence outputs. These variables are closer to the clinical motivation than a raw RSSI sequence because they describe when a person appeared settled, absent, moving between spaces, or sharing a room with another person. They remain candidate behavioural states, however, rather than measurements of sleep quality, social engagement, or functional impairment.

Home_X001 demonstrates both the value and the limitation of co-presence. Corrected same-room time changed only from 33.25 to 32.67 hours, but 41 windows were added and 48 removed. The similar total therefore concealed local changes in when co-presence was inferred. Separating awake and sleep co-presence was also important because the same-room state has different possible meaning in those contexts. Room overlap may support an interaction-aware representation of daily life, but it cannot establish that an interaction occurred [4].

The pressure branch provided a second example of context rather than direct classification. In NewData80h, the automatic pressure grouping recovered the two-floor beacon pairing, but only five room windows were changed by the trusted floor constraint. In Home_X001, apparently stable pressure subgroups failed the floor-scale criteria and the K=1 null outcome was retained. This contrast supports the use of pressure for vertical constraint while showing why statistical separation alone is insufficient. Barometric information can assist floor inference [7], but sensor offsets and mounting height can resemble floor structure unless physically meaningful separation is required.

Post-hoc participant feedback in NewData80h supported the inferred two-floor layout and the original selection of `3E05` as the leading sleep-location candidate. This provides useful qualitative credibility because the analysis preceded that feedback. It is still limited evidence from one participant and should not be treated as independent validation of the complete unified pipeline. A stronger future protocol would present pre-specified timeline summaries to participants and record agreement, disagreement, and uncertainty systematically.

## 6.5 Reference Agreement and the Cost of Generality

The fifth objective required evaluation appropriate to the evidence available. In all four labelled datasets, corrected end-to-end agreement exceeded the raw strongest-RSSI result. This improvement should be interpreted carefully. In the three DH datasets, much of the increased evaluable coverage came from mapping `Probable away` to reference `Out`, rather than from improving indoor room assignment alone. Reporting conditional accuracy, balanced accuracy, macro-F1, and end-to-end agreement together was therefore necessary to distinguish room classification from occupancy coverage.

The comparison with earlier methods reveals the main trade-off of the project. As shown in Figure 14, the earlier dataset-specific method retained higher balanced agreement in all four labelled comparisons, although the difference was small for KM Mal. These values were produced by related but non-identical evaluation protocols and should not be treated as a controlled algorithm benchmark. Nevertheless, they show that one general pipeline was not the optimal room classifier for every dataset.

![Figure 14: Balanced agreement trade-off](figures/figure_6_2_balanced_agreement_tradeoff.svg)

**Figure 14: Balanced reference agreement for earlier specialised methods and the unified pipeline under related but non-identical protocols.**

This performance cost is understandable. The earlier 4b and selected fixed-window methods were designed around a narrower task and could exploit dataset-specific window behaviour. The unified method imposed common safeguards, explicit missingness, occupancy states, and restrictions on step-derived and pressure-derived correction. These choices reduced the opportunity to maximise one room-level metric but made outputs more comparable and easier to audit. The result is therefore a framework with broader scope, not evidence of a universally superior localisation algorithm.

The labelled comparisons also do not constitute independent external validation. Step reconstruction and the step-derived Bedroom restriction were refined after examining DH outputs, while the borderline away rule was inspected in KM Mal. Reference labels were separated from prediction at runtime, but development decisions were still influenced by these datasets. A genuinely independent test would freeze all rules and thresholds before application to a new labelled collection.

Reference data introduce further limitations. Continuous observation can produce detailed labels but may alter natural behaviour and is difficult to sustain in private homes. Diaries are less intrusive but can have recall and timing errors [1]. Participant feedback can establish whether broad patterns appear credible, but may not resolve individual five-minute transitions. These sources should therefore be treated as complementary evidence rather than interchangeable ground truth.

## 6.6 Strengths, Limitations, and Clinical Implications

The main strength of the framework is explicit evidence handling. Raw room, corrected room, behaviour, occupancy, and correction reason remain separate. Missing windows are preserved unless a defined support rule applies, and movement, sleep, away, and pressure models are allowed to remain unresolved. This makes the outputs inspectable and reduces the risk that a smooth timeline is mistaken for a correct timeline.

Several limitations remain. RSSI is sensitive to body orientation, multipath propagation, beacon placement, and changes in the home. The five-minute grid can hide short transitions. Step-derived movement is weaker than ACC, while pressure was available in too few suitable multi-floor recordings to establish general performance. Bedroom and room metadata also affect which outputs can be named or spatially corrected. Most importantly, only four datasets had reference annotations, some pipeline rules were refined using those datasets, and no independent labelled test collection was available.

The behavioural interpretation is correspondingly preliminary. Main-sleep episodes are prolonged low-motion states with room support, not clinically measured sleep. `Probable away` is inferred from RSSI absence while the wearable remains online, not confirmed absence. Same-room time is not equivalent to social interaction, and floor transitions are not automatically stair use. The framework should therefore support hypothesis generation, visual review, and study design rather than direct clinical decision-making in its current form.

Despite these limitations, the project demonstrates a useful direction for home monitoring. Wearable activity becomes more interpretable when linked to room, occupancy, and household context. A low-motion period in a supported Bedroom state conveys different evidence from the same movement level in a Kitchen or during probable absence. This context-aware representation is closer to lived experience than either activity volume or location alone and provides a basis for future longitudinal measures of routine, independence, mobility, and co-presence.

## 6.7 AI-Assisted Development

AI-assisted tools supported code drafting, debugging, restructuring, figure preparation, and report organisation. Their main limitation was that plausible suggestions could contain incorrect assumptions about paths, columns, sensor formats, or the strength of available labels. Effective use therefore required inspecting the repository before editing, dividing work into small testable changes, checking generated outputs against audit files, and retaining human responsibility for scientific interpretation.

Examples included correcting path assumptions, separating annotation agreement from ground-truth accuracy, rejecting unsupported pressure groups, and preserving no-reference conclusions as descriptive. AI assistance accelerated implementation but did not replace validation or methodological judgement. Appendix F provides a fuller record of how these tools were used and checked.
