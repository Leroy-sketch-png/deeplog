# Findings from DeepLog and ByeBye

**Paper review for Wednesday knowledge sharing**  
**Assigned papers:** DeepLog (CCS 2017) and ByeBye (Stanford CS231n project report)  
**Related finding included:** Lifelong Anomaly Detection Through Unlearning (CCS 2019), a direct continuation of the DeepLog research direction

---

## Executive Summary

The two assigned papers address different engineering problems but share a similar design pattern: both combine specialized components into an end-to-end workflow and evaluate the resulting system through practical experiments.

**DeepLog** applies LSTM-based sequence modeling to system logs. It detects anomalies from log-key sequences and parameter values, then uses workflow information to support diagnosis. The paper reports strong HDFS results, including a 96% F-measure and a 99.994% anomaly detection rate under a selected top-*g* configuration. Its results depend on reliable log parsing, meaningful sequence identifiers, representative normal training data, and trusted logs.

**A directly related 2019 CCS paper, Lifelong Anomaly Detection Through Unlearning,** develops the post-deployment update problem beyond DeepLog’s limited false-positive adaptation. It adds controlled unlearning for false negatives, relearning for false positives, and memory-based regularization. This successor is relevant because it clarifies which parts of DeepLog remained active research questions after 2017.

**ByeBye** combines object detection, segmentation, inpainting, pose extraction, and image generation to remove a person from video and insert a stylized character. Its experiments show a clear quality-efficiency trade-off: OpenCV Telea performs best on the reported SSIM, LPIPS, and runtime measurements, while the authors find LaMa more visually coherent in difficult background regions. The pipeline remains frame-based, so temporal consistency is improved through parameter tuning rather than guaranteed by the architecture.

The main practical lesson is that both papers demonstrate useful engineering approaches within controlled evaluation settings. Their results are informative for prototyping and system design, but should not be treated as production guarantees without additional validation.

---

# 1. DeepLog

## 1.1 Purpose and Approach

DeepLog treats a system log as a structured sequence rather than a collection of independent messages. Raw log entries are parsed into:

- a **log key**, representing the message template;
- a **parameter-value vector**, containing values such as identifiers, elapsed time, and operational metrics.

The system contains three main components:

1. **Log-key anomaly detection:** an LSTM predicts the next likely log key from recent log history.
2. **Parameter-value anomaly detection:** separate models identify unusual parameter or timing behavior.
3. **Workflow-based diagnosis:** workflow information helps users investigate an anomaly after it is detected.

This design allows DeepLog to identify both unexpected execution sequences and unusual values within otherwise familiar log events.

## 1.2 Main Findings

### Strong performance on structured log data

On the HDFS dataset, DeepLog was trained using less than 1% of normal log entries and evaluated on the remaining data. The paper reports:

- an overall **F-measure of 96%**;
- **99.8%** coverage of normal next-log-key observations within the predicted top five keys;
- a **99.994% anomaly detection rate** for the selected top-*g* configuration, with one anomalous session missed.

These figures represent different measurements and should be reported separately. The strongest overall result is that DeepLog achieved a better F-measure than the evaluated PCA, invariant-mining, TF-IDF, and n-gram baselines. Some baselines performed better on individual error counts. For example, PCA produced fewer false positives in the reported HDFS comparison, but substantially more false negatives.

### Detection uses more than log-message order

DeepLog does not rely only on log-key sequences. Its parameter-value models can identify unusual timing or value patterns. This broadens the range of detectable conditions beyond unexpected execution paths.

### Diagnosis is included in the system design

The workflow component provides contextual information after an anomaly is detected. This is useful because anomaly detection alone does not explain the underlying execution path or likely source of failure.

### Limited online adaptation is supported

If a detected anomaly is confirmed by a user to be a false positive, DeepLog can use that labeled normal case to update its model incrementally. In the paper's OpenStack experiment, this mechanism reduces false-positive rates compared with using the original static model.

## 1.3 Conditions Behind the Results

### Reliable sequence grouping

HDFS provides a `block_id` that groups related log entries into a sequence. This helps separate events from concurrent tasks. A production system without a reliable request, session, trace, or transaction identifier may require additional correlation logic before applying the same approach.

### Stable and effective log parsing

DeepLog depends on converting raw logs into consistent log keys and parameters. New templates, changing message formats, or parser errors can alter the representation seen by the model.

