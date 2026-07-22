# MSc Final Report Writing Instructions for Codex

Working title:

**Combining Wearable Sensor and Environmental Beacon Data to Better Understand Lived Experience of Patients**

This title should guide the report framing. The report should present localisation, sensor fusion, co-presence, and behavioural metrics as methods for understanding lived experience, rather than as isolated engineering tasks.

## 1. Official PFR Requirements

This report must strictly follow the official MSc Project Final Report requirements.

The report should be written as a scientific thesis-style final report, not as a casual project summary. It must demonstrate:

* clear scientific context;
* high-quality data analysis and/or experimental work;
* appropriate project planning and management;
* clear research progress and contributions;
* honest discussion of limitations and conclusions;
* clear presentation, figure/table labelling, and referencing.

The report must include:

* Title Page;
* signed Declaration;
* approximately 200-word Abstract;
* main body of the report;
* References;
* Appendices if necessary.

The recommended structure is:

1. Abstract

[Write approximately 200 words. Briefly state the clinical/home-monitoring motivation, the dataset used, the main analysis pipeline, the key localisation/activity methods, the main quantitative results, and the most important limitation. Avoid citations in the abstract unless required.]

2. Introduction

[Introduce the broader problem: understanding lived experience at home using wearable sensors and environmental beacons. Explain why room-level location and activity information could be useful for patient monitoring, independent living, or behavioural analysis.]
2.1 Motivation
[Explain the motivation for combining wearable motion data and environmental beacon data rather than relying on a single sensor modality.]
2.2 Aim and Objectives
[State the overall aim in one sentence.]
• Objective 1: [Process and align raw RSSI, accelerometer and/or step-count data.]
• Objective 2: [Develop a baseline room-level localisation method using beacon RSSI.]
• Objective 3: [Incorporate movement information to improve or interpret localisation labels.]
• Objective 4: [Evaluate agreement with the existing annotation file and visualise spatial behaviour over time.]
2.3 Research Questions or Hypotheses
[Example: Can low-motion windows provide more stable RSSI signatures for room-level localisation? Does accelerometer magnitude provide a more useful movement feature than step count?]
2.4 Contributions of This Project
[Summarise the main technical and analytical contributions: data processing pipeline, motion-aware localisation approach, evaluation, and visualisation outputs.]
2.5 Report Structure
[Briefly describe what each chapter contains.]


3. Background

[Provide scientific context. This chapter should demonstrate that you understand the relevant literature and the limitations of existing approaches.]
3.1 Home Monitoring and Lived Experience
[Discuss why passive sensing in home environments is useful and what kind of clinical or behavioural information room-level location may provide.]
3.2 Wearable Sensors for Activity and Motion Analysis
[Review accelerometer, step count and other wearable sensing approaches. Explain their strengths and limitations.]
3.3 BLE RSSI and Environmental Beacon-based Indoor Localisation
[Explain RSSI, beacon signatures, room-level localisation, and common sources of noise such as body occlusion, multipath effects and beacon placement.]
3.4 Sensor Fusion for Location Estimation
[Explain why combining motion information with RSSI may improve interpretation, especially during stationary periods or transitions.]
3.5 Evaluation Challenges Without Independent Ground Truth
[Clarify that the existing annotation file should be treated as an existing reference annotation rather than an independent manually verified ground truth, if this is applicable to your dataset. Use the term agreement rather than accuracy when appropriate.]

4. Methodology

[This chapter should make your analysis reproducible. Describe the methods step by step and justify parameter choices.]

5. Results

[Present results objectively before interpreting them. Use figures and tables whenever they make the result easier to understand.]

6. Discussion

[Interpret the results and connect them back to the research questions and literature.]

7. Conclusions

[Summarise the project in 3-5 paragraphs. Clearly state what was achieved, what the main findings were, and what the key limitation is. Do not introduce new results here.]

8. Future Work

[Describe realistic extensions. Examples: using a real floor plan, incorporating additional sensors, improving RSSI vector modelling, applying supervised or semi-supervised learning, collecting independent ground-truth labels, or testing on more participants.]

9. References

[Use one consistent reference style. The official guidance suggests the Journal of Medical Engineering & Physics style unless your supervisor permits another style.]
[1] Author Initials. Surname, "Title of article," Journal Name, vol. X, no. Y, pp. xx-xx, year.
[2] Author Initials. Surname, Book Title. Publisher, year

10. Appendices

Appendix A: Code

Formatting requirements:

* A4 paper;
* 1.5 line spacing;
* 12-point Arial font;
* 2.5 cm margins on all sides;
* clear heading hierarchy;
* all figures and tables must be numbered, captioned, and referenced in the text;
* figure axes must be labelled with units where appropriate;
* use a consistent reference style, preferably the Journal of Medical Engineering & Physics style unless otherwise approved.

Word count:

* MSc report expected length: more than 8,000 words;
* maximum word count: 10,000 words;
* references and appendices do not count;
* figure captions and table captions do count;
* word count must not include the cover page.

Important terminology:

If the algorithm output is compared with the existing `annotator.json` file, do not call this “true accuracy” unless independent manually verified ground truth is available. Use:

* “agreement with the existing annotation file”;
* “agreement with reference labels”;
* “comparison with existing annotations”.

Avoid claiming “ground-truth accuracy” unless this is supported by independent ground truth.

---

## 2. Use LYH_Final_Report as a Style and Structure Reference

Use the previous MSc final report only as a writing and structure reference. Do not copy its wording.

Useful aspects to follow:

