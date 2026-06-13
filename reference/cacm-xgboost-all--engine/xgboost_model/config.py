"""XGBoost configuration — project YAML bridge.

project.yaml (at repo root) is the single source of truth. Copy project.example.yaml
to project.yaml and fill in your endpoint's tables, outcome column, and hyperparameters.
Run /onboard for an interactive setup.
"""

from pathlib import Path

try:
    import yaml
    _yaml_available = True
except ImportError:
    _yaml_available = False

# =============================================================================
# Project config (from project.yaml)
# =============================================================================

_PROJECT_FILE = Path(__file__).resolve().parent.parent / "project.yaml"
_project: dict = {}
if _PROJECT_FILE.exists() and _yaml_available:
    with open(_PROJECT_FILE) as _f:
        _project = yaml.safe_load(_f) or {}

# --- 1. Project identity ---
PROJECT_NAME = _project.get("project", {}).get("name", "xgboost")
PREFIX = _project.get("project", {}).get("prefix", "xgboost")
OWNER = _project.get("project", {}).get("owner", "")
COSTCENTER = _project.get("project", {}).get("costcenter", "")

# --- 2. Data sources ---
_data = _project.get("data", {})
GCP_PROJECT = _data.get("gcp_project", "")
# Support feature_tables (list) or feature_table (single string)
_ft_list = _data.get("feature_tables", None)
if _ft_list:
    FEATURE_TABLES: list[str] = list(_ft_list)
    FEATURE_TABLE = FEATURE_TABLES[0]
else:
    FEATURE_TABLE = _data.get("feature_table", "")
    FEATURE_TABLES = [FEATURE_TABLE] if FEATURE_TABLE else []
OUTCOME_TABLE = _data.get("outcome_table", "")
OUTCOME_COLUMN = _data.get("outcome_column", "outcome_flag")
ID_COLUMN = _data.get("id_column", "individual_id")
INDEX_DATE_COLUMN = _data.get("index_date_column", "index_dt")

# --- 3. Feature selection ---
_features = _project.get("features", {})
USEFUL_THRESHOLD = float(_features.get("useful_threshold", 0.004))
TOP_N = int(_features.get("top_n", 500))
FORCE_KEEP_PATTERNS = _features.get("force_keep_patterns", [])
EXCLUDE_PATTERNS = _features.get("exclude_patterns", [])
NON_FEATURE_COLUMNS = _features.get("non_feature_columns", [
    "individual_id", "index_dt", "outcome_flag",
    "impute_outcome_flag", "excluded_pre_index",
])

# --- 6. Training ---
_training = _project.get("training", {})
OBJECTIVE = _training.get("objective", "binary:logistic")
EVAL_METRIC = _training.get("eval_metric", "auc")
TREE_METHOD = _training.get("tree_method", "hist")
DEVICE = _training.get("device", "cuda")
MAX_DEPTH = int(_training.get("max_depth", 4))
LEARNING_RATE = float(_training.get("learning_rate", 0.05))
N_ESTIMATORS = int(_training.get("n_estimators", 500))
COLSAMPLE_BYTREE = float(_training.get("colsample_bytree", 0.5))
SUBSAMPLE = float(_training.get("subsample", 0.8))
_spw = _training.get("scale_pos_weight", None)
SCALE_POS_WEIGHT = float(_spw) if _spw is not None else None
TEST_SIZE = float(_training.get("test_size", 0.2))
VAL_SIZE = float(_training.get("val_size", 0.2))
RANDOM_STATE = int(_training.get("random_state", 42))
SMOKE_TEST_N = int(_training.get("smoke_test_n", 2000))

# --- 7b. Hyperparameter tuning (Optuna) ---
_tuning = _project.get("tuning", {})
HPO_N_TRIALS = int(_tuning.get("n_trials", 100))
HPO_CV_FOLDS = int(_tuning.get("cv_folds", 5))
HPO_TIMEOUT = _tuning.get("timeout_seconds", 3600)

# =============================================================================
# Paths (computed from config)
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _REPO_ROOT / "output"
DATA_DIR = OUTPUT_DIR / "data"
MODELS_DIR = OUTPUT_DIR / "models"
FEATURES_DIR = OUTPUT_DIR / "features"
FIGURES_DIR = OUTPUT_DIR / "figures"
DOCS_DIR = _REPO_ROOT / "docs"


def tag_path(base_dir: Path, tag: str, filename: str) -> Path:
    """Return a tagged output path: base_dir/tag/filename."""
    path = base_dir / tag
    path.mkdir(parents=True, exist_ok=True)
    return path / filename


def xgb_params() -> dict:
    """Return XGBoost constructor kwargs from config."""
    params = {
        "objective": OBJECTIVE,
        "eval_metric": EVAL_METRIC,
        "tree_method": TREE_METHOD,
        "device": DEVICE,
        "max_depth": MAX_DEPTH,
        "learning_rate": LEARNING_RATE,
        "n_estimators": N_ESTIMATORS,
        "colsample_bytree": COLSAMPLE_BYTREE,
        "subsample": SUBSAMPLE,
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
        "verbosity": 0,
    }
    if SCALE_POS_WEIGHT is not None:
        params["scale_pos_weight"] = SCALE_POS_WEIGHT
    return params