### Trusted logs

The paper assumes that logs are secure and that an attacker cannot modify log integrity or change the source code's logging behavior. As a result, the evaluation does not cover log deletion, fabrication, suppression, or deliberate manipulation.

### Representative normal training data

The model learns normal behavior from the available training sample. Legitimate patterns absent from training may be reported as anomalies until they are reviewed and incorporated.

## 1.4 Feedback and Ground Truth

DeepLog clearly describes how an operator can correct a false positive after the system raises an alert. The paper is less specific about how operational false negatives would be discovered and confirmed, because those events were not raised by the detector.

The workflow component helps diagnose detected anomalies, but it does not independently identify missed anomalies. A production implementation would therefore need an external ground-truth process, such as incident reviews, security investigations, service-level failures, or comparison with other monitoring systems. It would also need controls for label review and auditability before feedback is used to update the model.

This is an operational consideration rather than a contradiction in the paper. The paper demonstrates the model-level feedback mechanism, not a complete governance process for human labels.

## 1.5 Practical Takeaways

DeepLog is most applicable when:

- logs can be parsed into stable templates;
- events can be grouped into meaningful sequences;
- normal operational data are available for training;
- the logging pipeline can be trusted;
- alerts can be reviewed by knowledgeable operators.

For a production implementation, useful additions would include parser-drift monitoring, trace or session correlation, model-version tracking, feedback approval, rollback support, and evaluation on local logs before deployment.

---

# 2. Follow-up to DeepLog: Lifelong Anomaly Detection Through Unlearning

## 2.1 Why this paper is relevant

The assigned DeepLog paper already includes incremental updating when a user confirms that a detected anomaly is a false positive. A later CCS paper by Du et al. formalizes this broader post-deployment problem as **lifelong anomaly detection**. It is a direct continuation of the DeepLog research direction and uses DeepLog as the HDFS baseline.

Including this paper is useful for two reasons:

- it shows how the original approach was extended after 2017;
- it separates limitations that remained open from limitations that later work partially addressed.

The 2019 paper does not make DeepLog irrelevant. DeepLog remains the architectural baseline for sequence-based log anomaly detection and diagnosis. The follow-up mainly strengthens the model-update lifecycle.

## 2.2 Main Extension

The follow-up considers a deployed zero-positive detector that later receives a small number of labeled mistakes:

- **false negatives**, where an anomalous case was accepted as normal;
- **false positives**, where a normal case was reported as anomalous.

Its update framework includes:

- **unlearning** for false negatives, reducing the model's probability that the reported case is normal;
- **relearning** for false positives, increasing the probability that a corrected normal case is accepted;
- a bounded loss and smaller learning rates to control unstable updates;
- regularization based on an important memory set to reduce catastrophic forgetting.

This is broader than DeepLog's documented online update path, which is centered on false-positive feedback for detected anomalies.

## 2.3 Reported Results

On the paper's HDFS comparison:

- the static baseline reports 877 false positives, 922 false negatives, and F1 of 0.947;
- the retraining baseline reports 21 false positives, 2,236 false negatives, F1 of 0.928, and a runtime of 1,736.42 seconds;
- UNLEARN reports 157 false positives, 32 false negatives, F1 of 0.994, and an average update time of 1.12 seconds.

The comparison supports efficient incremental correction within the authors' setup. It should not be read as proof that this method outperforms every possible retraining strategy. The retraining baseline is constrained by the zero-positive design and does not incorporate false negatives in the same manner as UNLEARN.

## 2.4 What Remains Open

The follow-up improves the update mechanism but does not supply a complete operational ground-truth process. Manually reviewed labels are treated as authoritative. The paper does not evaluate malicious feedback, systematic labeling errors, disagreements between reviewers, or delayed confirmation.

It also does not remove DeepLog's broader implementation dependencies. Reliable parsing, meaningful sequence construction, telemetry integrity, and representation stability remain important. The paper's update controls reduce observed instability and forgetting, but its own ablations show that poorly selected learning rates or bounds can significantly increase false positives.

## 2.5 Updated View of the DeepLog Lineage

The combined finding is:

1. **DeepLog (2017)** establishes sequence-based log anomaly detection, parameter-value analysis, workflow diagnosis, and limited false-positive adaptation.
2. **Lifelong Unlearning (2019)** formalizes post-deployment correction and supports both false-negative unlearning and false-positive relearning.
3. The later work improves model maintenance but does not fully resolve label governance, telemetry trust, parser drift, or changing log semantics.

