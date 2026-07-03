# 2. Introduction

Writing status: first draft from current project progress.

This chapter introduces the project as a scientific data analysis project about combining wearable activity data and RSSI-derived location data to understand behaviour in the home. The report is framed around the clinical and methodological need for context-aware representations of lived experience, rather than around the chronological order in which the work was completed.

## 2.1 Motivation

Accurately measuring how people behave and function within their own homes is an important challenge in digital health research. Traditional clinical assessments and patient-reported outcomes can provide valuable information, but they are often collected episodically and may not capture the full variability of everyday behaviour. Wearable and environmental sensors offer a complementary approach by recording activity and environmental context continuously during normal daily life.

Wearable motion sensors can describe how active a person is, but movement alone does not explain where that activity takes place. For example, similar step counts may have different behavioural meanings if they occur in a bedroom, kitchen, living room, or outside the home. Room-level location can therefore provide important context for interpreting activity, routines, independence, and possible social interaction between people living in the same home.

Bluetooth Low Energy (BLE) environmental beacons provide a practical way to estimate room-level location. A wearable device can record Received Signal Strength Indicator (RSSI) values from nearby beacons, and the strongest or most stable beacon signal can be mapped to a room. However, RSSI is noisy in real homes because of body occlusion, multipath effects, beacon placement, missing detections, and changes in the environment. A location estimate based only on RSSI may therefore be unstable during transitions or ambiguous signal periods.

The motivation for this project is to combine RSSI-derived spatial evidence with wearable movement data. BLE-based room localisation is already an established area, so the focus of this project is not to invent BLE localisation from first principles. Instead, the project investigates how RSSI-derived location can be integrated with activity and movement measures, and how this combined information can be extended to describe two-person co-presence. Movement does not directly identify a room, but it can help interpret when an RSSI estimate is likely to be stable. Low-motion periods may provide more reliable RSSI signatures, while high-motion periods may correspond to transitions where shorter windows or lower confidence are more appropriate.

## 2.2 Aim and Objectives

Aim:

To develop and evaluate analysis and visualisation methods that combine wearable movement data with RSSI-derived environmental beacon data to estimate room-level location and describe home behaviour, including co-presence between two people.

Objectives:

- Objective 1: Develop a reproducible preprocessing pipeline for aligning raw BLE RSSI, wearable movement data, metadata, and available reference labels.
- Objective 2: Establish interpretable RSSI-derived room-level localisation baselines using nearest-beacon or strongest-beacon methods.
- Objective 3: Develop movement-aware localisation methods that use wearable activity signals to interpret RSSI stability and transitions.
- Objective 4: Extend individual room-level location analysis to visualisation and quantification of two-person co-presence.
- Objective 5: Evaluate methods across datasets using appropriate metrics for the available evidence, including agreement with existing annotations, descriptive no-reference comparison, and reference-label accuracy where available.

## 2.3 Research Questions or Hypotheses

Research questions:

- Can low-motion windows provide more stable RSSI signatures for room-level localisation?
- Does movement-adaptive RSSI window selection provide a useful and interpretable alternative to fixed-window RSSI localisation?
- Can low-motion RSSI clustering identify repeatable signal states that help interpret room-level location, and what are its limitations?
- How consistent are fixed-window RSSI, movement-adaptive RSSI, and clustering-based methods across datasets with and without reference labels?
- How can two-person RSSI-derived location timelines be used to describe co-presence and separation patterns in a home?

## 2.4 Contributions of This Project

This project contributes:

- A reproducible data-processing workflow for aligning raw RSSI, step-count, and accelerometer-derived movement signals.
- A baseline fixed-window strongest-beacon RSSI location method.
- A movement-aware step-adaptive RSSI method that uses low-motion periods to choose longer RSSI windows.
- An exploratory low-motion RSSI clustering method for identifying stable signal states.
- A conservative hybrid analysis that tests whether low-motion clustering can support, rather than replace, the step-adaptive RSSI method.
- A labelled-data evaluation workflow using accuracy, balanced accuracy, confusion matrices, and per-location recall where reference labels are available.
- A no-reference descriptive workflow for two-person co-presence analysis in Home_X001.
- Visualisations that combine location, movement, and co-presence information over time.

## 2.5 Report Structure

Chapter 3 reviews the background literature on home monitoring, wearable activity sensing, BLE RSSI localisation, sensor fusion, co-presence, and evaluation challenges. Chapter 4 describes the datasets, preprocessing steps, localisation algorithms, co-presence analysis, visualisation methods, and evaluation strategy. Chapter 5 presents the results, moving from initial visualisation and baseline localisation toward movement-aware methods, two-person co-presence analysis, and labelled-data evaluation. Chapter 6 interprets the findings in relation to the clinical context and research objectives. Chapter 7 summarises the conclusions, and Chapter 8 outlines future work.

## TODO Later

- Confirm final dataset names and chapter numbering.
- Add final quantitative headline result once Results is stable.
- Ensure the final introduction matches the revised Background and Methodology structure.
- Keep the project progression visible, but do not frame the report as a five-stage diary.
- Check final wording against supervisor feedback before submission.
