These slides are good.  

You have a done a lot of work and must ensure you are clear on:

1. The medical problem you are addressing
2. Objectives of work
3. State of the art
4. Your contribution
5. The extent you have met your objectives

There are two major issues I think you should address:

1. I don’t think it is clear what the underlying data source is. You need to explain clearly that you have a person (or people) wearable a bracelet that contains BLE module and motion sensors, and you have BLE beacons around the home. The beacons transmit BLE (RF) packets that the bracelet receives and that the Received Signal Strength Indication (RSSI) of these packets is a function of distance between beacon and bracelet.   You should have a diagram early on so people know what you are talking about. Otherwise there is a risk they won’t understand. 
2. You are not clear enough on what you have actually done.   Firstly explain what tools you used (python, codex) and secondly show how your algorithms process raw data. It would be great to show example raw data and processed results with a traditional max RSSI method, and with your new approach. 


More detailed  comments; 

## Method

1. You need to be clear that this is your work.  You have devised and implemented this pipeline.    You also need to make it more clear what you have done, that you have written code in python with help of codex etc. 

2. You might want to show some example sensor data to make this feel more real.  Otherwise the listener may not understand what you have done. 

## Results

1. The first results slide shows a significant improvement in accuracy, but it isn’t really clear what you mean by “raw” vs “corrected”.   If raw means a traditional highest RSSI approach, then make this clear. Your algorithm is better than standard algorithm on this annotated data in a clear way. 

2. Can you also anonymize the data. So talk about data set 1, dataset 2 etc. rather than DH Paris etc. 

3. Your case study slide is good, but you need to ensure people understand what it means. 