---

# 3. ByeBye

## 2.1 Purpose and Approach

ByeBye is a modular pipeline for removing a person from video frames and inserting a stylized replacement character. It combines existing models rather than training a new end-to-end architecture.

The pipeline uses:

- **YOLOv8** for person detection;
- **Segment Anything Model (SAM)** for segmentation masks;
- **OpenCV Telea or LaMa** for background inpainting;
- **OpenPose** for pose extraction;
- **Stable Diffusion with ControlNet** for pose-conditioned character generation;
- optional **LoRA** weights to reinforce a specific character style;
- mask-based compositing to place the generated character into the scene.

The experiments use a subset of DAVIS videos containing one prominent human subject. Frames are processed independently.

## 2.2 Main Findings

### Lightweight detection and segmentation provide a useful trade-off

The paper finds that YOLOv8s and SAM-ViT-B provide sufficient masks for the evaluated single-person scenes while reducing computational cost relative to larger variants. This supports a practical design principle: the largest model at every stage is not necessarily required for a satisfactory end-to-end result.

### Telea leads the reported quantitative inpainting results

Across the reported average of 25 sequences, the paper gives the following results:

- **OpenCV Telea:** SSIM 0.964, LPIPS 0.057, and 46.2 ms/frame;
- **LaMa Dilated:** SSIM 0.954, LPIPS 0.079, and 182.1 ms/frame;
- **LaMa Multi-Pass:** SSIM 0.950, LPIPS 0.080, and 549.7 ms/frame;
- **LaMa Aggressive:** SSIM 0.943, LPIPS 0.084, and 886.5 ms/frame.

Telea therefore provides the strongest reported combination of SSIM, LPIPS, and runtime. However, the authors' qualitative inspection finds that LaMa, especially Multi-Pass, preserves background structure and texture more convincingly in difficult examples. The paper does not include a formal human-rating study, so the defensible conclusion is that automated metrics and the authors' visual assessment favor different methods.

### Parameter tuning improves the temporal metric

The pipeline generates each frame independently, which can cause changes in clothing, facial details, and style between adjacent frames. The authors use frame-to-frame LPIPS as a proxy for temporal consistency.

In separate parameter sweeps:

- `CFG = 9` produces the lowest reported **mean LPIPS** among the tested CFG values;
- `strength = 0.7` produces the lowest reported **mean LPIPS** among the tested strength values.

Neither setting has the lowest reported variance in its respective sweep. These results should therefore be understood as the best mean LPIPS values within the tested configurations, not as a general optimum.

### LoRA improves mean LPIPS but introduces visual trade-offs

The report gives:

- without LoRA: mean LPIPS 0.1237 and variance 0.000633;
- with LoRA: mean LPIPS 0.1158 and variance 0.000661.

The lower mean indicates improved average adjacent-frame similarity. The printed variance is slightly higher, although the paper's prose describes it as lower. Qualitatively, LoRA improves clothing and style consistency but introduces noise and reduces facial fidelity.

## 2.3 Limitations

### Temporal consistency is not enforced by the architecture

Because each frame is generated independently, no temporal model explicitly preserves identity, clothing, motion, or background details across the video. Parameter tuning can reduce measured frame-to-frame differences, but it does not eliminate temporal instability.

### The demonstrated scope is single-subject video

The evaluation focuses on videos with one prominent person. Multi-person tracking, heavy occlusion, and complex interactions are not demonstrated in the reported experiments.

### Inpainting metrics do not provide exact background ground truth

SSIM and LPIPS can favor smooth local interpolation even when a reconstructed background is not semantically correct. This helps explain why Telea performs well numerically while the authors find LaMa more structurally convincing in some scenes.

### Visual replacement is not the same as anonymization

The paper evaluates image quality, temporal LPIPS, and runtime. It does not evaluate face recognition, gait recognition, re-identification, identity leakage, or formal privacy guarantees. ByeBye should therefore be described as a human-removal and stylized-replacement pipeline, not as a validated anonymization solution.

## 2.4 Practical Takeaways

ByeBye demonstrates the value of a modular pipeline for rapid experimentation. Individual components can be exchanged according to latency and quality requirements.

