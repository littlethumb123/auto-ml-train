"""Flexible ML Pipeline Definition with Feature Engineering and/or Hyperparameter Tuning."""
from kfp import dsl
from pipeline_helpers import create_custom_training_job_component, create_hyperparameter_tuning_component


@dsl.pipeline(
    name="flexible-ml-pipeline",
    description="Flexible pipeline supporting Feature Engineering and/or Hyperparameter Tuning"
)
def flexible_ml_pipeline(
    # All feature engineering parameters
    project_id: str = "",
    region: str = "",
    cmek_key: str = "",
    pipeline_root: str = "",
    package_uri: str = "",
    python_module: str = "trainer.task",
    service_account: str = "",
    docker_uri: str = "",
    lob: str = "",
    shared_project: str = "",
    gcp_gcp_project: str = "",
    gcp_db: str = "",
    prefix: str = "",
    default_exp: str = "",
    sdoh_year: str = "",
    location: str = "",
    bucket_name: str = "",
    gcs_destination_path: str = "",
    owner: str = "",
    costcenter: str = "",
    unique_id: str = "",
    pipeline_type: str = "",
    expiration_days: int = 7,
    sql_queries: str = "",
    random_seed: int = 35,
    numpy_seed: int = 35,
    embedding_pattern: str = "",
    variance_threshold: float = 0.001,
    target_column: str = "",
    exclude_for_variance: str = "[]",
    exclude_for_classification: str = "[]",
    feature_classification: str = "",
    min_occurrence: int = 2000,
    model_config: str = "",
    undersampling_config: str = "",
    rfecv_config: str = "",
    metrics_config: str = "",
    output_config: str = "",
    bigquery_query_config: str = "",
    machine_type_param: str = "n1-standard-4",
    accelerator_type: str = None,
    accelerator_count: int = 1,
    # Component enable flags
    enable_feature_engineering: bool = True,
    enable_hyperparameter_tuning: bool = True,
    # Hyperparameter tuning parameters
    hp_use_package_module: bool = True,  # Use package module (recommended) or GCS file
    hp_task_file_gcs: str = "",  # Only used if hp_use_package_module is False
    hp_training_table: str = "",  # Optional: existing table (empty = use FE output)
    hp_test_table: str = "",  # Optional: existing table (empty = use FE output)
    hp_sql_queries: str = "",  # Optional: SQL queries for HP tuning (if not using FE output)
    hp_machine_type: str = "n1-standard-8",
    hp_max_trials: int = 10,
    hp_parallel_trials: int = 2,
    hp_max_failed_trials: int = 2,
    hp_id_columns: str = "[]",  # JSON array string
    hp_parameter_spec: str = "{}",  # JSON string with parameter specifications
    hp_eval_metric: str = '{"roc_auc": "maximize"}',  # JSON string with eval metrics
):
    """Flexible pipeline supporting Feature Engineering and/or Hyperparameter Tuning.
    
    Components can be enabled/disabled via enable_feature_engineering and enable_hyperparameter_tuning.
    When both are enabled, they run SEQUENTIALLY: Feature Engineering → Hyperparameter Tuning
    """
    
    # Reconstruct constants dict from parameters
    pipeline_constants = {
        "PROJECT": project_id,
        "COMPUTE_PROJECT": project_id,
        "LOCATION": region,
        "CMEK_KEY": cmek_key,
        "SERVICE_ACCOUNT": service_account,
        "DOCKER_URI": docker_uri,
        "LOB": lob,
        "SHARED_PROJECT": shared_project,
        "LABELS": {
            "owner": owner,
            "costcenter": costcenter,
            "tenant": "hcm-cm-de",
            "self_serve": "true",
            "lob": lob,
            "pipeline_type": pipeline_type
        }
    }
    
    # Step 1: Feature Engineering (runs first if enabled)
    if enable_feature_engineering:
        # Set up environment variables
        env = {
            "GOOGLE_CLOUD_PROJECT": project_id,
            "GCP_PROJECT": project_id,
        }
        
        # Machine type configuration
        machine_type = {
            "machineType": machine_type_param,
        }
        
        # Add accelerator configuration if specified
        # Note: accelerator_type is a PipelineParameterChannel at compile time
        # The notebook handles None/empty conversion before passing to pipeline
        if accelerator_type.value is not None and accelerator_type.value != "NSSull" and accelerator_type.value != "None" and accelerator_type.value != "":
            machine_type["acceleratorType"] = accelerator_type
            machine_type["acceleratorCount"] = accelerator_count
        
        # Build command-line arguments for the training job
        training_args = [
            "--gcp-project", project_id,
            "--gcp-gcp-project", gcp_gcp_project,
            "--gcp-db", gcp_db,
            "--prefix", prefix,
            "--default-exp", default_exp,
            "--sdoh-year", sdoh_year,
            "--location", location,
            "--bucket-name", bucket_name,
            "--gcs-destination-path", gcs_destination_path,
            "--owner", owner,
            "--costcenter", costcenter,
            "--unique-id", unique_id,
            "--pipeline-type", pipeline_type,
            "--lob", lob,
            "--expiration-days", str(expiration_days),
            "--sql-queries", sql_queries,
            "--random-seed", str(random_seed),
            "--numpy-seed", str(numpy_seed),
            "--embedding-pattern", embedding_pattern,
            "--variance-threshold", str(variance_threshold),
            "--target-column", target_column,
            "--exclude-for-variance", exclude_for_variance,
            "--exclude-for-classification", exclude_for_classification,
            "--feature-classification", feature_classification,
            "--min-occurrence", str(min_occurrence),
            "--model-config", model_config,
            "--undersampling-config", undersampling_config,
            "--rfecv-config", rfecv_config,
            "--metrics-config", metrics_config,
            "--output-config", output_config,
            "--bigquery-query-config", bigquery_query_config,
        ]
        
        # Create feature engineering job
        feature_eng_job = create_custom_training_job_component(
            pipeline_root=pipeline_root,
            constants=pipeline_constants,
            machine_type=machine_type,
            package_uris=[package_uri],
            python_module=python_module,
            display_name="feature-engineering-training",
            env=env,
            args=training_args,
        )
        
        print("✅ Feature Engineering component created")
        print(f"   Output tables will be: {gcp_gcp_project}.{gcp_db}.{prefix}_selected_features_train")
        print(f"                          {gcp_gcp_project}.{gcp_db}.{prefix}_selected_features_test")
    
    # Step 2: Hyperparameter Tuning (runs after FE if both enabled, or standalone)
    if enable_hyperparameter_tuning:
        from google.cloud.aiplatform import hyperparameter_tuning as hpt
        
        # Reconstruct constants for hyperparameter tuning
        hp_constants = {
            "PROJECT": project_id,
            "COMPUTE_PROJECT": project_id,
            "LOCATION": region,
            "CMEK_KEY": cmek_key,
            "SERVICE_ACCOUNT": service_account,
            "DOCKER_URI": docker_uri,
            "LOB": lob,
            "SHARED_PROJECT": shared_project,
            "LABELS": {
                "owner": owner,
                "costcenter": costcenter,
                "tenant": "hcm-cm-de",
                "self_serve": "true",
                "lob": lob,
                "pipeline_type": "hyperparameter_tuning"
            }
        }
        
        # Determine table names for hyperparameter tuning
        # Priority: 1) User-provided tables from config, 2) Feature engineering output tables
        # Note: At compile time, these are PipelineParameterChannel objects, not strings
        # We construct the table names based on the parameters provided
        
        # Use feature engineering output tables (fixed names from config)
        # These will be constructed at runtime using the pattern from config.yaml
        training_table_for_hp = None
        test_table_for_hp = None
        
        # Construct table names based on enable flags and parameters
        # The actual decision logic happens at runtime through the component
        if enable_feature_engineering:
            # Use FE output tables (unless user provides override via hp_training_table)
            # Table names follow the pattern from config.yaml output section
            training_table_for_hp = f"{gcp_gcp_project}.{gcp_db}.{prefix}_selected_features_train"
            test_table_for_hp = f"{gcp_gcp_project}.{gcp_db}.{prefix}_selected_features_test"
        else:
            # User must provide tables via hp_training_table and hp_test_table parameters
            # These come from the config.yaml hyperparameter_tuning section
            training_table_for_hp = hp_training_table
            test_table_for_hp = hp_test_table
        
        # Build hyperparameter tuning args
        hp_args = [
            "--project", project_id,
            "--training_table", training_table_for_hp,
            "--target_column", target_column,
            "--model_dir", f"{pipeline_root}/models",
        ]
        
        # Add test table if provided (at runtime, empty strings will be handled by the component)
        hp_args.extend(["--test_table", test_table_for_hp])
        
        # Add ID columns - use from config if available, otherwise from parameter
        try:
            # Try to get ID columns from config (set in notebook)
            id_cols_list = _hp_id_columns_from_config
        except NameError:
            # Fallback: parse from parameter
            import json
            try:
                id_cols_list = json.loads(hp_id_columns) if hp_id_columns else []
            except:
                id_cols_list = []
        
        # Add ID columns to args if provided
        if id_cols_list:
            hp_args.extend(["--id_columns"] + id_cols_list)
        
        # Construct parameter spec from config.yaml (loaded in notebook)
        try:
            # This will be set in the notebook cell before pipeline definition
            param_spec_dict = _hp_parameter_spec_from_config
        except NameError:
            # Default parameter spec if not set
            param_spec_dict = {
                'eta': hpt.DoubleParameterSpec(min=0.01, max=0.15, scale='log'),
                'max_depth': hpt.IntegerParameterSpec(min=4, max=16, scale='linear'),
                'num_boost_round': hpt.IntegerParameterSpec(min=100, max=7000, scale='linear'),
                'subsample': hpt.DoubleParameterSpec(min=0.3, max=1.0, scale='linear'),
                'colsample_bytree': hpt.DoubleParameterSpec(min=0.3, max=1.0, scale='linear'),
                'min_child_weight': hpt.IntegerParameterSpec(min=1, max=20, scale='linear'),
                'reg_lambda': hpt.DoubleParameterSpec(min=0.1, max=10, scale='log'),
                'scale_pos_weight': hpt.DoubleParameterSpec(min=10.0, max=30.0, scale='linear'),
            }
        
        # Try to use eval metric from config if available
        try:
            eval_metric_dict = _hp_eval_metric_from_config
        except NameError:
            import json
            try:
                eval_metric_dict = json.loads(hp_eval_metric) if hp_eval_metric else {"roc_auc": "maximize"}
            except:
                eval_metric_dict = {"roc_auc": "maximize"}
        
        # Create hyperparameter tuning component
        # Use package module if enabled, otherwise use GCS file (legacy)
        if hp_use_package_module:
            hp_tune_job = create_hyperparameter_tuning_component(
                pipeline_root=pipeline_root,
                constants=hp_constants,
                machine_type={"machine_type": hp_machine_type},
                python_module="trainer.hp_tuning.task",  # Use package module
                package_uris=[package_uri],  # Same package as feature engineering
                parameter_spec=param_spec_dict,
                eval_metric=eval_metric_dict,
                parallel_trials=hp_parallel_trials,
                max_trials=hp_max_trials,
                max_failed_trials=hp_max_failed_trials,
                args=hp_args,
            )
        else:
            # Legacy: Use GCS file
            hp_tune_job = create_hyperparameter_tuning_component(
                pipeline_root=pipeline_root,
                constants=hp_constants,
                machine_type={"machine_type": hp_machine_type},
                file_to_run=hp_task_file_gcs,  # Legacy: GCS file
                parameter_spec=param_spec_dict,
                eval_metric=eval_metric_dict,
                parallel_trials=hp_parallel_trials,
                max_trials=hp_max_trials,
                max_failed_trials=hp_max_failed_trials,
                args=hp_args,
            )
        
        # CRITICAL: Set sequential execution order
        # If feature engineering is enabled, HP tuning MUST wait for it to complete
        if enable_feature_engineering:
            hp_tune_job.after(feature_eng_job)
            print("✅ Pipeline configured for SEQUENTIAL execution:")
            print("   1️⃣  Feature Engineering (creates tables)")
            print("   2️⃣  Hyperparameter Tuning (uses those tables)")
        else:
            print("✅ HP Tuning will run standalone (using existing tables)")
    
    # Summary
    if enable_feature_engineering and enable_hyperparameter_tuning:
        print("\n🎯 Pipeline Mode: FULL PIPELINE (FE → HP)")
    elif enable_feature_engineering:
        print("\n🎯 Pipeline Mode: FEATURE ENGINEERING ONLY")
    elif enable_hyperparameter_tuning:
        print("\n🎯 Pipeline Mode: HYPERPARAMETER TUNING ONLY")

