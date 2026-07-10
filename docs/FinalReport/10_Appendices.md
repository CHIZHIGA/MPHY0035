# 10. Appendices

Writing status: partly stable; fill as code and outputs stabilise.

Appendices should contain supporting material only. Do not use appendices to hide essential methodology or key results.

## Appendix A: Code Structure

TODO: Summarise the main scripts without overloading the main report.

Candidate script groups:

- early annotation and floor-plan visualisation scripts;
- AA002 raw RSSI and movement analysis scripts;
- Home_X001 availability and co-presence scripts;
- Home_X001 fixed-window, step-adaptive, clustering, and hybrid scripts;
- labelled-data comparison scripts;
- RSSI evidence and signal stability plotting scripts.
- Sixth Phase pressure-floor inference, floor-aware RSSI, stair-transition, sleep-location candidate, and room-transition metric scripts.

Suggested table:

| Script | Purpose | Main outputs |
|---|---|---|
| TODO | TODO | TODO |

## Appendix B: Additional Figures

Use this section for figures that support the report but are not essential in the main Results chapter.

Candidate figure types:

- extra per-dataset timelines;
- pairwise agreement heatmaps;
- additional confusion matrices;
- model-selection figures;
- supplementary co-presence timelines;
- early prototype visualisations.

## Appendix C: Parameter Settings

Suggested table:

| Method | Parameter | Value | Justification |
|---|---|---|---|
| Fixed RSSI | Window size | TODO | TODO |
| Step-adaptive RSSI | Step threshold | TODO | TODO |
| Low-motion clustering | Training window | TODO | TODO |
| Low-motion clustering | k range | TODO | TODO |
| Hybrid method | Override criteria | TODO | TODO |
| Pressure floor inference | Window size | TODO | TODO |
| ACC support | Motion threshold | TODO | TODO |
| Stair-transition duration | Valid duration threshold | TODO | TODO |
| Sleep-location candidate | Low-motion and night-window criteria | TODO | TODO |
| Active room-transition rate | Awake/motion threshold | TODO | TODO |

## Appendix D: Validation Checks

Document validation checks such as:

- input files are present;
- output CSV files are non-empty;
- output figures are non-empty;
- timestamp ranges match expected recording periods;
- shared Home_X001 overlap is used for two-person comparison;
- SUBJECT and STUDY_PARTNER roles are read from metadata;
- co-presence durations sum to the expected analysis duration;
- no-reference datasets are not reported using ground-truth accuracy language;
- labelled-data metrics are calculated only where reference labels are available.
- pressure-derived floor changes are checked against ACC support;
- pressure-floor-aware RSSI outputs are checked against beacon floor metadata;
- stair-transition durations are checked for plausible pressure-ramp direction and duration;
- sleep-location candidates are described as candidates, not verified sleep;
- room-transition rates are normalised by observed active or awake time where appropriate.

## Appendix E: AI-Assisted Coding and Verification

TODO: Add supporting details for the transparent AI-use statement in Methodology and Discussion, if required by the supervisor or course.

Suggested points:

- AI-assisted coding tools supported planning, code drafting, debugging, and report organisation.
- Outputs were checked using explicit validation tests, row-count checks, timestamp checks, non-empty output checks, and visual inspection.
- Scientific interpretation and final report responsibility remain with the student.
- Include a short list of practical verification examples, such as checking generated CSV files, confirming figure paths, validating timestamp ranges, and comparing method outputs against expected metadata.
- Refer to project work logs where appropriate, but do not reproduce long chat transcripts or implementation logs in the main report.

## TODO Later

- Decide which appendix material is necessary.
- Keep appendices concise.
- Avoid duplicating all work logs.
