# 3. Background

Writing status: revised draft based on the 2026-06-29 supervisor feedback. Literature content is drafted; formal citations should be completed later.

This chapter provides the scientific context for the project. The central argument is that BLE beacon-based room localisation is already an established area, but location estimates become more clinically and behaviourally meaningful when they are integrated with wearable movement data and extended to describe co-presence between people in the same home.

## 3.1 Home Monitoring, Lived Experience, and Clinical Context

Understanding how people behave and function in their own homes is a major challenge in digital health research. Traditional clinical outcome measures, clinic-based assessments, and patient-reported outcomes can provide important information, but they are often episodic, retrospective, and affected by subjectivity. They may not capture day-to-day variation in behaviour, changes in functional independence, or the way symptoms affect ordinary routines in the home [REF].

Continuous home sensing offers a complementary approach. Wearable and environmental sensors can collect passive data during normal daily life, allowing researchers to study patterns of movement, rest, room use, and routine over longer periods. This is particularly relevant for ageing, neurodegenerative disease, Alzheimer’s disease and related disorders, and other long-term conditions where daily function is a key clinical concern [REF]. In these settings, a person’s lived experience is not fully described by how much they move, but by how movement occurs within meaningful daily contexts.

Room-level location provides this contextual layer. For example, activity in a bedroom, kitchen, living room, or outside the home may imply different behaviours and different clinical interpretations. A period of low movement in the bedroom may reflect sleep or rest, while low movement in a living room may reflect sedentary daytime behaviour. Similarly, time spent in shared rooms may have different meaning from time spent alone. Combining home location with wearable activity measures can therefore support a more context-aware representation of lived experience than activity measurement alone.

The present project is positioned within this context. Its aim is not only to estimate room location, but to develop analysis and visualisation methods that combine RSSI-derived location, wearable movement measures, and two-person co-presence information. This framing connects technical localisation methods to the broader clinical problem of understanding daily behaviour in the home.

## 3.2 Wearable Activity Sensing and Its Context Problem

Wearable sensors are widely used to measure physical activity in real-world settings. Step count, actigraphy, and accelerometer-derived features can provide continuous person-specific information about movement intensity, rest, and activity patterns [REF]. Step count is particularly interpretable and easy to summarise, while accelerometer magnitude and variability can capture movement that is not represented by steps alone.

However, wearable activity data have an important limitation: they usually describe how much movement occurred, but not where it occurred or what environmental context surrounded it. The same step count may have different behavioural meaning depending on whether it occurred in a bedroom, kitchen, hallway, garden, or outside the home. Similarly, a low-activity period may represent sleep, seated activity, illness, device non-wear, or simply remaining in one room. Without location context, these possibilities can be difficult to distinguish.

This limitation motivates the integration of wearable movement sensing with indoor localisation. Room-level location can help interpret activity in relation to daily routines, such as sleeping, cooking, moving between rooms, or spending time in shared living spaces. In multi-person homes, location context can also support analysis of whether people appear to spend time together or separately. Therefore, the value of wearable activity sensing is increased when it is combined with environmental context.

In this project, step count and accelerometer-derived movement are not treated as direct room classifiers. Instead, movement signals are used to interpret the reliability and temporal meaning of RSSI-derived location estimates. Low movement may suggest that a participant remained in a stable location, while higher movement may indicate a transition between rooms or a period where short-window RSSI estimates are more appropriate.

## 3.3 BLE Beacon-Based Room-Level Localisation

Bluetooth Low Energy (BLE) beacons are a practical technology for indoor localisation. BLE systems are relatively low cost, low power, and easy to deploy in domestic settings compared with many infrastructure-heavy alternatives [REF]. A wearable device can record the Received Signal Strength Indicator (RSSI) of nearby beacons, and these RSSI readings can be used to infer proximity to rooms or locations where beacons are installed.

The simplest BLE localisation methods use a nearest-beacon or strongest-beacon rule. RSSI readings are grouped into time windows, the beacon with the strongest signal is identified, and that beacon is mapped to a room using metadata. This approach is attractive because it is transparent, calibration-light, and easy to interpret. It also provides a useful baseline for evaluating more complex methods.

More advanced BLE localisation approaches use richer RSSI representations. These include RSSI summary features, beacon ranking, strongest-second signal differences, and RSSI vector or fingerprinting methods. Fingerprinting and vector-based methods can preserve more information about the pattern of signal strengths across beacons, but they may require more calibration or be more sensitive to missing beacon readings and environmental changes [REF].

RSSI-based localisation is challenging in real homes. Signal strength is affected by multipath propagation, walls, furniture, device orientation, human body occlusion, beacon placement, and missing detections. The signal may also be unstable during room transitions or when the wearable is temporarily shielded. For this reason, room-level localisation is more realistic for this project than precise coordinate tracking. Room labels are also more clinically interpretable than exact coordinates because they connect activity to meaningful home contexts.

