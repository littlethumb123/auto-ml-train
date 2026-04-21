
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime
import json

# Base configuration models with strict typing
class MetadataConfig(BaseModel):
    cfg_version: str = Field(..., description="Configuration version")
    component_version: str = Field(..., description="Component version")
    image_tag: str = Field(..., description="Docker image tag")
    schema_version: str = Field(..., description="Schema version")
    created_by: str = Field(..., description="Creator identifier")
    created_at: str = Field(..., description="Creation timestamp")

class RuntimeConfig(BaseModel):
    project: str = Field(..., description="GCP project ID")
    costcenter: str = Field(..., description="Cost center code")
    owner: str = Field(..., description="Owner identifier")
    tenant: str = Field(..., description="Tenant identifier")
    pipeline_root: str = Field(..., description="Pipeline root GCS path")
    location: str = Field(default="US", description="GCP location")
    service_account: str = Field(..., description="Service account email for pipeline execution")
    cmek_key: str = Field(..., description="Customer-managed encryption key for data encryption")
    labels: Dict[str, str] = Field(default_factory=dict, description="Resource labels")

class BigQueryConfig(BaseModel):
    dataset: str = Field(..., description="BigQuery dataset")
    features_table: str = Field(..., description="Features table name")
    sql_path: str = Field(..., description="SQL file path")
    destination_table: str = Field(..., description="Destination table")
    query_params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")

class MachineTypeConfig(BaseModel):
    machine_type: str = Field(..., description="Machine type")
    accelerator_type: Optional[str] = Field(None, description="Accelerator type")
    accelerator_count: int = Field(default=0, description="Number of accelerators")

class ImageConfig(BaseModel):
    base_image: str = Field(..., description="Base Docker image")
    image_tag: str = Field(default="latest", description="Image tag")

class HyperparameterSpec(BaseModel):
    type: Literal["double", "int", "categorical", "discrete"] = Field(..., description="Parameter type")
    min: Optional[Union[int, float]] = Field(None, description="Minimum value")
    max: Optional[Union[int, float]] = Field(None, description="Maximum value")
    scale: Optional[Literal["linear", "log", "reverse_log"]] = Field(None, description="Scale type")
    values: Optional[List[Union[str, int, float]]] = Field(None, description="Categorical/discrete values")

class ExecutionConfig(BaseModel):
    file_to_run: str = Field(..., description="Python file to execute")
    args: List[str] = Field(default_factory=list, description="Command line arguments")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")

class TuningConfig(BaseModel):
    parallel_trials: int = Field(default=1, ge=1, description="Number of parallel trials")
    max_trials: int = Field(default=10, ge=1, description="Maximum number of trials")
    max_failed_trials: int = Field(default=3, ge=1, description="Maximum failed trials")
    optimization_goal: Literal["maximize", "minimize"] = Field(default="maximize", description="Optimization goal")
    primary_metric: str = Field(..., description="Primary metric to optimize")

class TrainingConfig(BaseModel):
    machine_type: MachineTypeConfig = Field(..., description="Machine configuration")
    image_config: ImageConfig = Field(..., description="Image configuration")
    execution: ExecutionConfig = Field(..., description="Execution configuration")
    hyperparameters: Dict[str, HyperparameterSpec] = Field(..., description="Hyperparameters to tune")
    tuning: TuningConfig = Field(..., description="Tuning configuration")

class EvaluationExecutionConfig(BaseModel):
    timeout_minutes: int = Field(default=30, ge=1, description="Execution timeout")

class EvaluationDataConfig(BaseModel):
    id_column: str = Field(default="id", description="ID column name")
    truth_column: str = Field(default="label", description="Ground truth column name")
    pred_column: str = Field(default="prediction_score", description="Prediction column name")
    ground_truth_table: str = Field(..., description="Ground truth table name")

class EvaluationConfig(BaseModel):
    execution: EvaluationExecutionConfig = Field(..., description="Execution configuration")
    data: EvaluationDataConfig = Field(..., description="Data configuration")

class ModelRegistryApproval(BaseModel):
    auto_approve: bool = Field(default=False, description="Auto-approve model")
    required_metrics: Dict[str, float] = Field(default_factory=dict, description="Required metric thresholds")

