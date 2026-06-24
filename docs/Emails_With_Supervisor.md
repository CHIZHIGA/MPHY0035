# SecondPhase

## 2026-05-18 Derek

What I really want you to do is work on raw data analysis. Rather than just doing visualization of the json files, I want you to recalculate location from the raw data.

I would like you to create an algorithm to use a combination of both beacon RSSI data AND​ movement data to label location,

The simplest measure movement is step count, so you could, start with that: When calculating position, you could use a sliding window to identify periods with very little motion (eg: fewer than n steps, where you can vary n to find a good performance) and in that period of time, identify the corresponding strongest beacon signature (simplest the beacon that has the highest proportion of time being lowest RSSI, but you could also try something that used the RSSI vector instead of lowest value). 

## 2026-05-20 czg

Thank you for your suggestions. I have thought more about the next step, and my understanding is that the main aim should be to move beyond visualising the existing annotation JSON files and instead recalculate room-level location directly from the raw sensor data.

My plan is to focus on AA002 first. I would first compare different ways of representing the raw beacon RSSI data, since this is the main spatial signal for room-level location. One simple approach is to use summary features, such as the strongest beacon, mean RSSI, maximum RSSI, signal ranking, or the difference between the strongest and second strongest beacon. Another approach is to use the full RSSI vector across all available beacons, which may preserve more information about the room-level signal signature. I can compare these RSSI representations against the existing room-level annotations to see which gives better location estimates.

After establishing an RSSI-based baseline, I would then combine RSSI with movement information. I would start with step count, as this is the simplest movement measure. For each sliding time window, step count can be used to identify low-motion periods, where the RSSI signature is likely to be more stable and informative for room-level location.

I would also like to make the sliding window adaptive rather than fixing it only by time of day. The algorithm could start from a short base window and expand the window when the data suggest a stable state, for example low step count, low acceleration variation, and a stable RSSI signature. If movement increases or the RSSI pattern changes quickly, the algorithm would use a shorter window to capture possible room transitions. In this way, longer windows would naturally occur during sleep or other low-motion periods, while shorter windows would be used during active or transitional periods.

After the step-count baseline, I would like to test accelerometer-derived features as well. Step count is simple and interpretable, but acceleration may capture non-walking movement. Therefore, I would like to compare RSSI only, RSSI with step count, RSSI with accelerometer features, and RSSI with both step count and accelerometer features.

The existing room-level annotations can be used as reference labels for evaluation. I can compare the estimated location against the annotated location using measures such as accuracy and a confusion matrix. This would allow me to assess which RSSI representation and which combination of movement features performs best.

In the later stage, I would also like to explore a supervised machine learning approach, where RSSI features, step count, and accelerometer features are used as input features, and the annotated room-level locations are used as training labels. This would allow me to evaluate whether a fused model can improve room-level location estimation compared with simpler rule-based or feature-based methods.

Overall, my planned direction is to first compare RSSI representations, then build an interpretable sliding-window baseline using RSSI and movement data, and finally explore whether a machine learning model can improve the robustness of room-level location estimation.

## 2026-05-20 Derek

Great description! Looks like you used some AI to help you write that description, which is fine.   

There is plenty more data for you to look at in due course. 

The one additional point you might want to look at is analysis of data from two people simultaneously. But I agree with the initial steps you propose.

## 2026-05-24 czg

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

## 2026-05-25 Derek

Thanks for your email. Great to hear your progress. 

I have some questions. 

1. How are you determining accuracy?  In the data I let you have, there is no reference of correct location. The annotation file you have is based on a max RSSI algorithm, without using step count.  We do have some data with reference data.
2. The data set I gave you is quite “clean”.   There are other datasets with more ambiguity of RSSI values, so including step-count is likely to help in those.

I will try to send you links to some more data for you to look at with your algorithms and see if we see more difference. 

## 2026-05-26 czg

Thank you very much for your comments. They were very helpful, especially your point about how the existing annotation file should be interpreted.

I realise now that I should not describe the previous results as true location accuracy. In my analysis, I was using the existing annotator.json labels as the reference for comparison, so the value I reported was really the agreement between my algorithm output and the existing annotation file, rather than accuracy against an independent ground-truth location label.

After checking the annotation file more carefully, I found that it is not an independent manually verified location dataset. It is based on a max-RSSI approach, and it also contains intervals labelled using other sensors such as accelerometer and pressure. In addition, some labels are not simple room labels, for example Indoor transition, Out, and Unknown. My current algorithm is therefore only a simplified reimplementation using fixed sliding windows and strongest-beacon signatures, so it does not exactly reproduce the original annotation process. This helps explain why the agreement is around 66% rather than 100%.

So my current understanding is that the AA002 results are still useful for checking whether the algorithm behaves consistently with the existing RSSI-derived annotation, but they cannot show whether adding step count genuinely improves true location estimation. For that, I agree that data with independent reference location labels would be much more useful.

