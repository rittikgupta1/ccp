---
title: "Runner OT prediction model accuracy"
date: 2026-05-05
author: ritikguptasnabbit
team: data
type: model
trust: draft
expires: 2026-11-01
---

# Runner OT prediction model accuracy

## Model: LightGBM v2 for OT Predictions

- **Target:** Whether a runner will accept OT slot
- **Features:** historical acceptance rate, distance from hood, day of week, shift type
- **Performance:** AUC 0.82, Precision 0.74 at 0.5 threshold
- **Training data:** 45K OT offers from Jan-Apr 2026

## Key Insight

Runners within 3km of hood have 2.3x higher OT acceptance rate. Distance is the strongest predictor.

