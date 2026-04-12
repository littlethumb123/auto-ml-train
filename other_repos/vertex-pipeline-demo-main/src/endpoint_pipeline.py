"""
Pipeline definition for Vertex AI model deployment.

This module contains the main pipeline definition and compilation logic.
"""

from kfp import dsl, compiler
from typing import Optional
import logging

try:
    from .components import (
        deploy_model_endpoint,
        validate_model_artifact,
        cleanup_old_model_versions,
    )
except ImportError:
    from components import (
        deploy_model_endpoint,
        validate_model_artifact,
        cleanup_old_model_versions,
    )


@dsl.pipeline(
    name="model-deployment-pipeline",
    description="Pipeline for deploying ML models to Vertex AI endpoints",
)
def model_deployment_pipeline(
    project_id: str,
    location: str,
    model_display_name: str,
    model_description: str,
    model_artifact_uri: str,
    serving_image_uri: str,
    encryption_key: str,
    machine_type: str = "n1-standard-2",
    min_replica_count: int = 1,
    max_replica_count: int = 1,
    validate_artifacts: bool = True,
    cleanup_old_versions: bool = False,
    max_versions_to_keep: int = 3,
):
    """
    Model deployment pipeline.

    This pipeline:
    1. Optionally validates model artifacts exist in GCS
    2. Deploys the model to a Vertex AI endpoint
    3. Optionally cleans up old model versions

    Args:
        project_id: GCP project ID
        location: GCP location/region
        model_display_name: Display name for the model
        model_description: Description of the model
        model_artifact_uri: GCS path to model artifacts
        serving_image_uri: Container image URI for serving
        encryption_key: KMS encryption key
        machine_type: Machine type for deployment (default: n1-standard-2)
        min_replica_count: Minimum number of replicas (default: 1)
        max_replica_count: Maximum number of replicas (default: 1)
        validate_artifacts: Whether to validate artifacts before deployment (default: True)
        cleanup_old_versions: Whether to cleanup old model versions (default: False)
        max_versions_to_keep: Maximum number of model versions to keep (default: 3)
    """

    # Step 1: Validate model artifacts (optional)
    if validate_artifacts:
        validation_task = validate_model_artifact(
            project_id=project_id,
            location=location,
            artifact_uri=model_artifact_uri,
        )

        # Step 2: Deploy model (depends on validation)
        deploy_task = deploy_model_endpoint(
            project_id=project_id,
            location=location,
            model_display_name=model_display_name,
            model_description=model_description,
            encryption_key=encryption_key,
            artifact_uri=model_artifact_uri,
            serving_container_image_uri=serving_image_uri,
            machine_type=machine_type,
            min_replica_count=min_replica_count,
            max_replica_count=max_replica_count,
        ).after(validation_task)
    else:
        # Step 2: Deploy model (no validation dependency)
        deploy_task = deploy_model_endpoint(
            project_id=project_id,
            location=location,
            model_display_name=model_display_name,
            model_description=model_description,
            encryption_key=encryption_key,
            artifact_uri=model_artifact_uri,
            serving_container_image_uri=serving_image_uri,
            machine_type=machine_type,
            min_replica_count=min_replica_count,
            max_replica_count=max_replica_count,
        )

    # Step 3: Cleanup old model versions (optional, runs after deployment)
    if cleanup_old_versions:
        cleanup_old_model_versions(
            project_id=project_id,
            location=location,
            model_display_name=model_display_name,
            max_versions_to_keep=max_versions_to_keep,
        ).after(deploy_task)


class PipelineCompiler:
    """Class to handle pipeline compilation and management."""

    def __init__(self, pipeline_root: str):
        """
        Initialize the pipeline compiler.

        Args:
            pipeline_root: Root path for pipeline artifacts
        """
        self.pipeline_root = pipeline_root
        self.logger = logging.getLogger(__name__)

    def compile_pipeline(
        self,
        output_path: str = "model-deployment-pipeline.json",
        pipeline_name: Optional[str] = None,
    ) -> str:
        """
        Compile the pipeline to JSON.

        Args:
            output_path: Path where compiled pipeline JSON will be saved
            pipeline_name: Optional custom pipeline name

        Returns:
            Path to the compiled pipeline JSON file
        """
        self.logger.info(f"Compiling pipeline to: {output_path}")

        # Create a pipeline function with the specified pipeline root
        @dsl.pipeline(
            name=pipeline_name or "model-deployment-pipeline",
            pipeline_root=self.pipeline_root + "model-deployment-pipeline",
            description="Pipeline for deploying ML models to Vertex AI endpoints",
        )
        def pipeline_with_root(
            project_id: str,
            location: str,
            model_display_name: str,
            model_description: str,
            model_artifact_uri: str,
            serving_image_uri: str,
            encryption_key: str,
            machine_type: str = "n1-standard-2",
            min_replica_count: int = 1,
            max_replica_count: int = 1,
            validate_artifacts: bool = True,
            cleanup_old_versions: bool = True,
            max_versions_to_keep: int = 5,
        ):
            model_deployment_pipeline(
                project_id=project_id,
                location=location,
                model_display_name=model_display_name,
                model_description=model_description,
                model_artifact_uri=model_artifact_uri,
                serving_image_uri=serving_image_uri,
                encryption_key=encryption_key,
                machine_type=machine_type,
                min_replica_count=min_replica_count,
                max_replica_count=max_replica_count,
                validate_artifacts=validate_artifacts,
                cleanup_old_versions=cleanup_old_versions,
                max_versions_to_keep=max_versions_to_keep,
            )

        # Compile the pipeline
        compiler.Compiler().compile(
            pipeline_func=pipeline_with_root, # type: ignore
            package_path=output_path,
        )

        self.logger.info(f"Pipeline compiled successfully to: {output_path}")
        return output_path

    def create_simple_pipeline(
        self, output_path: str = "simple-deployment-pipeline.json"
    ) -> str:
        """
        Create a simplified version of the pipeline without optional components.

        Args:
            output_path: Path where compiled pipeline JSON will be saved

        Returns:
            Path to the compiled pipeline JSON file
        """

        @dsl.pipeline(
            name="simple-model-deployment-pipeline",
            pipeline_root=self.pipeline_root + "simple-model-deployment-pipeline",
            description="Simplified pipeline for deploying ML models to Vertex AI endpoints",
        )
        def simple_pipeline(
            project_id: str,
            location: str,
            model_display_name: str,
            model_description: str,
            model_artifact_uri: str,
            serving_image_uri: str,
            encryption_key: str,
            machine_type: str = "n1-standard-2",
            min_replica_count: int = 1,
            max_replica_count: int = 1,
        ):
            # Only deploy the model - no validation or cleanup
            deploy_model_endpoint(
                project_id=project_id,
                location=location,
                model_display_name=model_display_name,
                model_description=model_description,
                encryption_key=encryption_key,
                artifact_uri=model_artifact_uri,
                serving_container_image_uri=serving_image_uri,
                machine_type=machine_type,
                min_replica_count=min_replica_count,
                max_replica_count=max_replica_count,
            )

        # Compile the simple pipeline
        compiler.Compiler().compile(
            pipeline_func=simple_pipeline, # type: ignore
            package_path=output_path,
        )

        self.logger.info(f"Simple pipeline compiled successfully to: {output_path}")
        return output_path
