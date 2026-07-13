# SecondPhase

## 2026-05-18 Derek

What I really want you to do is work on raw data analysis. Rather than just doing visualization of the json files, I want you to recalculate location from the raw data.

I would like you to create an algorithm to use a combination of both beacon RSSI data AND​ movement data to label location,

The simplest measure movement is step count, so you could, start with that: When calculating position, you could use a sliding window to identify periods with very little motion (eg: fewer than n steps, where you can vary n to find a good performance) and in that period of time, identify the corresponding strongest beacon signature (simplest the beacon that has the highest proportion of time being lowest RSSI, but you could also try something that used the RSSI vector instead of lowest value). 

## 2026-05-20 Derek

Great description! Looks like you used some AI to help you write that description, which is fine.   

There is plenty more data for you to look at in due course. 

The one additional point you might want to look at is analysis of data from two people simultaneously. But I agree with the initial steps you propose.

## 2026-05-25 Derek

Thanks for your email. Great to hear your progress. 

I have some questions. 

1. How are you determining accuracy?  In the data I let you have, there is no reference of correct location. The annotation file you have is based on a max RSSI algorithm, without using step count.  We do have some data with reference data.
2. The data set I gave you is quite “clean”.   There are other datasets with more ambiguity of RSSI values, so including step-count is likely to help in those.

I will try to send you links to some more data for you to look at with your algorithms and see if we see more difference. 

# ThirdPhase_X001

## 2026-06-08 Derek

I’ve uploaded some more data. This has no reference but is an interesting comparator. Can you try to download and start analyzing? There are two people with the same beacon configuration. 

The beacon labels are given below in the screenshot.

Let me know how you get on - and if you have any questions. I have more data I can find for you after this. 

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

### Part 1

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

### Part 2

#### Derek

I would like you to do some more analysis and visualization - see my points above.     

I am preparing some more data for you.   

In parallel, you should be starting to write the report outline for me to review. 

### Part 3 

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

Thanks for all this additional work. You are beginning to have interesting result now - and with the new data I’ve sent you links to, you can potentially measure accuracy of location (in general there isn’t colocation in all that data, but there is location so you an assess accuracy of location for each dataset for your different algorithms and we can try to decide which algorithm

Now that you are able to process data effectively,l we need to look at statistical measures as well as visualizations.

Here are some specific comments. 

### Part 1

For comparing different location algorithms you can look either at the location time series plots, or the co-occurance bar charts. They are two different ways of displays similarities and differences between algorithms. I think you should try to display all algorithms together. You can’t, however, draw many conclusions from a single dataset, which is one reason I wanted you to have more data to look at. 

### Part 2

I think your cluster approach is very interesting, but  you might want to consider making the clustering model using data from both SUBJECT and STUDY_PARTNER together - they are in the same space, and it would be interesting to see how much difference there is if you use a single cluster for both compared to separate clusters for each. 

### Part 3

I don’t understand your confidence score heat map. 

### Part 4

This representation is helpful (I’m just showing one example —— 4a fixed 30min RSSI). However, I dlno’t understand how the co-presence line is consistent wit the other data. Looking at the Subject and Study-partner plots, you can see that there is mis-labelling of bedroom vs bathroom for Subject, with this algorithm, yet the co-presence doesn’t show that. Can you look again?

### Part 5

The tables that summarize co-presence by window size are a good way of showing overall agreement between the algorithm - and you should quantify these. You can look at measures o agreement between the approaches. If you can process the data I sent you where there are hand annotations, you can also look at measures of positive and negative percent agreement between your algorithms and 

# SixPhase

## 2026-07-01 Derek

This data(data-80 hour single user) in someone in a home with 2 floors. What you could try to do here is use the pressure sensor to work out which floor someone is one.

Each beacon has a pressure value
The bracelet has a pressure value
Difference in pressure between beacon and bracelet

When working out the closest beacon, it may be that a beacon the floor above or floor below has highest RSSI (if the floor is just wood for example) but the pressure sensor enables you to also look at pressure difference between beacon and bracelet.  

Note: when you look at pressure difference, you need to first remove any spikes and then consider the window width

It would be very interesting if you could also look at this pressure data in your algorithm as an additional type of novelty

## 2026-07-05 Derek

In your final presentation and report, you will want to describe the challenge - indoor navigation and co-presence detection, using fusion wearable sensor data and environment beacon data, and describe the different approaches.

Two additional peace of work you are now quite close to is:

1. Quantifying stair-climbing (number of ascent / descent and time per ascent/descent)
2. Measuring room transitions per day (number of room transitions per day)

Of course these only apply indoors when we have beacon data.   We may want to therefore normalize these to the number of hours indoor (number of room transitions per waking hour indoor), for example:

The floor transitions associated with accelerometer signal are of course results of going up or down stairs. You can, therefore, make some interesting measurements:

1. Number of stair climbs per day (assent and descent) 
2. Time taken to ascend /descend).  This latter measure is a really interesting one of mobility. It would be great if you could try to find these events in the data.

