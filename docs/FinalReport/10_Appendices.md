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

## Appendix E: AI-Assisted Coding and Verification

TODO: Write a concise statement if required by the supervisor or course.

Suggested points:

- AI-assisted coding tools supported planning, code drafting, debugging, and report organisation.
- Outputs were checked using explicit validation tests, row-count checks, timestamp checks, non-empty output checks, and visual inspection.
- Scientific interpretation and final report responsibility remain with the student.

## TODO Later

- Decide which appendix material is necessary.
- Keep appendices concise.
- Avoid duplicating all work logs.
