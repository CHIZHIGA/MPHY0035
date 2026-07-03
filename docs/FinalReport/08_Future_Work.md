# 8. Future Work

Writing status: stable enough to draft now.

This chapter should describe realistic extensions, not speculative unrelated work.

## 8.1 Additional Labelled Data and Independent Ground Truth

Future work should prioritise datasets with independent or diary-based room reference labels. This would allow more robust evaluation of RSSI-only, movement-adaptive, clustering, and hybrid methods across more participants and home layouts.

TODO: Add final wording after confirming whether more labelled datasets are available.

## 8.2 Improved RSSI Modelling

Possible extensions:

- improve RSSI vector modelling;
- use probabilistic room estimates rather than single strongest-beacon labels;
- include uncertainty scores based on RSSI sample count, signal separation, and beacon consistency;
- test whether ambiguity-aware rules reduce false room transitions.

## 8.3 Deeper Movement Feature Integration

Possible extensions:

- use accelerometer magnitude and variation more fully;
- compare step count with acceleration-derived movement intensity;
- identify transition periods explicitly;
- model sleep or long stationary periods separately from active low-step behaviour.

## 8.4 Supervised and Semi-Supervised Learning

If enough labelled data become available, future work could test supervised or semi-supervised approaches using:

- RSSI features;
- step-count features;
- accelerometer-derived features;
- pressure-derived features where appropriate;
- temporal context.

Any machine learning method should be compared against the interpretable strongest-beacon and step-adaptive baselines.

## 8.5 Pressure-Based Floor Detection

The supervisor suggested pressure sensor data as a possible way to identify floor level in multi-floor homes. The current Home_X001 analysis is from an apartment-like setting, so this is better reserved for future multi-floor data.

Future analysis could compare pressure changes from wearable and beacon sensors to estimate whether a participant is upstairs or downstairs.

## 8.6 More Realistic Spatial Visualisation

Possible extensions:

- use a real floor plan rather than simplified room layouts;
- show uncertainty or confidence alongside location;
- improve visual comparison of multiple algorithms;
- create interactive timelines for supervisor or clinical review.

## 8.7 Generalisation Across Participants and Homes

Future work should test whether the selected thresholds and methods generalise across:

- different homes;
- different beacon placements;
- different participants;
- single-person and two-person datasets;
- clean and ambiguous RSSI environments.

## TODO Later

- Keep this chapter specific and realistic.
- Mention only future work that follows naturally from the current project.
- Avoid promising a complete clinical system.