You can use a similar approach to looking a rom transitions: changes between rooms (whether on same or different floor) associated with physical activity (from acceleration).   We will have some room transitions that are associated with change in RSSI but without significant movement. We want to ignore these, and focus on those room transitions that are associated with movement eg: at least 10 steps or some measure of acceleration magnitude . 

So it would be great if you could move to the next stage of using the data to quanitfy these metics of behavior 

I have quite a large amount of additional data I could let you look at from people with dementia if you have some evidence of this working. 

# SeventhPhase

## 2026-07-07 Derek

These should be interesting for you to look at as there is misclassification of night-time location as a result of beacon issue. If you combine the beaconRSSI and movement you might improve this and I’d like you to have a look. 

### EF-001

![EF-001](../Data/EF-001/EF-001.png)

This dataset had variability in beacon signal at night that results in the closest beacon moving to an adjacent room.  Because there is very little movement you should be able to correct for this with your algorithm that combines RSSI and movement. 

In this data, you can observe the sleep state during the night, but the location corresponding to the highest RSSI keeps changing.

### EF-002

![EF-002](../Data/EF-002/EF-002.png)

The challenge in this case is that, during the night sleep, the wearer can turn over in the bed and obscure the beacon signals entirely. There is virtually no movement in this time so they don’t move room. Hopefuly you can get your algorithm to identify to 

## 2026-07-12

### Part 1

I do think you could improve clarity of your achievements by refining some of the plots.  The figures for EF001 on page 8, and EF002 on the top of page 12 may not be as clear as they could be because you have a week of data displayed in one go, and it is too small to really see what your algorithm does and why it is better. . Displaying each 24 hour period separately could be much more clear.  For  example you could stack each 24 hour period the width of the page with the two algorithms, rather than the full 7 days.  What  you want to do is show a figure that indicates the the raw 5mm strongest RSSI gives room transitions that are implausible and are corrected by your algorithm. And you need a figure caption that clearly explains the take-home-message of the figure. 

### Part 2

I want you to think about whether you can explain your approach conceptional more clearly.  For example, I section 2 you show a plot of ACC magnitude std aligned with mean RSSI.   What do these two things meaning intuitively? And why are they the correct things to plot?  It is fine for you to use Codex to help you write analysis and to suggest algorithms, but you need to reflect on whether what codex proposes seems sensible. You could of course suggest that codex does something slightly different (which might be better for your project).   

For example, if what we are looking at is implausible room transitions, not might be interesting to plot room transitions against acceleration magnitude, focusing on    periods  during the night in which acceleration magnitude is low, so plotting acceleration magnitude against change in beacon with highest RSSI might help illustrate that issue.   The mean RSSI doesn’t tell you about transitions, but more how close the participant is to a beacon. And I you could more clearly explain why you chose std of accel magnitude as a measure of stillness. To a first approximation, mean acceleration magnitude during a window would seem a measure of still ness - and the std of that imight not be stillness. If you feel it is right to keep the current plot then please explain more clearly why it communicates something useful. 

Similarly you introduce concepts such as the log-space boundary without explaining what this is or why you have chosen it. 

Are you using fixed windows or sliding window?  What are the pros and cons of those two approaches?

You have refined your approach on this data compared to what you did on prior data. 

# EighthPhase

## 2026-07-12 Derek

However, what we ideally want is a single analysis framework that provides the best output across the range of different challenges. Are you able to test algorithms across all the datasets and then evaluate which might work best for certain cases, and which might work best overall?

So key issues:

1. You are not solving a series of different problems, but trying to generate a location algorithm that addresses a range of challenges with RSSI data, by incorporating other sensor data (motion sensor, steps, pressure).
2. Try to explain why your choice of metrics for the various algorithms makes sense.
3. Clearly show the benefit of your algorithm either against a reference, or by saying you are correcting for implausible location changes and illustrate how you have corrected these. Use captions of figure, or zoom-ing in to clearly articulate the improvement
4. It would be interesting to generate a combined analysis approach and try on all datasets - or if this isn’t possible, explain how such a unified analysis approach could be developed.