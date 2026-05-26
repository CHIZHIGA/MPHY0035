# 2026-05-18 Derek

What I really want you to do is work on raw data analysis. Rather than just doing visualization of the json files, I want you to recalculate location from the raw data.

I would like you to create an algorithm to use a combination of both beacon RSSI data AND​ movement data to label location,

The simplest measure movement is step count, so you could, start with that: When calculating position, you could use a sliding window to identify periods with very little motion (eg: fewer than n steps, where you can vary n to find a good performance) and in that period of time, identify the corresponding strongest beacon signature (simplest the beacon that has the highest proportion of time being lowest RSSI, but you could also try something that used the RSSI vector instead of lowest value). 

# 2026-05-20 czg

Thank you for your suggestions. I have thought more about the next step, and my understanding is that the main aim should be to move beyond visualising the existing annotation JSON files and instead recalculate room-level location directly from the raw sensor data.

My plan is to focus on AA002 first. I would first compare different ways of representing the raw beacon RSSI data, since this is the main spatial signal for room-level location. One simple approach is to use summary features, such as the strongest beacon, mean RSSI, maximum RSSI, signal ranking, or the difference between the strongest and second strongest beacon. Another approach is to use the full RSSI vector across all available beacons, which may preserve more information about the room-level signal signature. I can compare these RSSI representations against the existing room-level annotations to see which gives better location estimates.

After establishing an RSSI-based baseline, I would then combine RSSI with movement information. I would start with step count, as this is the simplest movement measure. For each sliding time window, step count can be used to identify low-motion periods, where the RSSI signature is likely to be more stable and informative for room-level location.

I would also like to make the sliding window adaptive rather than fixing it only by time of day. The algorithm could start from a short base window and expand the window when the data suggest a stable state, for example low step count, low acceleration variation, and a stable RSSI signature. If movement increases or the RSSI pattern changes quickly, the algorithm would use a shorter window to capture possible room transitions. In this way, longer windows would naturally occur during sleep or other low-motion periods, while shorter windows would be used during active or transitional periods.

After the step-count baseline, I would like to test accelerometer-derived features as well. Step count is simple and interpretable, but acceleration may capture non-walking movement. Therefore, I would like to compare RSSI only, RSSI with step count, RSSI with accelerometer features, and RSSI with both step count and accelerometer features.

The existing room-level annotations can be used as reference labels for evaluation. I can compare the estimated location against the annotated location using measures such as accuracy and a confusion matrix. This would allow me to assess which RSSI representation and which combination of movement features performs best.

In the later stage, I would also like to explore a supervised machine learning approach, where RSSI features, step count, and accelerometer features are used as input features, and the annotated room-level locations are used as training labels. This would allow me to evaluate whether a fused model can improve room-level location estimation compared with simpler rule-based or feature-based methods.

Overall, my planned direction is to first compare RSSI representations, then build an interpretable sliding-window baseline using RSSI and movement data, and finally explore whether a machine learning model can improve the robustness of room-level location estimation.

# 2026-05-20 Derek

Great description! Looks like you used some AI to help you write that description, which is fine.   

There is plenty more data for you to look at in due course. 

The one additional point you might want to look at is analysis of data from two people simultaneously. But I agree with the initial steps you propose.

# 2026-05-24 czg

I have been working on the raw-data location analysis for AA002, following your suggestion to combine beacon RSSI data with movement information.

So far, I have found two main results.

First, the pure RSSI strongest-beacon baseline is already quite strong for AA002. When I compared fixed windows of 1, 5, and 10 minutes, the performance was relatively similar, with the 5-minute and 10-minute windows only slightly better than 1 minute. This suggests that, for this participant, the strongest beacon already captures much of the room-level location information.

Second, I tested whether step count could improve the location estimate by controlling the window size adaptively. I tried two adaptive-window approaches:

