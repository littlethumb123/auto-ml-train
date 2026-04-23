"""
XGBoost Batch Prediction Serving Container (FastAPI)

Mirrors the local inference logic from local_bst_inference_test.ipynb:
  - Reindex to exact booster.feature_names order
  - pd.to_numeric(errors="coerce").fillna(-1)
  - xgb.DMatrix with explicit feature names
  - booster.predict(dmat)

Environment variables:
  AIP_STORAGE_URI       GCS path to model directory, e.g. gs://bucket/path/
                        Set automatically by Vertex AI batch prediction.
  MODEL_FILENAME        Model filename inside AIP_STORAGE_URI (default: a538985_Models_model.bst)
  LOCAL_MODEL_PATH      Fallback local path for offline/testing
  EXPECTED_FEATURES_JSON  JSON-encoded list of feature names (fallback if model has none embedded)
  LOG_LEVEL             Logging level: DEBUG | INFO | WARNING | ERROR (default: INFO)
"""

import json
import logging
import os
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException, Request
from google.cloud import storage
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging setup — very verbose to help debug Vertex container failures
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("xgb-server")

logger.info("=" * 70)
logger.info("XGBoost Serving Container — startup")
logger.info("=" * 70)

# ---------------------------------------------------------------------------
# Environment config
# ---------------------------------------------------------------------------
AIP_STORAGE_URI: str = os.getenv("AIP_STORAGE_URI", "").strip()
MODEL_FILENAME: str = os.getenv("MODEL_FILENAME", "a538985_Models_model.bst")
DEFAULT_LOCAL_MODEL_PATH: str = os.getenv(
    "LOCAL_MODEL_PATH", f"/tmp/model/{MODEL_FILENAME}"
)
EXPECTED_FEATURES_JSON: str = os.getenv("EXPECTED_FEATURES_JSON", "")

logger.info("Environment:")
logger.info("  LOG_LEVEL             = %s", LOG_LEVEL)
logger.info("  AIP_STORAGE_URI       = %s", AIP_STORAGE_URI or "<empty>")
logger.info("  MODEL_FILENAME        = %s", MODEL_FILENAME)
logger.info("  DEFAULT_LOCAL_MODEL_PATH = %s", DEFAULT_LOCAL_MODEL_PATH)
logger.info(
    "  EXPECTED_FEATURES_JSON = %s",
    (EXPECTED_FEATURES_JSON[:120] + "...") if len(EXPECTED_FEATURES_JSON) > 120 else EXPECTED_FEATURES_JSON or "<empty>",
)


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------
def _parse_gcs_uri(uri: str):
    """Return (bucket_name, prefix) from a gs:// URI."""
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {uri!r}")
    without = uri[5:]
    parts = without.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def _download_model_from_gcs(aip_storage_uri: str, model_filename: str) -> str:
    """
    Download model .bst file from GCS to a local temp directory.
    Tries common path patterns then falls back to scanning the prefix.
    """
    bucket_name, prefix = _parse_gcs_uri(aip_storage_uri)
    logger.info("GCS download | bucket=%s  prefix=%s", bucket_name, prefix)

    gcs_client = storage.Client()
    bucket = gcs_client.bucket(bucket_name)

    tmp_dir = Path(tempfile.mkdtemp(prefix="xgb_model_"))
    local_path = tmp_dir / model_filename
    logger.info("Local temp path: %s", local_path)

    # Try common blob path patterns
    candidate_blob_names: List[str] = []
    if prefix:
        candidate_blob_names.append(f"{prefix.rstrip('/')}/{model_filename}")
        # AIP_STORAGE_URI could point directly at the file (no trailing slash)
        if prefix.endswith(model_filename):
            candidate_blob_names.append(prefix)
    else:
        candidate_blob_names.append(model_filename)

    logger.info("Trying %d blob candidates: %s", len(candidate_blob_names), candidate_blob_names)

    for blob_name in candidate_blob_names:
        blob = bucket.blob(blob_name)
        logger.info("Checking gs://%s/%s ...", bucket_name, blob_name)
        if blob.exists():
            size_mb = blob.size / (1024 * 1024) if blob.size else 0
            logger.info(
                "Found model blob gs://%s/%s  size=%.2f MB — downloading",
                bucket_name, blob_name, size_mb,
            )
            blob.download_to_filename(str(local_path))
            logger.info(
                "Download complete → %s  bytes=%d", local_path, local_path.stat().st_size
            )
            return str(local_path)

    # Fallback: scan all objects under prefix for any .bst
    search_prefix = (prefix.rstrip("/") + "/") if prefix else ""
    logger.warning(
        "None of the blob candidates existed. Scanning gs://%s/%s for *.bst",
        bucket_name, search_prefix,
    )
    found_blobs = []
    for blob in gcs_client.list_blobs(bucket_name, prefix=search_prefix):
        found_blobs.append(blob.name)
        if blob.name.endswith(".bst"):
            logger.info(
                "Fallback found *.bst → gs://%s/%s  downloading", bucket_name, blob.name
            )
            blob.download_to_filename(str(local_path))
            logger.info(
                "Fallback download complete → %s  bytes=%d",
                local_path, local_path.stat().st_size,
            )
            return str(local_path)

    logger.error(
        "All objects under gs://%s/%s: %s", bucket_name, search_prefix, found_blobs
    )
    raise FileNotFoundError(
        f"Could not find model file {model_filename!r} in {aip_storage_uri!r}. "
        f"Candidates tried: {candidate_blob_names}. "
        f"All objects under prefix: {found_blobs}"
    )