Regarding the second point, I think additional datasets with more ambiguous RSSI patterns would be very helpful. The AA002 dataset seems relatively clean, so the strongest RSSI signal already performs quite well, and step count mainly seems useful for identifying when the RSSI-based estimate is more or less reliable. With a dataset that has more ambiguity, and ideally independent reference labels, I could better evaluate whether step count or accelerometer features improve the location algorithm.

My next plan would be to apply the same workflow to the new data if available: first compare the RSSI-only baseline, then add step count or accelerometer-based movement features, and finally evaluate whether the fused method improves performance against the reference labels.

# ThirdPhase_X001

## 2026-06-08 Derek

I’ve uploaded some more data. This has no reference but is an interesting comparator. Can you try to download and start analyzing? There are two people with the same beacon configuration. 

The beacon labels are given below in the screenshot.

Let me know how you get on - and if you have any questions. I have more data I can find for you after this. 

## 2026-06-09 czg

I have carried out an initial exploratory analysis of the new Home_X001 dataset and exported today’s work log as a PDF. Since this dataset does not have reference location labels, I treated the analysis as descriptive rather than as a formal accuracy evaluation.
So far, I have checked the data availability for the left-wrist and right-wrist devices, summarised the RSSI beacon detections, extracted 10-minute step count and accelerometer movement features, and compared the two devices over their shared recording period. The aim was to understand whether the dataset is usable and how the RSSI and movement patterns behave before applying the algorithm more formally.
I would like to arrange a meeting with you to discuss the next steps. In particular, I would like your advice on:
Which comparison analyses would be most valuable for the X001 dataset.
How best to apply the RSSI + movement algorithm to datasets without reference labels.
Whether the next datasets you mentioned may include reference location labels, and whether I should continue developing the algorithm following the direction we discussed previously.
I also wanted to let you know my upcoming project deadlines. I have a poster presentation on 12 June, my FYP presentation/defence is on 23 July, and the final dissertation submission deadline is before 31 July. It would be very helpful to discuss the analysis direction soon so that I can plan the remaining work clearly.
Would you be available for a meeting sometime this week or early next week?

# ForthPhase

## 2026-06-10 Derek

Thanks for sending this through. Great to see you making progress. Can you tell me what tools you are using for this analysis? It is very important in your masters project that you describe the tools you use (Claude code or whatever) and how you sed them. When using AI tools, you need to design some tests to confirm that the results are as expected - it is easy for AI tools not to work as needed.

In this case I know a bit about the data and so this is what I want you to do,

1. This is not one person wearing two bracelets, but two people each wearing one bracelet (it is the “subject type” that is the important one).

2. You are correct that you should only use the period of 170 hours when the datasets overlap. One bracelet collects for longer than the other.

3. Because there are two people, we can look at how much time they are together; it isn’t left/right comparison that is interesting, but Subject/Study-partner comparison.

   a. Time together in the home

      - Same location in home  
      - Different location in home

   b. In home, one away from home

   c. Both away from home.

4. The work you have done with beacon algorithms is very interesting. I want you to extend that. I want you to look at different ways of calculating locations.

   a. Closest beacons over 10 mins, and also 5 mins and 30 mins

   b. Combine movement with beacon data – so have the window length depend on movement. You could look at varying window lengths for calculating location from 1–30 mins depending on how many steps are in that period. You could try different step thresholds, so for example define “stationary” as:
      - 1 or fewer steps in the window
      - 2 or fewer steps in the window
      - 5 or fewer steps in the window
      - 10 or fewer steps in the window

   c. Use an automatic clustering approach: you can identify location using the combination of beacon data. You want to ignore periods where there is lots of movement (step count or acceleration magnitude is high) and just look at periods with little movement. You can then find distinct location clusters that are based on RSSI values during periods of non-movement. You can then process all the data (including when movement occurs) to generate a location timeline.

   d. Feel free to adapt these approaches or use different ones, or one that a LLM proposes. Ensure you justify your choice.

5. Generate an integrated timeline showing location (based on the different algorithms above).

   a. SUBJECT

   b. STUDY_PARTNER

   Show location for each on the timeline so we can see when together and apart. Measure those metrics of time together / apart by location.

Then let me see the data and I will comment on it

I want the key message of your report to be about using combination of movement and RSSI to estimate location. We don’t have much “gold standard” data but we have some we can le you have if you make progress on this work.

Another approach I would like you to use is to additionally use the pressure sensor data in identify which floor someone is in in the house- both beacon and bracelet contain pressure sensors, and you can try to use this information to work out which floor someone is in. The data you currently are using is in an apartment so there is only one floor but I can let yo have more data after you’ve done work with teh love.

## 2026-06-15 czg

I have attached my current Fourth Phase progress report for the Home_X001 dataset. Based on your previous feedback, I focused on using RSSI together with movement data to estimate location and co-presence patterns for SUBJECT and STUDY_PARTNER.