* The report should begin with a formal UCL-style title page, declaration, and abstract.
* The introduction should start from the broad application area, then narrow down to the specific research problem.
* The background section should explain the scientific and technical concepts needed to understand the methodology.
* The methodology section should be detailed enough for another person to reproduce the analysis.
* The results section should present objective findings with clear figures and tables.
* The discussion section should interpret the results, explain limitations, and connect back to the research aim.
* The conclusions section should summarise what was achieved without introducing new results.
* The future work section should be specific and realistic.
* Appendices should only contain supporting material such as code structure, extra figures, or detailed parameter settings.

For this project, the final report should not be written as “I made visualisations”. Instead, it should be written as a scientific data analysis project about combining wearable activity data and RSSI-derived location data to understand behaviour in the home.

---

## 3. Supervisor’s Intended Message for This Report

### 2026-06-17

1. Explain the application: better understand activities and behaviors including social interaction between multiple people
2. Your goal is to develop analysis and visualization methods for combination of activity and RSSI-derived location data
3. You explore different methods for integrating both the analysis and visualization of the multiple data sources
4. We need to consider metrics of success. I’ll try to get you some more data to help with this.

### 2026-06-29

I think you should spend some time working on the background. It is very important you provide scientific context and literature review, so you can put your work into this context.

There is lots of work on using BLE beacons to estimate location. The novelty of your work is around integrating multiple sensor data and looking at co-presence. 

It is important to explain the clinical context - why is it important to provide provide a combination of location in the home plus wearable sensor measures (activity level etc) to provide a more context-aware representation of lived experience of people with disease.  

Then draft some objectives, taking into account both the background and what you have achieved. 

You have described your method in stages. However it might be better to consider organizing the method (and results) in a way that makes sense wrt you background and objectives.  

You could talk about initial working on visualization of data processed using the “nearest beacon” approach and then developing novel methods to estimate location and evaluate them in a variety of setting. 

It is important you put the results into the context of the background (prior literature) and the objectives (including the clinical application) and describe next steps.

### 2026-07-02

You need to discuss the challenge of validating these location algoirthms as reference data has limitations: observation as a reference reduces the realism of the data; self-report is likely to have limited accuracy due to recall issues; so you are also using consistency and plausibility assessment by showing data to people it was collected from for qualitative assessment of credibility of the data

### 2026-07-12

Consider how the narrative of your algorithm development will be explained.  I realize you have done it all by “phase” but the report must describe it in terms of objectives and advances compared to state of the art.      So you might want to consider how you combine the different phases into a sections of a method, and sections of a results chapter in your thesis.  

### 2026-07-21

You need a clear statement of aims/objectives at the end of the introduction that links to what you describe in the results and refer back to in the discussion.

Codex record：

我看完了，先不改。我的判断是：`03_Background` 目前基本可以先保留，`02_Introduction` 需要微调更多，因为它还停留在“项目按阶段推进”的旧叙事，而 `04/05` 已经转向 unified pipeline 主线了。

建议调整这几处：

1. `02` 的 objectives 要从“多个方法”改成“一个可审计 pipeline”
   
   现在第 5 行还是：
   - preprocessing workflow
   - RSSI baselines
   - movement-aware / floor-aware methods
   - behavioural summaries
   - evaluation

   这个方向不差，但还没突出第八阶段主贡献。建议之后改成：
   - capability audit + five-minute common timeline
   - unified movement-supported RSSI pipeline
   - optional pressure / co-presence / behavioural branches
   - compare general pipeline against dataset-specific methods
   - evaluate with evidence-appropriate language

2. `02` 第 6-9 行的“iterative analysis pathway”太像阶段总结

   现在它从 earliest stage、Home_X001、later work、final stage 讲到 80h。这个和你导师 2026-07-12 的反馈有点冲突，因为看起来还是“我做了几个阶段”。

   建议保留一句简短的“the method was developed iteratively”，但不要逐阶段展开。可以改成更像：
   “Early analyses informed the final pipeline by identifying recurring problems: RSSI instability during low motion, missing RSSI during sleep, co-presence sensitivity, cross-floor ambiguity, and validation limits.”

3. `02` 里 “final stage extended...” 已经过时

   因为现在第八阶段才是核心，80h 不再是 final stage，而是 pressure branch / specialised downstream module 的对比案例。这里建议后面删掉“final stage”说法，避免和 `04/05` 冲突。

4. `02` 里 aim 目前可以保留，但最好加一点“不声称成熟完美”

   你说 pipeline 还不成熟，这个非常重要。Introduction 可以用稳妥措辞：
   “to develop and assess an auditable framework”
   而不是听起来像已经完成一个 fully validated system。

   比如 “analysis and visualisation methods” 可以微调成 “an auditable analysis framework and visualisation outputs”。

5. `03` 基本不用大改，但最后一句可以以后微调

   `03` 最后一句现在是：
   “Overall, this project uses interpretable BLE localisation as a foundation...”

   这句可以轻微改成：
   “This motivates an auditable pipeline...”
   
   这样和 `04` 接得更顺。但不急，`03` 现在没有明显问题。

6. `03` 还可以补一点 “general pipeline vs bespoke method” 背景

   因为 `05` 现在核心结果之一是 generality 有代价。Background 可以加一两句：real-world systems often need transferable, auditable methods, but dataset-specific tuning can improve performance at the cost of generalisability。这个会让 `05.6` 更自然。

7. 引用不用现在动

   如果只是这些轻微叙事调整，当前 `[1]-[7]` 大体还能用。等 `02/03` 最终文字稳定后再统一检查 reference 顺序比较好。

简短结论：  
`03` 是“可用，只需轻微衔接 unified pipeline”；`02` 需要从“阶段发展介绍”改成“clinical motivation + aim/objectives + final pipeline emerged from iterative problems”。这样它就不会和新的 `04/05` 打架。