# ---------------------------------------------------------------------------
# Model path resolution
# ---------------------------------------------------------------------------
def _resolve_model_path() -> str:
    if AIP_STORAGE_URI.startswith("gs://"):
        logger.info("Resolving model from GCS: %s", AIP_STORAGE_URI)
        return _download_model_from_gcs(AIP_STORAGE_URI, MODEL_FILENAME)

    # Non-GCS: treat AIP_STORAGE_URI as local directory or file
    if AIP_STORAGE_URI:
        p = Path(AIP_STORAGE_URI)
        if p.is_file():
            logger.info("AIP_STORAGE_URI points to local file: %s", p)
            return str(p)
        candidate = p / MODEL_FILENAME
        if candidate.exists():
            logger.info("AIP_STORAGE_URI is local dir, found model at: %s", candidate)
            return str(candidate)
        logger.warning("AIP_STORAGE_URI=%s is not GCS and not a valid local path", AIP_STORAGE_URI)

    # Default local path
    if Path(DEFAULT_LOCAL_MODEL_PATH).exists():
        logger.info("Using DEFAULT_LOCAL_MODEL_PATH: %s", DEFAULT_LOCAL_MODEL_PATH)
        return DEFAULT_LOCAL_MODEL_PATH

    raise FileNotFoundError(
        f"Model file not found. "
        f"AIP_STORAGE_URI={AIP_STORAGE_URI!r}, "
        f"MODEL_FILENAME={MODEL_FILENAME!r}, "
        f"DEFAULT_LOCAL_MODEL_PATH={DEFAULT_LOCAL_MODEL_PATH!r}. "
        f"Please set AIP_STORAGE_URI or LOCAL_MODEL_PATH."
    )


# ---------------------------------------------------------------------------
# Load expected features from env (fallback if model has no embedded names)
# ---------------------------------------------------------------------------
def _load_expected_features_from_env() -> List[str]:
    if not EXPECTED_FEATURES_JSON:
        return []
    try:
        data = json.loads(EXPECTED_FEATURES_JSON)
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            logger.info(
                "EXPECTED_FEATURES_JSON loaded %d feature names from env", len(data)
            )
            return data
        logger.error(
            "EXPECTED_FEATURES_JSON must be a JSON list of strings. Got type=%s",
            type(data).__name__,
        )
    except Exception:
        logger.exception("Failed to parse EXPECTED_FEATURES_JSON")
    return []


# ---------------------------------------------------------------------------
# Load model at startup — crash here is intentional so container fails fast
# ---------------------------------------------------------------------------
logger.info("Resolving model path ...")
model_path = _resolve_model_path()

logger.info("Loading XGBoost Booster from: %s", model_path)
booster = xgb.Booster()
booster.load_model(model_path)
logger.info("Booster loaded successfully")

# Feature names
model_feature_names: List[str] = booster.feature_names or []
env_feature_names: List[str] = _load_expected_features_from_env()

if model_feature_names:
    expected_features: List[str] = model_feature_names
    logger.info(
        "Using embedded model feature names: count=%d  sample=%s",
        len(expected_features), expected_features[:10],
    )
else:
    expected_features = env_feature_names
    if expected_features:
        logger.warning(
            "Model has no embedded feature names. "
            "Falling back to EXPECTED_FEATURES_JSON: count=%d  sample=%s",
            len(expected_features), expected_features[:10],
        )
    else:
        logger.warning(
            "No feature list available from model or env. "
            "Dict-instance column ordering will be determined by incoming payload."
        )

logger.info("=" * 70)
logger.info("Serving ready. expected_features=%d", len(expected_features))
logger.info("=" * 70)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="XGBoost Batch Prediction Server",
    description="Custom serving container for a538985_Models_model.bst (readmission risk)",
    version="1.0.0",
)


class PredictRequest(BaseModel):
    instances: List[Union[Dict[str, Any], List[Any]]]


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    logger.info("Health check called")
    return {
        "status": "ok",
        "model_loaded": True,
        "model_path": model_path,
        "expected_feature_count": len(expected_features),
        "expected_features_source": (
            "booster.feature_names"
            if model_feature_names
            else ("EXPECTED_FEATURES_JSON" if env_feature_names else "none")
        ),
    }


