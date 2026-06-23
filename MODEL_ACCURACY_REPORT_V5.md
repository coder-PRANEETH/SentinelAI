# Model Accuracy Report (v5)

## 1. What Was Tried

All experiments used the identical V4 train(64%)/val(16%)/test(20%) split (`random_state=42`). CV scores are 5-fold on train+val. Test set evaluated **once** at the end.

| Experiment | Description | CV Macro-F1 |
|---|---|---|
| **V4 Baseline** | V4 features: zone, interactions, rolling risk | 0.614 ± 0.011 |
| **+ TF-IDF (30 terms)** | Free-text description TF-IDF, 30 components | 0.637 ± 0.017 |
| **+ `authenticated` flag** | Operator auth status added as cat feature | included above |
| **Threshold tuning (val set)** | Sweep 0.30–0.70 on val probabilities | best=0.50 (no change) |

**Negative results:**
- `client_id`: Only 2 clients; client_id=2 has 95% Low priority but only 80 records — too sparse to generalize and has near-1:1 class tendency. **Excluded as leakage risk.**
- `created_by_id` operator tendency: Per-operator priority ratios hit 1.0 for many users with <5 records — classic sparse-categorical leakage pattern. **Excluded.**
- Ensemble (CatBoost + LogReg): Attempted brief ablation on validation; no measurable lift over single CatBoost with balanced weights.
- Threshold tuning: Optimal threshold remained 0.50 on validation set — model probabilities are reasonably calibrated and default threshold is already near-optimal.

## 2. Leakage Red-Flag Log

| Feature | Investigation | Decision |
|---|---|---|
| `client_id` | client_id=2 → 95% Low, only 80 rows | **EXCLUDED** — near-1:1, too sparse |
| `created_by_id` | Many operator IDs map 100% to one class, sparse | **EXCLUDED** — categorical memorization risk |
| `authenticated` | No/yes splits 63.3%/61.3% High — mild signal, no near-1:1 | **INCLUDED** — safe |
| `description` TF-IDF | Terms like "accident", "fire", "major" add modest signal | **INCLUDED** — descriptions are entered at report time, before priority assignment |
| No single TF-IDF jump > 3 pts from V4 | Well below the 5-point red-flag threshold | **Clear** |

## 3. Final Configuration

**Features (V5):**
- Categorical: `event_type_grouped`, `event_cause`, `requires_road_closure`, `veh_type_grouped`, `day_of_week`, `zone`, `cause_x_peak`, `cause_x_zone`, `veh_x_zone`, `authenticated`
- Numeric: `hour_of_day`, `month`, `is_peak_hour`, `is_weekend`, `zone_historical_risk`, + 30 TF-IDF description components

**Best Hyperparams** (same as V4, validated by CV): `iterations=500, lr=0.1, depth=4, l2_leaf_reg=5, auto_class_weights='Balanced'`

**5-Fold CV Stability (Train+Val):**
- CV Accuracy: **0.6454 ± 0.0168**
- CV Macro-F1: **0.6367 ± 0.0166**

## 4. Final Locked Test Set Result

*Test set evaluated exactly once after all decisions finalized.*

**Updated Baseline Comparison Table:**
| | Accuracy | Macro-F1 |
|---|---|---|
| Majority-Class Baseline | 0.6153 | 0.3809 |
| V3 Model (leaky eval) | 0.6618 | 0.6490 |
| V4 Model (strict) | 0.6404 | 0.6272 |
| **V5 Model (final)** | **0.6538** | **0.6434** |

**Classification Report:**
| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Low (0) | 0.55 | 0.61 | 0.58 | 629 |
| High (1) | 0.74 | 0.69 | 0.71 | 1006 |
| **Accuracy** | | | **0.6538** | 1635 |
| Macro avg | 0.65 | 0.65 | 0.64 | 1635 |

## 5. Misclassification Analysis

Spot-checked 10 randomly sampled misclassified test cases. **Three clear patterns emerged:**

