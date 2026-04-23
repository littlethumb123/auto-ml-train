# Vertex AI Migration Modules

As we move model **training and inference to Vertex AI**, these modules create structured pathways for an easier transition — standardising how we preprocess data, select features, tune models, and retrain existing models within the Vertex ecosystem.

---

## Module Pipeline

The core pipeline follows a sequential flow for building new models on Vertex AI:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VERTEX AI MODEL Training                         │
│                                                                     │
│  ┌──────────────────┐     ┌──────────────────┐     ┌────────────┐   │
│  │  1. Preprocessing│     │ 2. Feature Eng   │     │ 3. Hyper-  │   │
│  │                  │     │                  │     │  parameter │   │
│  │  Gather all      │     │  Select the most │     │  Tuning    │   │
│  │  possible        │     │  important       │     │            │   │
│  │  variables       │     │  features        │     │  Under     │   │
│  │                  │     │                  │     │ Development│   │
│  └──────────────────┘     └──────────────────┘     └────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Available Modules

### 1. Preprocessing
> **Status:** ✅ Available

Collects and prepares all possible candidate variables from source systems. This is the entry point of the pipeline — raw data is gathered, cleaned, and consolidated into a structured format ready for feature selection.

---

### 2. Feature Engineering
> **Status:** ✅ Available

Takes the full variable set from Preprocessing and identifies the most predictive features. Uses undersampling experiments and Recursive Feature Elimination with Cross-Validation (RFECV) to output an optimal feature subset that is written back to BigQuery for downstream training.

---

### 3. Hyperparameter Tuning
> **Status:** 🚧 Under Development

Will provide automated hyperparameter optimisation for the trained model using Vertex AI's built-in tuning capabilities.

---

## Standalone Module

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STANDALONE: RETRAINING                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Vertex Model Trainer                                        │   │
│  │                                                              │   │
│  │  For models that are already trained and need retraining.    │   │
│  │  Uses prebuilt Vertex AI images with specific configurations │   │
│  │  to ensure compatibility with Batch Prediction.              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Vertex Model Trainer
> **Status:** ✅ Available

**Not part of the pipeline above.** This module is designed for models that have already been developed and need to be **retrained** under Vertex AI. It wraps the training job in a prebuilt Vertex AI container image with the necessary configurations to make the model compatible with **Vertex Batch Prediction**.

Use this when:
- A model already exists and needs periodic retraining
- You need Vertex Batch Prediction compatibility
- You want to leverage prebuilt runtime images without building custom containers

---

## Module Summary

| Module                  | Role                              | Status              | Part of Pipeline |
|-------------------------|-----------------------------------|---------------------|------------------|
| Preprocessing           | Gather all candidate variables    | ✅ Available        | ✅ Yes — Step 1  |
| Feature Engineering     | Select the most important features| ✅ Available        | ✅ Yes — Step 2  |
| Hyperparameter Tuning   | Optimise model hyperparameters    | 🚧 Under Development| ✅ Yes — Step 3  |
| Vertex Model Trainer    | Retrain existing models on Vertex | ✅ Available        | ❌ Standalone    |