# ---------------------------------------------------------------------------
# /predict
# ---------------------------------------------------------------------------
@app.post("/predict")
def predict(req: PredictRequest):
    try:
        n = len(req.instances)
        logger.info("--- /predict called | instances=%d ---", n)

        if n == 0:
            logger.warning("Empty instances list received; returning empty predictions")
            return {"predictions": []}

        first = req.instances[0]
        logger.info("First instance type: %s", type(first).__name__)
        if isinstance(first, dict):
            logger.debug("First instance keys (sample): %s", list(first.keys())[:15])
        elif isinstance(first, list):
            logger.debug("First instance length: %d  sample: %s", len(first), first[:5])

        # ------------------------------------------------------------------
        # Build DataFrame — mirrors local_bst_inference_test.ipynb exactly
        # ------------------------------------------------------------------
        if isinstance(first, dict):
            logger.info("Building DataFrame from dict instances")
            df = pd.DataFrame(req.instances)
            logger.info(
                "Raw DataFrame | rows=%d  cols=%d  columns_sample=%s",
                df.shape[0], df.shape[1], list(df.columns)[:15],
            )

            if expected_features:
                incoming_cols = set(df.columns)
                expected_set = set(expected_features)
                missing = [c for c in expected_features if c not in incoming_cols]
                extra = [c for c in df.columns if c not in expected_set]

                if missing:
                    logger.warning(
                        "Missing features (will be filled with NaN→-1): count=%d  sample=%s",
                        len(missing), missing[:10],
                    )
                if extra:
                    logger.info(
                        "Extra columns in payload (will be dropped): count=%d  sample=%s",
                        len(extra), extra[:10],
                    )

                # Reindex to exact model feature order
                # (matches: feature_df = work_df.reindex(columns=model_feature_names))
                df = df.reindex(columns=expected_features)
                logger.info(
                    "After reindex | rows=%d  cols=%d", df.shape[0], df.shape[1]
                )
            else:
                logger.warning(
                    "No expected feature list — using incoming dict column order as-is"
                )

        elif isinstance(first, list):
            logger.info("Building DataFrame from list instances")
            arr = np.array(req.instances, dtype=object)
            logger.info("Array shape: %s", arr.shape)

            n_cols = arr.shape[1] if arr.ndim == 2 else None
            if expected_features and n_cols is not None and n_cols == len(expected_features):
                df = pd.DataFrame(arr, columns=expected_features)
                logger.info(
                    "Mapped %d list columns to expected_features", n_cols
                )
            elif expected_features and n_cols is not None:
                logger.warning(
                    "List instance column count=%d does not match expected_features count=%d; "
                    "using positional columns without names",
                    n_cols, len(expected_features),
                )
                df = pd.DataFrame(arr)
            else:
                df = pd.DataFrame(arr)
                logger.info(
                    "Created DataFrame from list array shape=%s", df.shape
                )

        else:
            raise ValueError(
                f"Unsupported instance format: {type(first).__name__}. "
                f"Expected dict or list."
            )

        # ------------------------------------------------------------------
        # Numeric coercion + fill NaN → -1
        # (matches: feature_df = feature_df.apply(pd.to_numeric, errors="coerce").fillna(-1))
        # ------------------------------------------------------------------
        logger.info(
            "Before numeric cast | shape=%s  dtypes_sample=%s",
            df.shape,
            dict(df.dtypes.astype(str).head(5)),
        )
        df = df.apply(pd.to_numeric, errors="coerce").fillna(-1)
        logger.info(
            "After numeric cast  | shape=%s  NaN count=%d",
            df.shape,
            int(df.isna().sum().sum()),
        )

        # ------------------------------------------------------------------
        # Build DMatrix
        # (matches: dtest = xgb.DMatrix(feature_df, feature_names=list(feature_df.columns)))
        # ------------------------------------------------------------------
        feature_cols = list(df.columns)
        logger.info(
            "Building DMatrix | rows=%d  feature_cols=%d  first_10=%s",
            len(df), len(feature_cols), feature_cols[:10],
        )
        dmat = xgb.DMatrix(df, feature_names=feature_cols)

        # ------------------------------------------------------------------
        # Predict
        # (matches: pred = booster.predict(dtest))
        # ------------------------------------------------------------------
        preds: np.ndarray = booster.predict(dmat)
        logger.info(
            "Predictions | count=%d  min=%.6f  max=%.6f  mean=%.6f  std=%.6f",
            len(preds),
            float(np.min(preds)),
            float(np.max(preds)),
            float(np.mean(preds)),
            float(np.std(preds)),
        )

        return {"predictions": preds.tolist()}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Prediction failed: %s", str(exc))
        logger.error("Full traceback:\n%s", traceback.format_exc())
        # Return error in response body so it appears in BigQuery output table.
        # Vertex AI batch prediction does NOT surface 500-level logs to the user,
        # but it DOES write the response body to the output table — so errors
        # returned here will be visible as an "error" column in BigQuery output.
        # Reference: https://datatonic.com/insights/vertex-ai-improving-debugging-batch-prediction/
        return {
            "predictions": [],
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