This project builds on prior BLE localisation work rather than claiming novelty in BLE localisation itself. The novelty lies in how RSSI-derived room estimates are combined with wearable movement data, how multiple algorithms are compared across datasets, and how location estimates are used to describe two-person co-presence.

## 3.4 Sensor Fusion: Combining Location and Movement

Sensor fusion is important because RSSI and movement data provide complementary information. RSSI provides spatial evidence about nearby beacons, while wearable movement data provides information about whether the participant appears stationary, active, or transitioning. Combining these data sources can therefore improve interpretation even when movement does not directly identify the room.

One useful fusion principle is that low-motion windows may provide more stable RSSI signatures. If a participant has taken very few steps over a time window, it is more plausible that they remained in one room, so a longer RSSI window may reduce short-term signal noise. In contrast, when movement is higher, shorter RSSI windows may be needed to avoid smoothing over room transitions. Movement can therefore act as a temporal stability signal for RSSI localisation.

This idea can be implemented in interpretable ways. Rather than immediately using a complex machine learning model, a rule-based method can use step count to choose the RSSI window length. Longer windows are selected during low-motion periods, while shorter windows are used during more active periods. RSSI remains the spatial signal; movement controls how RSSI evidence is grouped and interpreted.

Accelerometer-derived features can also provide movement context. Step count is simple and clinically understandable, but it may miss non-walking movement. Acceleration magnitude and its variability can capture additional motion, such as arm movement, posture changes, or small movements within a room. This makes accelerometer data a useful extension for future refinement of movement-aware localisation.

In this report, movement-aware localisation is framed as a way to make RSSI estimates more interpretable and context-sensitive. The aim is not to replace RSSI with activity signals, but to use activity signals to identify stable periods, possible transitions, and uncertainty in location estimates.

## 3.5 Co-Presence and Multi-Person Home Behaviour

Many home-monitoring studies focus on a single participant. However, lived experience often occurs in a social context. In two-person households, it may be useful to know not only where one person is, but whether two people appear to be in the same room, in different rooms, or whether one person appears to be away from the home environment. These patterns may provide information about daily routines, caregiving, social contact, shared activities, and separation within the home [REF].

Co-presence analysis extends room-level localisation from individual monitoring to interaction-aware home behaviour. If two people are estimated to be in the same room, this may indicate possible shared activity or social interaction. If they are in different rooms, this may indicate independent activity. If only one person is detected in the home, this may indicate separation or missing/unmapped signal evidence. These interpretations must be made cautiously, but the derived states can still provide a useful behavioural summary.

This project treats co-presence as a key part of the novelty. BLE localisation alone can estimate where a device is, but combining two people’s room-level estimates allows the analysis to describe together/apart patterns. When movement information is added, the resulting representation can show not only where people appear to be, but whether location changes occur during active or low-motion periods.

It is important to distinguish estimated co-presence from verified social interaction. In datasets without independent room labels or direct observation, co-presence states should be described as RSSI-derived estimates. They are useful for descriptive analysis and algorithm comparison, but they should not be over-interpreted as confirmed behaviour without validation.

## 3.6 Evaluation Challenges in Real-World Home Sensing

Evaluation is difficult in real-world home sensing because independent ground-truth location labels are often limited or unavailable. Some datasets contain existing annotation files, but these annotations may themselves be derived from RSSI or other sensor algorithms rather than independent manual observation. In those cases, comparison with the annotation file should be described as agreement with existing annotations, not as true ground-truth accuracy.

When diary-based or independently labelled reference data are available, stronger quantitative evaluation is possible. Metrics such as accuracy, balanced accuracy, confusion matrices, and per-location recall can be used to compare methods. Balanced accuracy is particularly useful for room-level localisation because room labels are often imbalanced; a participant may spend much more time in one room than another, so overall accuracy alone can hide poor performance for less frequent locations.

For datasets without independent reference labels, the evaluation strategy must be descriptive. Methods can be compared using transition counts, timeline stability, RSSI sample evidence, signal separation, pairwise agreement between algorithms, and visual plausibility checks. For example, excessive room switching during likely sleep periods may indicate unstable localisation, while consistent low-motion room estimates may be more plausible.

These evaluation distinctions shape the whole report. Early comparisons with existing annotations are treated as agreement analyses. Home_X001 is treated as a no-reference descriptive dataset for RSSI-derived location and estimated co-presence. Later labelled datasets provide stronger reference-label evaluation. This careful terminology is necessary to connect the technical results to the scientific context without overstating the evidence.

## TODO Later

- Add final formal citations for home monitoring, wearable activity sensing, BLE localisation, sensor fusion, co-presence, and evaluation metrics.
- Decide whether to keep `[REF]` placeholders or convert to numbered citations during the final reference pass.
- Add one or two high-value papers specifically on multi-person or co-presence sensing if available.