class ModelRegistryConfig(BaseModel):
    model_name: str = Field(..., description="Model name")
    version_strategy: Literal["auto_increment", "manual", "semantic"] = Field(default="auto_increment", description="Versioning strategy")
    description: str = Field(..., description="Model description")
    approval: ModelRegistryApproval = Field(..., description="Approval configuration")

# Main pipeline configuration
class PipelineConfig(BaseModel):
    metadata: MetadataConfig = Field(..., description="Configuration metadata")
    runtime: RuntimeConfig = Field(..., description="Runtime configuration")
    bigquery: BigQueryConfig = Field(..., description="BigQuery configuration")
    training: TrainingConfig = Field(..., description="Training configuration")
    evaluation: EvaluationConfig = Field(..., description="Evaluation configuration")
    model_registry: ModelRegistryConfig = Field(..., description="Model registry configuration")

    class Config:
        # Make the config immutable
        allow_mutation = False
        # Validate on assignment
        validate_assignment = True
# Component parameter models for KFP
class ComponentParams(BaseModel):
    """Base class for component parameters with explicit typing"""
    run_id: str = Field(..., description="Unique run identifier")
    cfg_json: str = Field(..., description="Configuration as JSON string")
    
    class Config:
        allow_mutation = False

class TrainingComponentParams(ComponentParams):
    component_type: Literal["training"] = Field(default="training", description="Component type")
    hyperparameters_json: Optional[str] = Field(None, description="Hyperparameters as JSON string")
    trial_id: Optional[str] = Field(None, description="Trial identifier for hyperparameter tuning")

class BigQueryComponentParams(ComponentParams):
    component_type: Literal["bigquery"] = Field(default="bigquery", description="Component type")
    query: str = Field(..., description="SQL query to execute")
    destination_table: Optional[str] = Field(None, description="Destination table")
    query_params_json: Optional[str] = Field(None, description="Query parameters as JSON string")

class EvaluationComponentParams(ComponentParams):
    component_type: Literal["evaluation"] = Field(default="evaluation", description="Component type")
    model_artifact_uri: str = Field(..., description="Model artifact URI")
    test_data_uri: str = Field(..., description="Test data URI")

class ModelRegistryComponentParams(ComponentParams):
    component_type: Literal["model_registry"] = Field(default="model_registry", description="Component type")
    model_artifact_uri: str = Field(..., description="Model artifact URI")
    metrics_json: str = Field(..., description="Model metrics as JSON string")
    model_version: Optional[str] = Field(None, description="Model version")

# Utility functions for parameter handling
def config_to_json(config: PipelineConfig) -> str:
    """Convert config to JSON string for KFP parameter passing"""
    return config.json(exclude_none=True, by_alias=True)

def json_to_config(json_str: str) -> PipelineConfig:
    """Parse JSON string back to config object"""
    return PipelineConfig.parse_raw(json_str)

def safe_json_to_config(json_input) -> PipelineConfig:
    """Safely parse config from JSON, handling both strings and KFP PipelineParameterChannel objects"""
    try:
        # If it's a string, parse directly
        if isinstance(json_input, str):
            return PipelineConfig.parse_raw(json_input)
        
        # If it's a PipelineParameterChannel (in KFP context), we can't parse it
        # Instead, we'll return None and components should handle this case
        else:
            # This will be handled by the components by not parsing config
            # and using passed parameters instead
            raise ValueError("Cannot parse PipelineParameterChannel in KFP context")
            
    except Exception as e:
        raise RuntimeError(f"Config parsing error: {e}")

def validate_hyperparameters(hyperparams_json: str) -> Dict[str, Any]:
    """Validate and parse hyperparameters JSON"""
    try:
        hyperparams = json.loads(hyperparams_json)
        if not isinstance(hyperparams, dict):
            raise ValueError("Hyperparameters must be a dictionary")
        return hyperparams
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid hyperparameters JSON: {e}")

def generate_run_id(prefix: str = "run") -> str:
    """Generate a unique run ID"""
    from datetime import datetime
    import uuid
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{short_uuid}"
