# Model Accuracy Report

## 1. Executive Summary
- **Priority/Risk Classifier is Heavily Overfitted:** The model achieved an artificial 1.00 (100%) test accuracy. Analysis reveals a near 1:1 mapping between `corridor` and `priority` in the dataset, leading the model to overfit on location rather than learning actual risk dynamics.
- **Resolution Time Regressor Struggles with Variance:** The time prediction model has an $R^2$ of ~0.03, meaning it is effectively guessing the mean. The median absolute error is ~27 minutes, but the 95th percentile error shoots up to ~236 minutes.
- **Planned Event Sample Size is Dangerously Low:** There are only 467 "planned" events in the entire dataset (8173 records). For the time regressor, only 8 planned events landed in the test set, making forecasts for planned events highly unreliable.
- **TF-IDF Search is Vulnerable to Unseen Vocabulary:** The historical search successfully boosts matching `event_cause` attributes, but fails silently if a term like "rally" is missing from the known `event_cause` categorical list (matching irrelevant incidents via text overlap instead).

## 2. Methodology
- **Data Source:** `dataset_processed/astram_events_processed.csv` and `dataset_processed/astram_events_resolved.csv` (8,173 records).
- **Split Strategy:** All models were evaluated on a clean **80/20 holdout test set** with `random_state=42`. Classification models (`priority` and `requires_road_closure`) used stratified splitting to preserve class balance.
- **Sample Breakdown:**
  - Total Training Samples: ~6,500
  - Total Test Samples: ~1,635
  - Planned Events in Test Set: 91 for Priority, 87 for Closure, 8 for Resolution Time.
- **Tools:** Re-ran inferences using `evaluate_models.py` leveraging standard `sklearn.metrics` to ensure unbiased scoring against the `.cbm` model artifacts.

## 3. Priority/Risk Classifier Results
*Target variable: `priority` mapped to high (1) and low (0).*

**Overall Test Set Metrics (1635 samples):**
| Metric | Pred Low (0) | Pred High (1) |
| --- | --- | --- |
| **Precision** | 1.00 | 1.00 |
| **Recall** | 1.00 | 1.00 |
| **F1-Score** | 1.00 | 1.00 |

*Overall Accuracy: 1.00*

**Planned Events Only (91 samples):**
* Accuracy: 1.00 (100%)

**Confusion Matrix (Overall):**
```text
               Pred Low  Pred High
  Actual Low        629          0
 Actual High          1       1005
```

**Feature Importance (Top 3):**
1. `corridor`: 96.94%
2. `event_cause`: 1.57%
3. `longitude`: 0.59%

**Audit Note:** The accuracy is misleadingly high due to the dataset structure. Only 4 out of 23 unique corridors have more than one priority class associated with them. The model simply learned that "Corridor X = Priority Y".

## 4. Closure Probability Model Results
*Target variable: `requires_road_closure` (1) vs No Closure (0).*
*Configuration: Used `auto_class_weights='Balanced'` due to low closure frequency.*

**Overall Test Set Metrics (1635 samples):**
* **ROC-AUC:** 0.7884
* **Accuracy:** 0.82

| Class | Precision | Recall | F1-Score | Support |
| --- | --- | --- | --- | --- |
| No Closure (0) | 0.96 | 0.84 | 0.90 | 1500 |
| Requires Closure (1) | 0.26 | 0.62 | 0.37 | 135 |

**Planned Events Only (87 samples):**
* **ROC-AUC:** 0.8631
* **Accuracy:** 0.55
* **Recall for Class 1:** 0.97
* **Precision for Class 1:** 0.46

**Audit Note:** The class balancing strategy boosts recall significantly (catching 97% of planned event closures), but destroys precision. It over-predicts closures heavily, resulting in a false positive rate that could lead to over-deployment of barricades in production.

**Feature Importance (Top 3):**
1. `event_cause`: 22.18%
2. `corridor`: 11.57%
3. `police_station_grouped`: 10.00%

## 5. Resolution Time Regressor Results
*Target variable: `response_time_minutes` (Log-transformed during training).*

**Overall Test Set Metrics:**
* **MAE:** 71.40 minutes
* **RMSE:** 199.62 minutes
* **$R^2$:** 0.0303
* **Median Absolute Error:** 27.24 minutes

**Error Distribution (Percentiles):**
* 50th Percentile Error: 27.24 minutes
* 80th Percentile Error: 65.84 minutes
* 95th Percentile Error: 235.88 minutes

**Planned Events Only (8 samples):**
* **MAE:** 146.21 minutes
* **Median AE:** 60.55 minutes

**Feature Importance (Top 3):**
1. `event_cause`: 41.21%
2. `veh_type_grouped`: 18.14%
3. `corridor`: 7.70%

**Audit Note:** The model is effectively failing to learn. A $R^2$ of 0.03 implies it's barely outperforming a simple mean-prediction baseline. The extreme right skew of incident durations forces the model to struggle, making predictions highly unreliable for operational usage.

## 6. Historical Similarity Search (TF-IDF) Evaluation
The hybrid TF-IDF + rule-based search engine (`search_similar_incidents()`) was stress-tested against realistic BTP prompts.

**Observations:**
1. **The Event Cause Booster Works:** When querying `vip_movement` at `orr east 1`, the top returned matches were exclusively VIP movements (Base cosine score of ~0.49, boosted to ~0.89), proving the recent 0.6/0.4 fix behaves properly.
2. **Vocabulary Missing Errors:** When querying for a "rally" at "hosur road", the engine failed silently. Because "rally" does not exist as an explicit `event_cause` within the dataset (they are logged as `public_event`, `protest`, etc.), the strict cause-matching was bypassed. The model defaulted to pure text-overlap, successfully matching the word "huge" but surfacing irrelevant "Huge Potholes" incidents instead.

## 7. Data Quality & Leakage Risks
- **Data Leakage (Priority):** The near 1:1 geographic mapping between `corridor` and `priority` functions as a data leak. The model is learning the dataset's artifact rather than evaluating genuine event risk.
- **Class Imbalance:** Extreme class imbalance in closures forces a high false-positive rate due to the synthetic class weights applied during training. 
- **Duplicates:** No full-row duplicates exist (0/8173), but ~121 rows share identical geographic coordinates, causes, and times, suggesting mild multi-logging.

## 8. Honest Limitations
- **Sample Size Caveat:** The planned-event subset is far too small to yield statistically significant findings for the time regression model (n=8 in test). We cannot currently guarantee the system's accuracy for forecasting the impact of planned rallies or VIP movements.
- **Non-Standardized Event Causes:** The historical database lacks a robust ontology. Planners inputting "rally" fail to match historical "public_event" records.

## 9. Recommendations
1. **Ontology Mapping (Critical):** Implement an LLM-based query expansion or synonym mapper before querying TF-IDF so that "rally", "procession", and "public_event" resolve to a unified `event_cause` token.
2. **Collect More Planned Event Data:** The models require at least ~2,000+ planned events to properly capture variance in duration and closure probability.
3. **Drop `corridor` from Priority Model:** Temporarily remove the `corridor` feature from the priority classifier to force the model to learn multi-variate risk signals (time of day, event cause, cascade size) instead of memorizing static map routes.
4. **Switch to Quantile Regression for Time:** Since incident durations are highly right-skewed, switch the `CatBoostRegressor` loss function to `Quantile` (e.g., predicting the 80th percentile worst-case scenario) rather than optimizing for `RMSE`, which gets heavily punished by long-tail outliers.
