import datetime
import os
import json
from typing import Any, Dict, List, Optional, Text, Tuple, Union, Sequence, Callable
from time import time
from cytoolz.curried import merge, keymap
import utils.gcp_handling

from google_cloud_pipeline_components.types import artifact_types
from google_cloud_pipeline_components.preview import (
    custom_job as persistent_job,
    dataflow as dataflow_flex,
    llm,
)
from google_cloud_pipeline_components.v1 import (
    bigquery,
    custom_job,
    endpoint,
    model,
    vertex_notification_email,
    model_evaluation,
    batch_predict_job,
    dataflow,
    wait_gcp_resources,
    dataproc,
    hyperparameter_tuning_job,
)

# kfp.v2 alias may be deprecated soon, can use `from kfp import ...`
from kfp.v2 import dsl, compiler, components
from kfp.v2.dsl import Artifact, Input
from google.cloud.aiplatform import hyperparameter_tuning as hpt

from google.cloud.aiplatform_v1 import MetadataServiceClient
from google.cloud.aiplatform_v1.types import Artifact


def send_completion_email_component(constants: dict) -> dsl.component:
    """A helpful kfp component to send an email upon success/failure of KFP pipeline"""

    email = constants["EMAIL"]

    email_sender = vertex_notification_email.VertexNotificationEmailOp(
        recipients=[email]
    )

    return email_sender


def get_cost_owner():
    costcenter = os.environ.get("COSTCENTER")
    if not costcenter:
        raise KeyError(
            "COSTCENTER environment variable does not exist, please set this via the command line."
        )
    owner = os.environ.get("OWNER")
    if not owner:
        raise KeyError(
            "OWNER environment variable deos not exist, please set this via the command line following the formatting below https://github.aetna.com/abc-cloud/abc-gcp-onboarding/blob/master/bigquery/README.md#2-label-requirements"
        )
    return costcenter, owner


def create_component_config(
    sql_inputs: list,
    drop_created_table: Optional[bool] = True
) -> dict:
    """A helper function for more powerful BQ component use, to allow
    DDL statements and BQ functions"""

    sql_query, table_name, sql_functions = sql_inputs
    
    if table_name is not None:
        sql_query = (
            get_sql_create_table(sql_query, table_name)
            if drop_created_table
            else get_sql_create_exists(sql_query, table_name)
        )
        
    if sql_functions is not None:
        sql_query = sql_functions + sql_query

    job_configuration_query = {
        "query": sql_query,
        "useQueryCache": True,
    }

    return job_configuration_query


def get_sql_create_table(
    sql: str, table_name: str, prepend_sql: Optional[str] = None
) -> str:
    """A helper function to add DDL with the correct BQ labels for
    CREATE OR REPLACE in BQ"""

    costcenter, owner = get_cost_owner()
    if prepend_sql is None:
        prepend_sql = ""

    table_modifier = ""
    if table_name:
        table_modifier = f"""
            CREATE OR REPLACE TABLE `{table_name}` 
            options (
                labels=[("owner", "{owner}"),("costcenter","{costcenter}")]  
            )
            AS 
        """

    sql_preamble = f"""
    {prepend_sql}
    {table_modifier}
    """
    sql_create = sql_preamble + sql
    return sql_create