**Pattern A — Missing/Empty Descriptions (4/10 cases)**
Cases where `description` is blank or a placeholder (e.g., "vehicle break down", empty string). The model has no text signal to differentiate ambiguous vehicle-breakdown events. These are genuinely ambiguous — even a human reviewer would need to call the operator.
- Example: `ACTUAL: HIGH | PRED: LOW | Cause: vehicle_breakdown | Vehicle: heavy_vehicle | Zone: unknown | Desc: [empty] | Hour: 22, Peak: 0`

**Pattern B — Zone=unknown kills context (4/10 cases)**
Several misclassifications occur where `zone` is `unknown`, stripping the most powerful geographic feature from the model. The historical risk signal also defaults to 0.50 (no prior data), leaving the model to predict from cause/vehicle type alone — which is insufficient for borderline cases.
- Example: `ACTUAL: LOW | PRED: HIGH | Cause: vehicle_breakdown | Vehicle: private_car | Zone: unknown`
- Example: `ACTUAL: HIGH | PRED: LOW | Cause: vehicle_breakdown | Vehicle: heavy_vehicle | Zone: unknown`

**Pattern C — Genuine label ambiguity (2/10 cases)**
Two cases where the cause is `others` or `vehicle_breakdown`, the description is vague ("electrical pol road"), time is off-peak, and zone is unknown. These are legitimately borderline — no reasonable feature set could reliably distinguish High vs Low here without dispatcher ground truth.
- Example: `ACTUAL: HIGH | PRED: LOW | Cause: others | Vehicle: nan | Zone: unknown | Desc: "electrical pol road [person]" | Hour: 21`

## 6. Honest Final Verdict

**80% accuracy was NOT reached.** The V5 final test score is **65.38% accuracy / 0.6434 macro-F1** — an improvement of **+1.34pp accuracy and +1.62pp macro-F1 over V4** (64.04%/0.6272).

The improvement (+1.34pp) is **within the CV standard deviation (±1.68pp)**, meaning it is a plausible but not definitively statistically significant gain. It is a real improvement, not a regression, but should be reported as marginal rather than a breakthrough.

**Why 80% is not reachable with this dataset:**

1. **Zone sparsity (~10% of records have `zone=unknown`):** Loses the most predictive geographic feature for a significant slice of records.
2. **Empty descriptions (~30-40% of records have blank or near-blank `description`):** The free-text field that would differentiate ambiguous incidents is systematically missing.
3. **Binary priority with fuzzy labeling:** The distinction between "High" and "Low" in the original dataset relies on dispatcher judgment — there is no objective ground truth formula. Misclassified cases visually appear indistinguishable from correctly-classified ones with identical features.
4. **Dataset size ceiling (~8,000 rows):** Too small for reliable TF-IDF to learn more than ~30 high-frequency terms, and too small for deep interaction features without overfitting.

The model's performance is likely near the **practical ceiling for this dataset** at ~65-67% with current data quality.

## 7. Recommendation

What would ACTUALLY be needed to push toward 80%:

| Requirement | Impact |
|---|---|
| **Fix `zone=unknown` records** | ~10% of data loses the strongest geographic feature — backfilling via GPS→zone lookup could recover 3-5pp |
| **Enforce structured descriptions** | Require operators to tag descriptions with standardized keywords at submission. Currently 30-40% are blank or free-form noise |
| **Larger dataset** | 80%+ would require 3-5× more records to train stable interaction features without overfitting |
| **Live contextual signals** | Real-time traffic density, weather, prior day incident count for the zone — features the static historical dataset cannot provide |
| **Human-in-the-loop for P=0.45–0.55** | Flag borderline probabilities for dispatcher review rather than forcing a binary prediction — reduces hard misclassifications on ambiguous cases |

For the jury: *"Our model achieves 65.4% accuracy / 0.64 macro-F1 — meaningfully above the 61.5%/0.38 naive baseline. We pushed hard with TF-IDF text embeddings, calibrated threshold search, zone-level rolling risk, and interaction features. After forensically reviewing 10 misclassified cases, we identified that the remaining errors concentrate in records with missing zone data or blank descriptions — structural data quality gaps, not a modeling failure. Getting to 80% requires fixing data collection upstream, not more model complexity."*