1. Step-count adaptive window  
   The algorithm uses a longer RSSI window when step count is low, and a shorter RSSI window when step count is higher. For example, if the 10-minute step count is very low, the algorithm uses a 10-minute RSSI window; if movement is higher, it falls back to 5-minute or 1-minute windows.

2. Step count + RSSI stability adaptive window  
   I then added RSSI stability, so that a long window is only used when both movement is low and the RSSI signature is stable. I measured RSSI stability using the proportion of time the same beacon is strongest, and the gap between the strongest and second strongest beacon.

However, neither adaptive-window method improved the overall accuracy compared with the best pure RSSI baseline. The pure 10-minute strongest-beacon RSSI baseline remained slightly better.

That said, step count still seems useful. When I filtered for low-motion windows, RSSI-based location estimates became much more reliable. For example, 10-minute windows with very low step count achieved much higher accuracy than the overall RSSI baseline. This suggests that step count may be more useful as a confidence or stability indicator, rather than as a direct way to improve every location estimate.

My current interpretation is that the algorithm can estimate location mainly from RSSI, while movement information may help indicate when the estimate is more or less reliable. For example, low step count and stable RSSI could indicate a high-confidence location estimate, while higher movement or unstable RSSI could indicate lower confidence or a possible transition period.

I wanted to ask your advice on the next direction. Do you think I should revise the adaptive-window algorithm further, for example by changing the thresholds or the way RSSI stability is used? Or would it be better to try replacing step count with accelerometer-derived movement features, since acceleration may capture non-walking movement better than step count?

My current thought is that acceleration may provide a more sensitive movement measure, especially for detecting small movements or transitions that step count misses. But I would appreciate your guidance on whether the next step should focus on improving the step-count algorithm, moving to accelerometer features, or treating movement mainly as a confidence measure for RSSI-based location estimates.

# 2026-05-25 Derek

Thanks for your email. Great to hear your progress. 

I have some questions. 

1. How are you determining accuracy?  In the data I let you have, there is no reference of correct location. The annotation file you have is based on a max RSSI algorithm, without using step count.  We do have some data with reference data.
2. The data set I gave you is quite “clean”.   There are other datasets with more ambiguity of RSSI values, so including step-count is likely to help in those.

I will try to send you links to some more data for you to look at with your algorithms and see if we see more difference. 

# 2026-05-26 czg

Thank you very much for your comments. They were very helpful, especially your point about how the existing annotation file should be interpreted.

I realise now that I should not describe the previous results as true location accuracy. In my analysis, I was using the existing annotator.json labels as the reference for comparison, so the value I reported was really the agreement between my algorithm output and the existing annotation file, rather than accuracy against an independent ground-truth location label.

After checking the annotation file more carefully, I found that it is not an independent manually verified location dataset. It is based on a max-RSSI approach, and it also contains intervals labelled using other sensors such as accelerometer and pressure. In addition, some labels are not simple room labels, for example Indoor transition, Out, and Unknown. My current algorithm is therefore only a simplified reimplementation using fixed sliding windows and strongest-beacon signatures, so it does not exactly reproduce the original annotation process. This helps explain why the agreement is around 66% rather than 100%.

So my current understanding is that the AA002 results are still useful for checking whether the algorithm behaves consistently with the existing RSSI-derived annotation, but they cannot show whether adding step count genuinely improves true location estimation. For that, I agree that data with independent reference location labels would be much more useful.

Regarding the second point, I think additional datasets with more ambiguous RSSI patterns would be very helpful. The AA002 dataset seems relatively clean, so the strongest RSSI signal already performs quite well, and step count mainly seems useful for identifying when the RSSI-based estimate is more or less reliable. With a dataset that has more ambiguity, and ideally independent reference labels, I could better evaluate whether step count or accelerometer features improve the location algorithm.

My next plan would be to apply the same workflow to the new data if available: first compare the RSSI-only baseline, then add step count or accelerometer-based movement features, and finally evaluate whether the fused method improves performance against the reference labels.