---
marp: true
theme: cvs-health
paginate: true
author: "Zhaopeng Xing"
title: "Autonomous ML Runner"
---

<!-- _paginate: false -->
<!-- _class: lead invert -->

# Autonomous ML Runner

## Harness Engineering in Practice

**Zhaopeng Xing | CVS Health | May 2026**

---

# What Makes an Agent Reliable?

> "If you're not the model, you're the harness." — LangChain

The **agent** is the goal-directed behavior you see. The **harness** is the infrastructure that produces it. *The dog is capable. Reliable behavior comes from what surrounds it.*

<style scoped>
td { font-size: 0.76em; vertical-align: top; }
th { font-size: 0.76em; }
</style>

| Component | What It Does | Teaching Spotty |
|---|---|---|
| **Behavioral bounds** | Defines what the agent can and cannot touch | A physical harness in month 1 — not because Spotty is incapable, but to limit the blast radius of mistakes while reliable habits form |
| **Measurable objective** | Defines what success looks like, before the agent starts | One specific spot — not "outside," but *this* patch of grass, every time. Specificity creates an unambiguous binary. |
| **Persistent memory** | Records what worked, what failed, and why | Capture and label every outcome — reward the right spot, redirect the wrong one, immediately and consistently, every single time |
| **Independent verification** | Judges outcomes separately from the agent that acted | The trainer and the judge are not the same person — a separate judge has no incentive to confirm |

---

<!-- _backgroundColor: #f5f5f5 -->

# 50 Autonomous Rounds — IP Commercial Campaign

<style scoped>
h3 { font-size: 0.75em; margin: 6px 0 4px 0; color: #a50000; }
td { font-size: 0.58em; vertical-align: top; padding: 4px 8px; }
th { font-size: 0.58em; padding: 4px 8px; }
table { margin-bottom: 6px; }
</style>

| Stage | Rounds | Key finding | val lift@1% |
|---|---|---|---|
| **Baselines** | 1–3 | Hybrid beats tabular; embeddings alone are weak — both signal sources needed | 22.21 |
| **Model families** | 4–10 | Three gradient boosting families; combining them outperforms any individual model | 22.33 |
| **Ensemble expansion** | 10–22 | Training each model on a different feature subset creates structural diversity — feature diversity beats hyperparameter tuning | 22.73 |
| **Breakthrough** | 25 | Tuning XGBoost for overall ranking quality instead of top-1% lift makes it far more complementary in the ensemble tail — **+0.446 in one round** | **23.17** |
| **Plateau** | 26–47 | 22 consecutive failed experiments; Historian concludes the weight optimizer — stuck climbing from a fixed point — is the ceiling, not the models | 23.17 |
| **Escape** | 48 | Global weight search (evolves a population of candidate solutions simultaneously) finds a better distribution than 23 rounds of local search | **23.26** |
| **Final test** | 50 | Ranking quality generalizes near-perfectly; gap concentrates in extreme top-1% tail | test: **22.48** |

### Production Baseline vs. Campaign Champion

| | Baseline (default CatBoost, hybrid features) | Champion (ensemble, diverse feature sets) | Gain |
|---|---|---|---|
| **val lift@1%** | 22.21 | **23.26** | **+1.05 (+4.7%)** |
| **val AUC-ROC** | 0.859 | 0.857 | −0.002 |

---

<!-- _class: lead invert -->

# The dog is capable.

## Build the harness.

Behavioral bounds. Measurable objective. Persistent memory. Independent verification.