For further development, the most relevant improvements would be:

- tracking and identity management for multiple people;
- video-native diffusion or temporal conditioning;
- optical-flow or feature-based consistency checks;
- human evaluation alongside SSIM and LPIPS;
- privacy-specific evaluation if anonymization is an intended use case.

---

# 4. Comparison and Discussion Points

Although the papers address different domains, they offer several common engineering lessons.

## Modular system design

DeepLog and its 2019 follow-up separate parsing, sequence detection, parameter analysis, diagnosis, and controlled model updating. ByeBye separates detection, segmentation, inpainting, pose extraction, generation, and compositing. Modularity makes each system easier to evaluate and update, but also means that errors can propagate between stages.

## Evaluation depends on representation and metrics

DeepLog's results depend on how raw logs are parsed and grouped into sequences. ByeBye's conclusions depend on how image quality and temporal similarity are measured. In both cases, the reported metric is only meaningful when its input representation and limitations are understood.

## Human feedback remains important

DeepLog uses operator review to correct false positives, while the 2019 follow-up expands feedback to false-negative unlearning and false-positive relearning. ByeBye relies on qualitative inspection to identify cases where automated image metrics do not match perceived quality. Both papers show that automated metrics alone are insufficient for every engineering decision.

## Production use requires additional validation

Before either approach is used operationally, it should be evaluated on the intended environment, data distribution, failure modes, and governance requirements. The papers provide useful starting points, not deployment certification.

---

# 5. Suggested Points for Wednesday Sharing

1. **DeepLog's main contribution** is treating logs as sequences and combining log-key, parameter-value, and workflow information.
2. **Its HDFS performance is strong**, but the 96% F-measure and 99.994% anomaly detection rate are different measurements.
3. **Reliable parsing and sequence identifiers are important implementation requirements.**
4. **DeepLog supports false-positive feedback**, but a production solution still needs a process for establishing and reviewing ground truth, especially for false negatives.
5. **The 2019 successor extends DeepLog** with false-negative unlearning, false-positive relearning, and memory-based regularization, while leaving label governance and parser drift open.
6. **ByeBye demonstrates a practical modular video pipeline** using existing detection, segmentation, inpainting, and generative models.
7. **Telea wins the reported quantitative inpainting comparison**, while the authors find LaMa more convincing in difficult backgrounds.
8. **Temporal consistency remains the main technical limitation** because generation is frame-by-frame.
9. **ByeBye evaluates visual quality, not privacy guarantees**, so it should not be presented as a validated anonymization system.

---

# Conclusion

DeepLog shows that sequence modeling can provide effective log anomaly detection and useful diagnostic context when logs are structured, correlated, and trustworthy. The 2019 lifelong-unlearning follow-up extends the maintenance path to false-negative unlearning and false-positive relearning. Together, they motivate practical work on parser quality, sequence construction, feedback governance, controlled updating, and local validation.

ByeBye shows that an effective video-editing prototype can be assembled from modular off-the-shelf models. Its experiments clarify the trade-off between quantitative metrics, visual quality, and runtime, while also showing why video-native temporal modeling is needed for more stable output.

Together, the papers provide two useful examples of applied machine-learning system design: strong component selection and benchmark results are valuable, but production readiness depends on the assumptions, data pipeline, evaluation method, and operational controls surrounding the model.

---

# References

[1] M. Du, F. Li, G. Zheng, and V. Srikumar, “DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning,” *Proceedings of the 2017 ACM SIGSAC Conference on Computer and Communications Security*, 2017. DOI: 10.1145/3133956.3134015. https://users.cs.utah.edu/~lifeifei/papers/deeplog.pdf

[2] M. Du, Z. Chen, C. Liu, R. Oak, and D. Song, “Lifelong Anomaly Detection Through Unlearning,” *Proceedings of the 2019 ACM SIGSAC Conference on Computer and Communications Security*, 2019. DOI: 10.1145/3319535.3363226. https://zhichen98.github.io/data/3319535.3363226.pdf

[3] A. Mahendran, C. Y. W. Choe, and A. Varanasi, “ByeBye: A Zero-Shot Human Removal and Replacement Pipeline with Stylized Character Insertion,” Stanford CS231n final project report. http://vision.stanford.edu/teaching/cs231n/papers/text_file_840579931-CS231N_Final_Report.pdf
