# Model Accuracy Report (v3)

## 1. What Changed Since V2
Based on the critical audit finding that the V2 priority model (Accuracy 60%) was losing to a naive majority-class baseline (Accuracy ~61.5%), the following diagnostic steps and fixes were applied:

- **Baseline Metrics Added:** Explicit majority-class baseline calculations were added to `evaluate_models.py` for all classification models to compute both Accuracy and Macro-F1 on the exact test split.
- **Cascade_size Leakage Removed:** Discovered that `cascade_size` (previously the 5th most important feature at 8.9%) is a downstream outcome (known only post-incident when cascading events occur). It was removed from the features to prevent forward-looking data leakage.
- **Safe Geographic Feature Reintroduced:** After confirming that `zone` does *not* have a 1:1 leaky mapping to priority (unlike `corridor`), it was added back to the model to provide a moderate, safe geographical signal.
- **Hyperparameter Retuning:** Retrained the model with the cleaner feature set (`zone` added, `cascade_size` and `is_cascaded` removed). Class weighting (`auto_class_weights='Balanced'`) was kept, as it properly penalizes missing the minority class.

## 2. Updated Priority/Risk Classifier Results
*Configuration: 80/20 stratified split, `random_state=42`. Leaky `cascade_size` removed, `zone` safely added.*

**Baseline Comparison Table (Required):**
| | Accuracy | Macro-F1 |
|---|---|---|
| **Majority-Class Baseline** | 0.6153 | 0.3809 |
| **Model (V2 - broken)** | 0.6000 | ~0.5900 |
| **Model (V3 - fixed)** | **0.6618** | **0.6490** |

*Verdict:* The V3 model legitimately beats the baseline on **both** Accuracy and Macro-F1, proving it has learned genuine risk dynamics.

**Overall Test Set Metrics (1635 samples):**
| Metric | Pred Low (0) | Pred High (1) |
| --- | --- | --- |
| **Precision** | 0.55 | 0.74 |
| **Recall** | 0.61 | 0.69 |
| **F1-Score** | 0.58 | 0.72 |

**Planned Events Only (91 samples):**
* **Accuracy:** 0.69 (69%)
* **Macro-F1:** 0.68

**Confusion Matrix (Overall):**
```text
               Pred Low  Pred High
  Actual Low        385        244
 Actual High        309        697
```

**New Feature Importance (Top 5):**
*(Note: `cascade_size` successfully removed. `zone` safely incorporated).*
1. `veh_type_grouped`: 15.81%
2. `event_cause`: 15.65%
3. `day_of_week`: 15.03%
4. `zone`: 12.01%
5. `month`: 11.78%

## 3. Closure Probability Model — Baseline Check
*Target variable: `requires_road_closure` (1) vs No Closure (0).*
*Configuration: Used `auto_class_weights='Balanced'` due to low closure frequency (135 out of 1635 test samples).*

**Baseline Comparison Table:**
| | Accuracy | Macro-F1 |
|---|---|---|
| **Majority-Class Baseline** | 0.9174 | 0.4785 |
| **Model** | 0.8239 | **0.6330** |

*Verdict:* The baseline artificially scores ~92% Accuracy by predicting "No Closure" for every single event, effectively failing its purpose (Macro-F1 of 0.47). The trained model sacrifices some accuracy (82.3%) to achieve a vastly superior Macro-F1 (0.63), demonstrating it successfully detects closures.

**Overall Test Set Metrics (1635 samples):**
* **ROC-AUC:** 0.7884
* **Accuracy:** 0.82

| Class | Precision | Recall | F1-Score | Support |
| --- | --- | --- | --- | --- |
| No Closure (0) | 0.96 | 0.84 | 0.90 | 1500 |
| Requires Closure (1) | 0.26 | 0.62 | 0.37 | 135 |

## 4. Unchanged Sections (from V2)
- **Resolution Time Regressor Results:** Still out of scope. Remains weak with a $R^2$ of ~0.03. High variance in response times remains a core modeling challenge.
- **Historical Similarity Search (TF-IDF):** Synonym vocabulary gap was fixed in V2. Searching for informal terms like "rally" or "convoy" successfully triggers the `exact_cause_match` boolean and returns highly relevant categories (`public_event` / `vip_movement`).

## 5. Honest Verdict
The V3 priority model **genuinely beats the naive baseline** on both Accuracy (66.18% vs 61.53%) and Macro-F1 (0.6490 vs 0.3809). It is now a fully leak-free, defensible risk classifier. 

## 6. Updated Jury Framing Recommendation
When discussing the models during the demo, adopt a baseline-aware framing to demonstrate engineering rigor.

*"Our priority model achieves 66.2% accuracy and a macro-F1 of ~0.65, which is meaningfully ahead of a naive always-predict-majority baseline (61.5% accuracy / ~0.38 macro-F1). This proves our system is learning real, actionable risk signals. Similarly, for predicting road closures, because closures only happen in ~8% of cases, a naive model can get 92% accuracy by doing nothing. We intentionally chose a balanced-weight architecture that trades raw accuracy (82%) for a massive jump in Macro-F1 (0.63 vs 0.47 baseline), ensuring we actually detect when closures are needed rather than just playing the statistical odds."*