Since this dataset does not currently have independent reference location labels, I have treated the results as descriptive estimates rather than formal validation. The report includes the fixed-window RSSI baseline, the step-adaptive RSSI method, exploratory low-motion RSSI clustering, and integrated visualisations comparing these approaches.

I would appreciate your feedback on whether this framing is appropriate, and whether the next step should be to refine the step-adaptive method, add accelerometer features, or wait for data with reference labels for more formal evaluation.

## 2026-06-15 Derek

The sort of plot you have below could b looked at in more detail(Home X001 ForthPhase Point 5: Method comparison timeline).  

I suggest you do one line per day and then put the days one on top of the other so we have a timeline over the week, one day at a time.

You could present the information in the  following ways:

1. One line per day, showing co-presence. This should make it easier to see patterns in the data within and between days.
2. 2 lines per day: showing location calculation (so you could see at a glance which location each participant was in)
3. Trying to include some measure of physical activity to the plot (this only works for one line per person)  It is hard to do this with color alone, but you could modulate the width of the line with some measure of activity like step-count per minute or average acceleration magnitude per a minute

You can generate these representations  for the different ways in which you calculated locations

In particular we want to identify periods of time / locations where the different location algorithms give different answers and try to better understand that - and we can review these data representations and see which are most consistent with the collected data.   Let me know if you have any questions. 

## 2026-06-17

### Note1

#### czg

Following your feedback on the timeline visualisations, I have prepared a new set of single-day line figures for Home_X001. I focused on 14 January 2026, because this day has relatively clear mapped RSSI coverage, so the line patterns are easier to inspect.
In the attached document, I have separated the figures into two groups:

1. Showing co-presence
This compares the estimated together/apart states across the different methods.
2. Showing location calculation
This shows SUBJECT and STUDY_PARTNER estimated locations, with line width representing step-count activity.

I included the fixed RSSI methods at 5, 10, and 30 minutes, the step-adaptive RSSI method, and the low-motion RSSI clustering method. My current interpretation is that the step-adaptive RSSI method is the most useful main method, because it combines movement and RSSI in an interpretable way. The clustering method is useful as an exploratory signal-state analysis, but seems less suitable as the main room-level location method.

#### Derek

I have some questions.

1. Display of multi-day data

I would like you to draw one line per day, not just show a single day. The co-presence plot should have one line per 24 hour period, so if there are 3 days, there would three lines one above the other. The location calculation should have a pair of lines (for subject and study partner) for each day.

It is best to displays lines from mid-day to mid-day not midnight to midnight, as then the sleep period is uninterrupted.  This is important as the night time patterns are a useful validation point: if there are lots of room changes while sleeping this is not correct!  

2. I do not understand your algorithms. 

Can you please give more detail on how you calculate the ste-padaptive RSSI and the low-motion RSSI-clustering.    

3. Please explain how you calculate the plots with the line thickness modulated by activity: 

Are you using step data for that? If so. How?
Some results appear inconsistent of different variants of your algorithm. For example look at 4b and 4c for study partner. 

How can the grey periods (which means no beacons visible because the person is away from home) become blue (meaning in the bathroom)?


4. The data I gave you was quite difficult and I thought it would be good at showing differences between algoirthms. 

Please keep working on this dataset and I’ll also get you some more to look at. 

### Note2

#### czg

I would appreciate your advice on whether this is the right direction for the final analysis, and what you think the next step should be. In particular, I would be grateful for your guidance on whether I should refine the step-adaptive method further, add accelerometer features, or focus more on preparing the final report with the current results.

#### Derek

I would like you to do some more analysis and visualization - see my points above.     

I am preparing some more data for you.   

In parallel, you should be starting to write the report outline for me to review. 

### Note3 

#### czg

I also wanted to note the remaining module deadlines:
- Project Talks slides submission: 17:00, Wednesday 22 July 2026
- Project Talks: Thursday 23 and Friday 24 July 2026
- Final Report submission: Friday 31 July 2026
I am planning to start writing the report gradually now. Although the analysis is still developing, my current plan is to begin structuring the report around the completed work and update it as the project progresses. I would really appreciate any advice you have on how best to frame the report and which results should be prioritised.

#### Derek

I think the message of the report should broadly be:
1. Explain the application: better understand activities and behaviors including social interaction between multiple people
2. Your goal is to develop analysis and visualization methods for combination of activity and RSSI-derived location data
3. You explore different methods for integrating both the analysis and visualization of the multiple data sources
4. We need to consider metrics of success. I’ll try to get you some more data to help with this.

# FifthPhase

## 2026-06-24 Derek

I’ve uploaded more data

In this folder there is data that includes in in each case a reference location in a separate analysis folder. So the raw data folders should be linkable to the analysis folders. In general there is only one person in each data set, though there is one or two with two people. 

Have a look and let me know if you have any questions. This should enable you to evaluate which of your algorithms is most accurate against self-report location. 