def get_sql_create_exists(
    sql: str, table_name: str, prepend_sql: Optional[str] = None
) -> str:
    """A helper function to add DDL with the correct BQ labels for
    CREATE IF NOT EXISTS in BQ"""

    costcenter, owner = get_cost_owner()
    if prepend_sql is None:
        prepend_sql = ""

    table_modifier = ""
    if table_name:
        table_modifier = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}`
            options(
                labels=[("owner", "{owner}"),("costcenter","{costcenter}")]
            )
            AS
        """

    sql_preamble = f"""
    {prepend_sql}
    {table_modifier}
    """
    sql_create = sql_preamble + sql
    return sql_create


def query_bigquery_component(
    constants: dict,
    query: str,
    destination_table: Optional[str] = None,
    sql_functions: Optional[str] = None,
    display_name: Optional[str] = None,
) -> dsl.component:
    """A wrapper to call BQ services. Useful for running jobs that can last up to 6 hours
    inputs:
        constants: dict - this has been created based on inputs in notebook 2 and is
            added as an argument to the pipeline
        query: str - BQ query string to run
        destination_table: Optional[str] - Best practice to pass a query with output table name --
            destination_table is the name of the table the query should be written to
        sql_functions: Optional[str] - Any customized BQ functions required for your query to run
        display_name: Optional[str] - A custom display name, if desired. Defaults to destination_table
    """

    if not display_name and destination_table is not None:
        display_name = f"build_{destination_table}"

    return bigquery.BigqueryQueryJobOp(
        job_configuration_query=create_component_config(
            sql_inputs=[query, destination_table, sql_functions]
        ),
        **constant_bq_args(constants),
    ).set_display_name(display_name)


def bq_export_query_component(
    constants: str, query: str, gcs_location: str, compress: Optional[bool] = True
) -> dsl.component:
    """A wrapper to use BQ to export a query without using intermediate table

    inputs:
        constants: dict - this has been created based on inputs in notebook 2 and is
            added as an argument to the pipeline
        query: str - BQ query string to run
        gcs_location: str - Location to extract parquets to. Should be a directory in which
            to write a variable number of parquets
        compress: Optional[bool] - Whether to use snappy compression
    """
    compression = ",compression='SNAPPY'" if compress else ""

    return bigquery.BigqueryQueryJobOp(
        job_configuration_query={
            "query": f"""
                EXPORT DATA
                  OPTIONS (
                    uri="{gcs_location}/*.parquet"
                    ,format='Parquet'
                    ,overwrite=true
                    {compression}
                )
                AS (
                  {query}
                );""".replace(
                "\n", " "
            ),
            "useQueryCache": True,
        },
        **constant_bq_args(constants),
    ).set_display_name(f"extract_to_{gcs_location}")


def bq_export_table_component(
    constants: str, table_name: str, gcs_location: str, compress: Optional[bool] = True
) -> dsl.component:
    """A wrapper to use BQ to export an existing table

    inputs:
        constants: dict - this has been created based on inputs in notebook 2 and is
            added as an argument to the pipeline
        table_name: str - BQ table to be exported
        gcs_location: str - Location to extract parquets to. Should be a directory in which
            to write a variable number of parquets
        compress: Optional[bool] - Whether to use snappy compression
    """
    compression = ",compression='SNAPPY'" if compress else ""

    return bigquery.BigqueryQueryJobOp(
        job_configuration_query={
            "query": f"""
                EXPORT DATA
                  OPTIONS (
                    uri="{gcs_location}/*.parquet"
                    ,format='Parquet'
                    ,overwrite=true
                    {compression}
                )
                AS (
                  SELECT *
                  FROM `{table_name}`
                );""".replace(
                "\n", " "
            ),
            "useQueryCache": True,
        },
        **constant_bq_args(constants),
    ).set_display_name(f"extract_{table_name}")


def create_bq_model(
    constants,
    model_type,
    input_label_cols,
    training_table=None,
    training_query=None,
    *args,
    **kwargs,
):
    # Need to handle additional "OPTIONS" with *args, **kwargs...

    if training_table and training_query:
        raise ValueError("Please specify table OR query but not both")

    if training_table:
        source = "`" + training_table + "`"
    if training_query:
        source = f"( {training_query} )"

    model_query = f"""
        CREATE OR REPLACE MODEL `{constants["DB_PREFIX"]}.{constants["MODEL_NAME"]}`
            OPTIONS(
                model_type='{model_type}',
                input_label_cols={input_label_cols},
                DATA_SPLIT_METHOD='AUTO_SPLIT',
                ENABLE_GLOBAL_EXPLAIN=TRUE
            ) AS
            SELECT *
            FROM {source}
    """

    train_job = bigquery.BigqueryCreateModelJobOp(
        query=model_query,
        **constant_bq_args(constants),
    )

    return train_job


def explain_bq_model(constants, model_name=None, kf_model=None):
    if model_name and kf_model:
        raise ValueError(
            "Only supply one of the model_name or the kubeflow component with the model as an output"
        )

    if model_name:
        model = model_name
    if kf_model:
        model = kf_model.outputs["model"]

    explainability_job = bigquery.BigqueryMLGlobalExplainJobOp(
        model=model,
        **constant_bq_args(constants),
    )
    return explainability_job


def export_bq_model(pipeline_root, constants, model_name=None, kf_model=None):
    if model_name and kf_model:
        raise ValueError(
            "Only supply one of the model_name or the kubeflow component with the model as an output"
        )

    if model_name:
        model = model_name
    if kf_model:
        model = kf_model.outputs["model"]

    export_model = bigquery.BigqueryExportModelJobOp(
        model=model,
        model_destination_path=f"{pipeline_root}/model",
        **constant_bq_args(constants),
    )

    return export_model


def predict_bq_model(
    constants,
    validation_table_name,
    write_disposition="WRITE_APPEND",
    model_name=None,
    kf_model=None,
):
    if model_name and kf_model:
        raise ValueError(
            "Only supply one of the model_name or the kubeflow component with the model as an output"
        )

    if model_name:
        model = model_name
    if kf_model:
        model = kf_model.outputs["model"]

    offline_predict = bigquery.BigqueryPredictModelJobOp(
        model=model,
        table_name=validation_table_name,
        job_configuration_query={
            "createDisposition": "CREATE_IF_NEEDED",
            "writeDisposition": write_disposition,
            "destinationTable": {
                "projectId": constants["SHARED_PROJECT"],
                "datasetId": constants["TENANCY"],
                "tableId": f"{constants['MODEL_NAME']}_{constants['MODEL_TIMESTAMP']}_val_preds",
            },
        },
        **constant_bq_args(constants),
    )

    return offline_predict


def eval_bq_model(
    constants, write_disposition="WRITE_TRUNCATE", model_name=None, kf_model=None
):
    if model_name and kf_model:
        raise ValueError(
            "Only supply one of the model_name or the kubeflow component with the model as an output"
        )

    if model_name:
        model = model_name
    if kf_model:
        model = kf_model.outputs["model"]

    model_evaluate = bigquery.BigqueryEvaluateModelJobOp(
        model=model,
        job_configuration_query={
            "createDisposition": "CREATE_IF_NEEDED",
            "writeDisposition": write_disposition,
            "destinationTable": {
                "projectId": constants["SHARED_PROJECT"],
                "datasetId": constants["TENANCY"],
                "tableId": f"{constants['MODEL_NAME']}_evaluate_{constants['MODEL_TIMESTAMP']}",
            },
        },
        **constant_bq_args(constants),
    )
    return model_evaluate


def dataflow_job_component(
    pipeline_root: str,
    constants: dict,
    pipeline_file_gcs_uri: str,
    requirements_file_gcs_uri: str,
    args: Optional[List[Any]] = None,
) -> List[dsl.component]:
    """EXPERIMENTAL

    Component to trigger standard dataflow jobs requiring only simple installations from pypi

    Uses await op to ensure that job finishes rather than just being started remotely

    inputs:
        pipeline_root: str - GCS path in which to save any artifacts using environment vars
        constants: dict - this has been created based on inputs in notebook 2 and is
            added as an argument to the pipeline
        pipeline_file_gcs_uri: str - The GCS path of the python file of the apache beam pipeline.
        requirements_file_gcs_uri: str
        args: Optional[List[Any]] - Arguments to be passed to DataFlow job
    """

    project, service_account, cmek_key = required_kf_info(constants)

    args = [] if args is None else args
    args.extend(
        [
            "--dataflow_kms_key",
            cmek_key,
            "--service_account_email",
            constants["SERVICE_ACCOUNT"],
            "--experiments",
            "use_runner_v2",
            "--subnetwork",
            constants["SUBNETWORK"],
            "--no_use_public_ips",
            "--requirements_file",
            requirements_file_gcs_uri,
        ]
    )

    print(f"args: {args}")
    args = remove_duplicate_args(args)
    dataflow_trigger_job = dataflow.DataflowPythonJobOp(
        python_module_path=pipeline_file_gcs_uri,
        args=args,
        project=project,
        location=constants["LOCATION"],
        temp_location=f"{pipeline_root}/dataflow/temp",
    )

    dataflow_wait_op = wait_gcp_resources.WaitGcpResourcesOp(
        gcp_resources=dataflow_trigger_job.outputs["gcp_resources"]
    ).set_display_name(f"await_dataflow_job")

    dataflow_wait_op.after(dataflow_trigger_job)

    return [dataflow_trigger_job, dataflow_wait_op]


def dataflow_flex_template_component(
    pipeline_root: str,
    constants: dict,
    dataflow_template_path: str = None,
    max_workers: int = 500,
    job_name: str = "job",
) -> List[dsl.component]:
    """Component to trigger flex template dataflow jobs requiring specific configuration(s)
    from inside composer regarding the container to be used and the functionality

    Uses await op to ensure that job finishes rather than just being started remotely

    inputs:
        pipeline_root: str - GCS path in which to save any artifacts using environment vars
        constants: dict - this has been created based on inputs in notebook 2 and is
            added as an argument to the pipeline
        dataflow_template_path: str - GCS path pointing to flex template artifact
        max_workers: int - Maximum number of e2-standard-(2/4) computers to use in the job
        job_name: str: A way to set the display name in a custom way
    """

    project, service_account, cmek_key = required_kf_info(constants)

    dataflow_trigger_job = dataflow_flex.DataflowFlexTemplateJobOp(
        container_spec_gcs_path=constants.get("DATAFLOW_PATH", dataflow_template_path),
        job_name=job_name,
        max_workers=max_workers,
        location=constants["LOCATION"],
        service_account_email=service_account,
        kms_key_name=cmek_key,
        project=project,
        additional_user_labels=constants["LABELS"],
        temp_location=f"{pipeline_root}/dataflow/temp",
        staging_location=f"{pipeline_root}/dataflow/staging",
    ).set_display_name(f"dataflow_{job_name}")

    dataflow_wait_op = wait_gcp_resources.WaitGcpResourcesOp(
        gcp_resources=dataflow_trigger_job.outputs["gcp_resources"]
    ).set_display_name(f"await_{job_name}")

    dataflow_wait_op.after(dataflow_trigger_job)

    return [dataflow_trigger_job, dataflow_wait_op]


def dataproc_job_component(
    pipeline_root: str,
    constants: dict,
    file_to_run: str,
) -> dsl.component:
    """EXPERIMENTAL

    Component to trigger dataproc jobs in a stateless fashion

    inputs:
        pipeline_root: str - GCS path in which to save any artifacts using environment vars
        constants: dict - this has been created based on inputs in notebook 2 and is
            added as an argument to the pipeline
        file_to_run: str - The file in `my_repo` that should be run
    """

    project, service_account, cmek_key = required_kf_info(constants)

    # TODO: a831018
    # runtime_config_version,
    # runtime_config_properties,
    # network_tags,
    # network_uri,
    # subnetwork_uri,
    # metastore_service,
    # spark_history_dataproc_cluster,
    # python_file_uris,
    # jar_file_uris,
    # file_uris,
    # archive_uris,
    # args,

    return dataproc.DataprocPySparkBatchOp(
        main_python_file_uri=file_to_run,
        batch_id="",
        # runtime_config_version: str = '',
        # runtime_config_properties: dict[str, str] = {},
        # network_tags: list[str] = [],
        # network_uri: str = '',
        # subnetwork_uri: str = '',
        # metastore_service: str = '',
        # spark_history_dataproc_cluster: str = '',
        # python_file_uris: list[str] = [],
        # jar_file_uris: list[str] = [],
        # file_uris=[],
        # archive_uris=[],
        # args=[],
        container_image=constants["DOCKER_URI"],
        location=constants["LOCATION"],
        project=project,
        labels=constants["LABELS"],
        kms_key=cmek_key,
        service_account=service_account,
    )


def generate_compute_environment(pipeline_root: str, constants: dict, env: dict = None):

    base_env = {
        "PYTHONPATH": "$PYTHONPATH:/home/jupyter/my_repo/:/home/jupyter/builtin_scripts",
        "LOB": constants["LOB"],
        "PROJECT": constants["PROJECT"],
        "COMPUTE_PROJECT": constants["COMPUTE_PROJECT"] or "False",
        "SHARED_PROJECT": constants["SHARED_PROJECT"],
        "AIP_DIR": pipeline_root,
        **keymap(lambda k: k.upper(), constants["LABELS"]),
    }

    env = env or {}
    final_env = merge(base_env, env)
    final_env = [{"name": k, "value": str(v)} for k, v in final_env.items() if v]

    return final_env


def vertex_paramter_tuning_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    file_to_run: str,
    parameter_spec: dict,
    eval_metric: dict = {"f1": "maximize"},
    parallel_trials: int = 1,
    max_trials: Optional[int] = 8,
    max_failed_trials: Optional[int] = 2,
    args: Optional[List[Any]] = None,
    env: Optional[Dict[str, Any]] = None,
) -> dsl.component:
    """A component to trigger a training job that has been set up to run
    with the hyperparameters passed in the function. An example of that
    dictionary is below. This is part of the Vertex Managed Vizier /
    HyperParameter Tuning service

    The default search is a Bayesian Optimization search. For Random Search,
    set parallel_trials == max_trials

    Worker pool spec may need to be modified in the case of using a cluster
    if the job cannot be run on 1 (potentially very large) machine. In this
    case, you might want to prefer DataProc

    inputs:
        pipeline_root: str - GCS location to provide to the environment of the job
        constants: dict,
        machine_type: dict - A compatible machine type for running the trials
        file_to_run: str - A path from `my_repo` which contains the training logic and
            arg parser
        parameter_spec: dict - A dictionary with the `hpt.X` values as the parameter space(s)
        parallel_trials: int - How many trials to run in parallel
        eval_metric: dict - The key is the metric to be watched, and the value is the ideal direction
            For f1 or accuracy, "maximize" but for log_loss, "minimize"
        max_trials: Optional[int] - The maximum number of trials
        max_failed_trials: Optional[int] - How many trials can fail before the job is cancelled
        args: Optional[List[Any]] - Arguments to be passed to the container, if any
        env: Optional[Dict[str, Any]] - Environment vars to be passed to the container
    """

    project, service_account, cmek_key = required_kf_info(constants)

    ENV = generate_compute_environment(pipeline_root, constants, env)

    # Example parameter_spec
    # parameter_spec = {
    #     'eta': hpt.DoubleParameterSpec(min=0, max=1, scale='linear')
    #     , 'n-estimators': hpt.IntegerParameterSpec(min=10, max=1000, scale='linear')
    #     , 'max-depth': hpt.IntegerParameterSpec(min=1, max=10, scale='linear')
    #     , 'gamma': hpt.DoubleParameterSpec(min=0, max=3, scale='linear')
    #     , 'min-child-weight': hpt.IntegerParameterSpec(min=1, max=10, scale='linear')
    #     , 'colsample-bytree': hpt.DoubleParameterSpec(min=0, max=1, scale='linear')
    #     , 'subsample': hpt.DoubleParameterSpec(min=0, max=1, scale='linear')
    # }

    kfp_parameter_spec = hyperparameter_tuning_job.serialize_parameters(parameter_spec)

    worker_pool_specs = [
        {
            "machine_spec": {**machine_type},
            "replica_count": 1,
            "container_spec": {
                "image_uri": constants["DOCKER_URI"],
                "command": ["python3", file_to_run],
                "args": args or [],
                "env": ENV,
            },
        }
    ]

    metrics = hyperparameter_tuning_job.serialize_metrics(eval_metric)

    hp_tune = hyperparameter_tuning_job.HyperparameterTuningJobRunOp(
        display_name="self_serve_hptune",
        study_spec_metrics=metrics,
        study_spec_parameters=kfp_parameter_spec,
        max_trial_count=max_trials,
        parallel_trial_count=parallel_trials,
        max_failed_trial_count=min(max_failed_trials, max_trials - 1),
        # study_spec_algorithm: str = 'ALGORITHM_UNSPECIFIED',  # Bayes-Opt
        # study_spec_measurement_selection_type: str = 'BEST_MEASUREMENT',
        # network: str = ''
        worker_pool_specs=worker_pool_specs,
        base_output_directory=f"{pipeline_root}/hp_tuning",
        encryption_spec_key_name=cmek_key,
        service_account=service_account,
        location=constants["LOCATION"],
        project=project,
    )

    return hp_tune


def customjob_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    file_to_run: str,
    display_name: str,
    env: Optional[dict] = None,
    args: Optional[List[str]] = None,
    persistent_resource_id: Optional[str] = None,
) -> dsl.component:
    """

    inputs:
        pipeline_root: str - GCS path to give to the training job for save locations
        constants: dict - Dict created in notebook 2 and passed through the pipeline fn
        machine_type: dict - Dict formatted for valid GCP machine types
        file_to_run: str - The path for the file to be run from `my_repo`
        display_name: str - A custom name for demarcating one job vs another
        env: Optional[dict] - Any additional parameters to add to the environment
        args: Optional[List[str]] - Args to be passed to the container at runtime;
            split the arg whitespace into a new string. For instance:
                ["--arg1=something --arg2 something_else"] ->
                    ["--arg1=something", "--arg2", "something_else"]
            Not recommended. Prefer to use environment variables due to enhanced formatting
            forcing / alignment
        persistent_resource_id: Optional[str] - A string resource id for any reserved GPUs or
            other compute resources
    """

    project, service_account, cmek_key = required_kf_info(constants)

    ENV = generate_compute_environment(pipeline_root, constants, env)

    kwargs = {
        "project": str(project),
        "display_name": display_name,
        "location": constants["LOCATION"],
        "worker_pool_specs": [
            {
                "machineSpec": {**machine_type},
                "replicaCount": "1",
                "containerSpec": {
                    "imageUri": constants["DOCKER_URI"],
                    "command": ["python3", file_to_run],
                    "env": ENV,
                    "args": args or [],
                },
            }
        ],
        "labels": constants["LABELS"],
        "base_output_directory": os.getenv("AIP_MODEL_DIR", pipeline_root),
    }

    if persistent_resource_id:
        disk_spec = {
            "disk_spec": {
                "bootDiskType": "pd-standard",
                "bootDiskSizeGb": 200,
            }
        }

        kwargs["worker_pool_specs"].update(disk_spec)

        custom_job_component = persistent_job.CustomTrainingJobOp(
            # service_account=service_account, # Might be necessary?
            persistent_resource_id=persistent_resource_id,
            timeout="2700000s",  # 3+ weeks
            **kwargs,
        )

    else:
        custom_job_component = custom_job.CustomTrainingJobOp(
            service_account=service_account, encryption_spec_key_name=cmek_key, **kwargs
        )

    custom_job_component.set_display_name(display_name)

    return custom_job_component


def artifact_importer_component(
    constants: dict,
    artifact_uri: str,
    metadata_configuration: Optional[dict] = None,
    artifact_class: artifact_types = artifact_types.UnmanagedContainerModel,
) -> dsl.component:
    """A component to import artifacts represented by URIs through
    Vertex, in particular to acknowledge/load these URIs in other processes

    inputs:
        constants: dict - Dict created in notebook 2 to provide useful information;
            injected from pipeline fn
        artifact_uri: str - The location of the item. Can be a GCS link or
            potentially a BQ table string; further information at
            https://google-cloud-pipeline-components.readthedocs.io/en/latest/api/artifact_types.html
        metadata_configuration: Optional[dict] - Most likely a ContainerSpec for an
            UnmanagedContainerModel
        artifact_class: google_cloud_pipeline_components.types.artifact_types typically;
            see the link to better understand how these are structured and other details
            https://google-cloud-pipeline-components.readthedocs.io/en/latest/api/artifact_types.html
    """

    if not metadata_configuration:
        metadata_configuration = {}

    return dsl.importer(
        artifact_uri=artifact_uri,
        artifact_class=artifact_class,
        metadata=metadata_configuration,
    )


def vertex_model_importer_component(
    pipeline_root: str, constants: dict, model_registry_id: Union[str, int]
) -> dsl.component:
    """A component to retrieve a model from Vertex Model Registry to be passed
    along to other downstream components

    inputs:
        pipeline_root: str - GCS path to give to the training job for save locations
        constants: dict - Dict created in notebook 2 to provide useful information;
            injected from pipeline fn
        model_registry_id: Union[str, int] - The integer ID of the model registry item
            that should be loaded and predicted from
    """

    project, _, _ = required_kf_info(constants)

    return model.ModelGetOp(
        model_name=model_registry_id,
        project=project,
        location=constants["LOCATION"],
    )


def vertex_model_upload_component(
    pipeline_root: str,
    constants: dict,
    imported_model: dsl.component,
    extended_description: str,
    extra_args: Optional[Dict] = None,
) -> dsl.component:
    """A component to use the Vertex Batch Prediction Managed Service.
    A little bit naughty, but overall scales well. Uses DataFlow in the
    background to provide extremely scalable inference.

    May need to configure a `server.py` if your input_source data needs
    to be transformed from the endpoint that is spun up.

    inputs:
        pipeline_root: str - GCS path to give to the training job for save locations
        constants: dict - Dict created in notebook 2 to provide useful information;
            injected from pipeline fn
        imported_model: dsl.component - Should be a component of the model.ModelGetOp
            variety. Vertex model registry want to load the other information from
            getting that model. Use model_registry_id with `vertex_model_importer_component`
        extended_description: str - Additional information to be passed along to the
            Vertex Model Registry
        extra_args: Optional[Dict] - This largely is used to handle the situation
            where you want to provide lineage ("Parent Models") to the Model
            Registry in order to keep the interface clean and indicate model
            versioning. See use in the `model_registry_upload_subpipeline` in
            subpipelines.py
    """

    if not extra_args:
        extra_args = {}

    project, service_account, cmek_key = required_kf_info(constants)

    return model.ModelUploadOp(
        display_name=f"{constants['MODEL_NAME']}",
        unmanaged_container_model=imported_model.outputs["artifact"],
        version_aliases=[
            constants.get("VERTEX_MODEL_ALIAS", f"t{constants['MODEL_TIMESTAMP']}"),
            "default",
        ],
        description=f"""
            A Self Service Deployment Repo
            {extended_description}
        """,
        encryption_spec_key_name=cmek_key,
        location=constants["LOCATION"],
        project=project,
        labels=constants["LABELS"],
        **extra_args,
    )


def vertex_batch_prediction_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    destination_table: str,
    input_source: str,
    model_registry_id: Optional[Union[str, int]] = None,
    parent_model: Optional[artifact_types.VertexModel] = None,
    manual_batch_size: Optional[int] = None,
    max_replica_count: Optional[int] = 16,
) -> List[dsl.component]:
    """A component to use the Vertex Batch Prediction Managed Service.
    A little bit naughty, but overall scales well. Uses DataFlow in the
    background to provide extremely scalable inference.

    May need to configure a `server.py` if your input_source data needs
    to be transformed from the endpoint that is spun up.

    inputs:
        pipeline_root: str - GCS path to help with saved artifacts etc
        constants: dict - Dict created in notebook 2 to provide useful information;
            injected from pipeline fn
        machine_type: dict - A compatible GCP machine dictionary
        destination_table: str - A table name (not project or dataset) where to
            store output predictions
        input_source: str - The full BQ path to the table where the rows are to be
            predicted
        model_registry_id: Optional[Union[str, int]] - The integer ID of the model registry item
            that should be loaded and predicted from
        parent_model: Optional[artifact_types.VertexModel] - A way to pass in an existing Vertex model;
            This can come from model.ModelGetOp or potentially other sources
        manual_batch_size: Optional[int] - Set a manual batch size (probably not recommended)
        max_replica_count: Optional[int] - How many machines to use. No autoscaling (see note)
    """

    project, service_account, cmek_key = required_kf_info(constants)

    final_kwargs = manipulate_args_batch_predict(
        machine_type, input_source, manual_batch_size
    )

    if model_registry_id and not parent_model:
        parent_model = model.ModelGetOp(
            model_name=f"{model_registry_id}@t{constants['MODEL_TIMESTAMP']}",
            project=project,
            location=constants["LOCATION"],
        )

    inference = batch_predict_job.ModelBatchPredictOp(
        job_display_name=f"{constants['SERVE_VERSION']}_bp_{destination_table}",
        model=parent_model.outputs["model"],
        predictions_format="bigquery",
        bigquery_destination_output_uri=f"{constants['DB_PREFIX']}.{destination_table}_{str(int(time()))}",
        excluded_fields=["label", "entity_id", "observation_dt"],
        max_replica_count=max_replica_count,
        starting_replica_count=max_replica_count,  # See note below
        location=constants["LOCATION"],
        project=project,
        labels=constants["LABELS"],
        encryption_spec_key_name=cmek_key,
        service_account=service_account,  # constants['BQ_CMEK_KEY_COMPUTE_PROJECT'] # ? because of writing to BQ
        **final_kwargs,
    ).after(parent_model)

    """
    5/9/2024: https://cloud.google.com/vertex-ai/docs/predictions/get-batch-predictions
    Unlike online prediction, batch prediction jobs do not autoscale.
    Because all of the input data is known up front, the system partitions
    the data to each replica when the job starts. The system uses the 
    starting_replica_count parameter; the max_replica_count parameter is ignored.
    """

    return [parent_model, inference]


def vertex_evaluation_component(
    constants: dict,
    model_kfp: artifact_types.VertexModel,
    batch_predict_kfp: artifact_types.VertexBatchPredictionJob,
    # destination_table: str,
) -> dsl.component:
    """EXPERIMENTAL

    A way to pass batch predictions to an evaluation service that generates
    a profile of Classification Related graphs and calculations that are
    stored in the Vertex Model Registry entry

    Currently (7/31/2024) tempermental due to a formatting issue with
    bigquery outputs in BatchPredict
    """

    project, service_account, cmek_key = required_kf_info(constants)

    return model_evaluation.ModelEvaluationClassificationOp(
        target_field_name="label",
        model=model_kfp.outputs["model"],
        location=constants["LOCATION"],
        predictions_format="bigquery",
        predictions_bigquery_source=batch_predict_kfp.outputs["bigquery_output_table"],
        prediction_score_column="",  # 'prediction.scores',
        prediction_label_column="",  # 'prediction.classes',
        dataflow_service_account=service_account,
        encryption_spec_key_name=cmek_key,
        project=project,
        # bigquery_destination_output_uri = f"bq://{bq_loc}_eval",
        # force_runner_mode = '',
        # ground_truth_format='bigquery',
        # ground_truth_bigquery_source = f"bq://{active_bq_loc}_kfp", # q.ouputs['gcp_resources'],
        # classification_type = 'multiclass',
        # class_labels=['0', '1'],
        # dataflow_subnetwork: str = '',
        # dataflow_use_public_ips = False,
        # slicing_specs: list[Any] = [],
        # positive_classes = ["1"],
        # dataflow_disk_size_gb = 50,
        # dataflow_machine_type: str = 'n1-standard-4',
        # dataflow_workers_num = 1,
        # dataflow_max_workers_num = 5,
        # predictions_gcs_source: dsl.Input[system.Artifact] = None,
        # ground_truth_gcs_source: list[str] = [],
    )


def vertex_endpoint_component(
    pipeline_root: str,
    constants: dict,
    machine_type: dict,
    model_id: Union[str, int],
    min_replica: Optional[int] = 1,
    max_replica: Optional[int] = 4,
) -> List[dsl.component]:
    """
    A component to create an endpoint and deploy a model to a PERSISTENT
    compute resource for online predictions

    inputs:
        pipeline_root: str - GCS path from pipeline_fn
        constants: dict - Dict created in notebook 2 to pass useful information
        machine_type: dict - Dict with compatible GCP machine to use as an endpoint
        model_id: Union[str, int] - The integer ID of the Vertex Model Registry entry
        min_replica: Optional[int] - Starting, default number of machine_type
            machines (replicas)
        max_replica: Optional[int] - Maximum autoscaling number of machine_type
            machines (replicas)
    """
    project, service_account, cmek_key = required_kf_info(constants)

    endpoint_create = endpoint.EndpointCreateOp(
        project=project,
        display_name="endpoint_create",
        location=constants["LOCATION"],
        labels=constants["LABELS"],
        encryption_spec_key_name=cmek_key,
    )

    endpoint_deploy = endpoint.ModelDeployOp(
        model=model_id,
        endpoint=endpoint_create.outputs["endpoint"],
        service_account=service_account,
        deployed_model_display_name=constants["MODEL_NAME"] + "-endpoint",
        dedicated_resources_machine_type=machine_type["machineType"],
        dedicated_resources_accelerator_type=machine_type.get("acceleratorType", ""),
        dedicated_resources_accelerator_count=machine_type.get("acceleratorCount", 0),
        dedicated_resources_min_replica_count=max(1, min_replica),
        dedicated_resources_max_replica_count=max(1, max_replica),
        # enable_request_reponse_logging = False,
        # request_response_logging_bq_destination_table = None,
        disable_container_logging=False,
        enable_access_logging=False,
    )
    endpoint_deploy.after(endpoint_create)

    return [endpoint_create, endpoint_deploy]


def vertex_undeploy_endpoint_component(
    deployment_components: Tuple[Any, artifact_types.VertexEndpoint],
    model_id: Union[int, str],
) -> List[dsl.component]:
    """A component that can ONLY be used in COMPUTE_PROJECTS to delete a
    PERSISTENT online endpoint

    inputs:
        deployment_components: List[Any, artifact_types.VertexEndpoint] - Contains (as the second element) an endpoint
            Vertex artifact
        model_id: Union[int, str] - The integer ID from Vertex Model Registry entry
    """

    endpoint_op, model_op = deployment_components

    undeploy = endpoint.ModelUndeployOp(
        model=model_id, endpoint=endpoint_op.outputs["endpoint"]
    )
    delete_endpoint = endpoint.EndpointDeleteOp(
        endpoint=endpoint_op.outputs["endpoint"]
    )
    delete_endpoint.after(undeploy)

    return [undeploy, delete_endpoint]


def google_llm_inference_component(
    constants: dict,
    prompt_dataset: str,
    system_prompt: str,
    prompt_seq_len: Optional[int] = 512,
    target_seq_len: Optional[int] = 64,
    sampling_strategy: Optional[Union[list, str]] = ["greedy", "temperature_sampling"],
    language_model: Optional[Union[list, str]] = ["text-bison@001", "t5-small"],
) -> dsl.component:
    """EXPERIMENTAL

    A component to launch an LLM prediction request from a compatible LLM.
    See link below. Options have expanded since this function was written.

    inputs:
        constants: dict - Dict created in Notebook 2 to pass along important information
        prompt_dataset: str - GCS path to dataset with formatting restrictions as described
            in the hosted documentation
        system_prompt: str - A system prompt to be passed to the LLM
        prompt_seq_len: Optional[int] - The accepted prompt length
        target_seq_len: Optional[int] - The ideal response sequence length
        sampling_strategy: Optional[Union[list, str]] - Choose from existing strategies for Transformer
            Decoding
        llm: Optional[Union[list, str]] - Choose a compatible LLM as a string

    """

    project, _, cmek_key = required_kf_info(constants)

    # https://google-cloud-pipeline-components.readthedocs.io/en/google-cloud-pipeline-components-2.12.0/api/preview/llm.html#preview.llm.infer_pipeline.large_model_reference
    language_model = (
        language_model[0]
        if isinstance(language_model, (tuple, list))
        else language_model
    )

    sampling_strategy = (
        sampling_strategy[0]
        if isinstance(sampling_strategy, (list, tuple))
        else sampling_strategy
    )

    return llm.infer_pipeline(
        large_model_reference=language_model,
        prompt_dataset=prompt_dataset,
        prompt_sequence_length=prompt_seq_len,
        target_sequence_length=target_seq_len,
        sampling_strategy=sampling_strategy,
        instruction=system_prompt,
        accelerator_type="GPU",
        location="us-central-1",  # ONLY CENTRAL 1!!
        project=project,
        encryption_spec_key_name=cmek_key,
    )


def store_model_registry_info_component(
    data: Any,
    gcs_path: str,
) -> dsl.component:
    """A simple/useful component for artifacting the Vertex Model
    Registry resource ID which otherwise may be difficult to find
    later

    inputs:
        data: Any - Not really Any...see implementation in Model Registry
            Upload Component
        gcs_path: String GCS path where to send the file
    """

    # https://github.com/kubeflow/pipelines/issues/4378
    # https://raw.githubusercontent.com/kubeflow/pipelines/112de249a2c252f0a636bbfdf469d7ef2456f286/components/google-cloud/storage/upload_to_explicit_uri/component.yaml'

    return components.load_component_from_text(
        """
        name: Upload to GCS
        inputs:
        - {name: Data}
        - {name: GCS path, type: String}
        outputs:
        - {name: GCS path, type: String}
        implementation:
            container:
                image: google/cloud-sdk
                command:
                - sh
                - -ex
                - -c
                - |
                    if [ -n "${GOOGLE_APPLICATION_CREDENTIALS}" ]; then
                        gcloud auth activate-service-account --key-file="${GOOGLE_APPLICATION_CREDENTIALS}"
                    fi
                    echo "$0" > temp
                    gsutil cp -r temp "$1"
                    mkdir -p "$(dirname "$2")"
                    echo "$1" > "$2"
                - inputPath: Data
                - inputValue: GCS path
                - outputPath: GCS path
        """
    )(data=data, gcs_path=gcs_path)


def compute_project_handler(constants):
    """Reused utility to get the correct project"""

    default_project = os.getenv("CLOUD_ML_PROJECT_ID", constants["PROJECT"])
    project = constants["COMPUTE_PROJECT"] or default_project

    return project


def constant_bq_args(constants: dict) -> dict:
    """Formats the constants into kwargs for BQ components"""

    labels = constants.get(
        "LABELS",
        {
            "owner": f"{constants['OWNER']}",
            "costcenter": f"{constants['COSTCENTER']}",
            "tenant": f"{constants['TENANT']}",
        },
    )

    project = compute_project_handler(constants)

    return {
        "labels": labels,
        "project": project,
        # 'encryption_spec_key_name': constants['BQ_CMEK_KEY'], # encryption not currently enforced, but may be in the future
        "location": "US",
    }


def required_kf_info(constants: dict) -> List[str]:
    """A helper function to get the correct project / label / save location"""

    project = compute_project_handler(constants)
    service_account = (
        constants["SERVICE_ACCOUNT_COMPUTE_PROJECT"]
        if constants["SERVICE_ACCOUNT_COMPUTE_PROJECT"]
        else constants["SERVICE_ACCOUNT"]
    )
    cmek_key = (
        constants["CMEK_KEY_COMPUTE_PROJECT"]
        if constants["CMEK_KEY_COMPUTE_PROJECT"]
        else constants["CMEK_KEY"]
    )
    # ai_platform_loc = pipeline_root  # os.getenv('AIP_MODEL_DIR', pipeline_root)

    return project, service_account, cmek_key  # , ai_platform_loc


def format_machine_batch_predict(machine_type: dict) -> dict:
    """For some reason, Batch Predict component doesn't honor the typical KubeFlow pipeline syntax
    for machine_type. So this function modifies your inputs for compatibility"""

    accelerator_info = {}
    if machine_type.get("acceleratorType") or machine_type.get("accelerator_type"):
        accelerator_info["accelerator_type"] = machine_type.get(
            "acceleratorType", machine_type.get("accelerator_type")
        )
        accelerator_info["accelerator_count"] = machine_type.get(
            "acceleratorCount", machine_type.get("accelerator_count")
        )

    machine_type = {
        "machine_type": machine_type.get(
            "machineType", machine_type.get("machine_type", "g2-highmem-16")
        ),
        **accelerator_info,
    }
    return machine_type


def format_inputs_batch_predict(input_source: str) -> dict:
    """Takes the input source as a GCS path or BQ full path including
    table. Returns the function modifiers depending on the input type
    """

    source_kwargs = {"instances_format": "jsonl"}

    if isinstance(input_source, (list, tuple)):
        if input_source[0].lower().strip().startswith("gs://"):
            source_kwargs["gcs_source_uris"] = input_source
    elif input_source.lower().strip().startswith("gs://"):
        source_kwargs["gcs_source_uris"] = [input_source]
    else:
        source_kwargs["bigquery_source_input_uri"] = input_source
        source_kwargs["instances_format"] = "bigquery"

    return source_kwargs


def manipulate_args_batch_predict(
    machine_type: dict, input_source: str, manual_batch_size: int
) -> dict:
    """Composes several functions into the final kwargs for batch prediction.
    Functions used:
        format_machine_batch_predict
        format_inputs_batch_predict
    """

    machine_type = format_machine_batch_predict(machine_type)
    source_kwargs = format_inputs_batch_predict(input_source)
    if manual_batch_size:
        source_kwargs["manual_batch_tuning_parameters_batch_size"] = manual_batch_size

    final_kwargs = {**source_kwargs, **machine_type}
    return final_kwargs


def model_garden_upload_component(
    pipeline_root, constants, model_name, task, serving_env, docker_uri
):

    env = {
        "serving_env": str(serving_env),
        "DOCKER_URI": docker_uri,
        "constants": str(constants),
        "model_name": model_name,
        "task": task,
    }

    @dsl.component(
        packages_to_install=["google-cloud-aiplatform"],
    )
    def upload_from_vertex_garden() -> str:

        import os, datetime
        from google.cloud import aiplatform

        constants = eval(os.getenv("constants"))

        model = aiplatform.Model.upload(
            display_name=f"{os.getenv('model_name')}-{os.getenv('task')}",
            serving_container_image_uri=os.getenv("DOCKER_URI"),
            serving_container_ports=[7080],
            serving_container_predict_route="/predictions/transformers_serving",
            serving_container_health_route="/ping",
            serving_container_environment_variables=eval(os.getenv("serving_env")),
            project=os.getenv("PROJECT"),
            location=constants["LOCATION"],
            labels=constants["LABELS"],
            encryption_spec_key_name=os.getenv("CMEK_KEY"),
        )

        model_registry_id = model.resource_name.split("/")[-1]

        return str(model_registry_id)

    return dsl_component_to_vertex(
        pipeline_root,
        constants,
        upload_from_vertex_garden,
        env,
        machine_type={"machine_type": "e2-standard-4"},
        display_name="upload_from_vertex_garden",
    )


def dsl_component_to_vertex(
    pipeline_root,
    constants,
    component_func,
    env,
    machine_type,
    display_name=None,
    *args,
    **kwargs,
):

    project, service_account, cmek_key = required_kf_info(constants)

    return gcp_handling.create_custom_training_job_from_component(
        component_spec=component_func,
        display_name=display_name or component_func.__name__,
        replica_count=1,
        project=project,
        location=constants["LOCATION"],
        service_account=service_account,
        encryption_spec_key_name=cmek_key,
        base_output_directory=pipeline_root,
        labels=constants["LABELS"],
        env=generate_compute_environment(pipeline_root, constants, env),
        **machine_type,
    )()


def remove_duplicate_args(args: list) -> list:
    """
    Remove duplicate command-line arguments, keeping the last occurrence of each argument.

    Args:
        args (list): A list of command-line arguments.

    Returns:
        list: A list of command-line arguments with duplicates removed.
    """
    arg_dict = {}
    n = len(args)
    for i, v in enumerate(args):
        if v.startswith("--"):
            if i + 1 < n:
                arg_dict[v] = args[i + 1]
            else:
                arg_dict[v] = "--"
    unique_args = []
    for k, v in arg_dict.items():
        unique_args.append(k)
        if not v.startswith("--"):
            unique_args.append(v)
    return unique_args


def gcs_copy_file_component(
    pipeline_root: str,
    files: List[str],
    gcs_folder: str,
    constants: dict,
    machine_type: dict,
    display_name: str,
    job_config: dict,
    persistent_resource_id: Optional[str] = None,
):
    """
    Simplified GCS Copy Component with an inline implementation of the enhanced `upload_to_gcs`.

    Args:
        pipeline_root (str): Root path for the pipeline.
        files (List[str]): List of local files to copy to GCS.
        gcs_folder (str): Full GCS folder path (must end with a `/`).
        constants (dict): Constants dictionary.
        machine_type (dict): Machine type configuration.
        display_name (str): Display name for the component.
        job_config (dict): Configuration for GCS operations (e.g., project, service account).
        persistent_resource_id (Optional[str]): Reserved resource ID (optional).

    Returns:
        dsl.component: A custom job component to handle the GCS copy.
    """

    # Define the Python script to perform the GCS upload
    inline_python_script = f"""
from festa.gcs_operations import upload_to_gcs

# Variables
files = {files}  # List of files passed as input
gcs_folder = "{gcs_folder}"
job_config = {job_config}

# Perform the upload
upload_to_gcs(files, gcs_folder, job_config)
"""

    # Call the existing `customjob_component` to execute the script
    return customjob_component(
        pipeline_root=pipeline_root,
        constants=constants,
        machine_type=machine_type,
        file_to_run="-c",
        display_name=display_name,
        args=[inline_python_script],
        persistent_resource_id=persistent_resource_id,
    )
