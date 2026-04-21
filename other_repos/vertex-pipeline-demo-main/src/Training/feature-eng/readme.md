# Feature Engineering Component Documentation

## Summary
The Vertex AI feature engineering component embeds the feature engineering script directly in the pipeline using base64 encoding or GCS paths, creating a self-contained pipeline without external dependencies. The component is fully customizable - you can change the feature engineering script (feature-engineering.py), data sources, feature selection parameters, and encoding strategies on demand for each pipeline run.

## Component Description
The component is designed to be fully customizable. You can change the feature engineering script (feature-engineering.py) for each pipeline run by simply providing a different file (via GCS path or base64 encoded content). This allows you to experiment with different feature engineering approaches, encoding strategies, or feature selection methods without modifying the pipeline definition.

All feature engineering parameters are configurable through the script itself. You can adjust:
- SQL queries for data loading from BigQuery
- Feature type classification thresholds (binary, categorical, continuous)
- One-hot encoding parameters (minimum occurrence thresholds)
- Feature selection methods (RFECV parameters)
- Data preprocessing steps

Training arguments and data sources are also customizable. You can change BigQuery table names, target columns, output locations, and any other parameters your script accepts. This makes the component adaptable to different datasets and use cases.

## How Feature Engineering Component Works

### Two File Delivery Methods

**1. GCS Path Method (`customjob_component_with_gcs_download`)**
- The training script is stored in a GCS bucket
- At runtime, the component downloads the script using `gsutil cp`
- Suitable for frequently updated scripts or when you want to manage scripts separately
- Requires the script to be uploaded to GCS before pipeline execution

**2. Base64 Embedded Method (`customjob_component_with_embedded_file`)**
- The training script is base64 encoded and embedded directly in the pipeline
- The script is decoded at runtime and written to the container
- Creates a self-contained pipeline with no external file dependencies
- Better for version control and reproducibility

### Feature Engineering Pipeline Steps

1. **Data Loading**: Loads training and test datasets from BigQuery using SQL queries
   - Supports parameterized SQL queries with variable substitution
   - Uses BigQuery Storage API for efficient data transfer
   - Handles large datasets with progress tracking

2. **Data Preprocessing**:
   - Missing value imputation (0 for numeric, empty string for categorical)
   - Special handling for embedding columns (emb0-emb255)
   - Date column detection and handling

3. **Feature Type Classification**:
   - Automatically classifies features into types:
     - **Type 0**: Categorical (discrete values, typically strings or low cardinality)
     - **Type 1**: Continuous (numeric with many unique values)
     - **Type 2**: Binary (exactly 2 unique values or boolean-like)
     - **Type 3**: Date/DateTime columns
   - Configurable thresholds for binary and categorical detection
   - Manual overrides supported for specific features

4. **One-Hot Encoding**:
   - Encodes categorical features using scikit-learn's OneHotEncoder
   - Filters categories by minimum occurrence threshold (default: 2000)
   - Handles unknown categories gracefully
   - Fits encoder on training data only, applies to both train and test

5. **Feature Selection**:
   - Uses Recursive Feature Elimination with Cross-Validation (RFECV)
   - XGBoost classifier as the base estimator
   - Stratified K-Fold cross-validation
   - ROC-AUC as the scoring metric
   - Automatically determines optimal number of features

6. **Output Generation**:
   - Creates datasets with selected features only
   - Uploads results to BigQuery tables
   - Adds labels and expiration timestamps
   - Optionally saves selected feature list to GCS

### Environment Setup
The component automatically sets up the compute environment with:
- Required Python packages (pandas, numpy, xgboost, scikit-learn, etc.)
- Environment variables for GCP project configuration
- BigQuery client authentication
- Custom environment variables as specified

## 1. Parameters

**Pipeline Parameters:**
- `pipeline_root`: GCS path for storing pipeline outputs
- `project_id`: GCP project ID
- `region`: GCP region (e.g., us-east4)
- `cmek_key`: Customer-managed encryption key path
- `file_to_run` or `task_file_content`: Feature engineering script (GCS path or base64)

**Component Configuration:**
- `machine_type`: Compute resources (e.g., n1-standard-16)
- `packages`: Python dependencies to install
- `env`: Custom environment variables
- `display_name`: Display name for the Vertex AI job

**Feature Engineering Script Parameters (in feature-engineering.py):**
- `user_constants`: Dictionary with GCP project, database, and prefix information
- `sql`: SQL query for training data
- `sql2`: SQL query for test data
- Feature type classification thresholds
- One-hot encoding minimum occurrence threshold
- RFECV parameters (CV folds, scoring metric, step size)

## 2. How to Use

### Step 1: Prepare Your Feature Engineering Script

Modify `feature-engineering.py` with your feature engineering logic:
- Define SQL queries for data loading
- Configure feature type classification parameters
- Set one-hot encoding thresholds
- Configure RFECV parameters

### Step 2: Choose File Delivery Method

**Option A: GCS Path Method**
```python
feature_engineering_job = customjob_component_with_gcs_download(
    pipeline_root,
    constants,
    machine_type,
    'gs://your-bucket/path/to/feature-engineering.py',
    display_name="customjob-feature-eng",
    packages=packages_to_install,
    env=env,
)
```

**Option B: Base64 Embedded Method**
```python
# Read and encode the file
with open("feature-engineering.py", 'rb') as f:
    task_file_content = base64.b64encode(f.read()).decode('utf-8')

feature_engineering_job = customjob_component_with_embedded_file(
    pipeline_root,
    constants,
    machine_type,
    task_file_content,
    display_name="customjob-feature-eng",
    packages=packages_to_install,
    env=env,
)
```

### Step 3: Configure Pipeline Parameters

- Set up environment variables
- Choose machine type based on data size
- Specify required Python packages
- Configure GCP project and region settings

### Step 4: Run the Pipeline

- Compile the pipeline to JSON
- Initialize Vertex AI client
- Create and submit PipelineJob
- Monitor execution in Vertex AI Console

### Customization After Pipeline Runs

- Swap feature-engineering.py files for different preprocessing approaches
- Adjust SQL queries for different data sources
- Modify feature selection parameters based on results
- Change encoding strategies or thresholds
- Update machine types for different data sizes

## 3. How to Debug

### View Logs
You can check logs for the feature engineering job by clicking on 'View Logs' in the Vertex AI Console. The logs will show:
- Data loading progress from BigQuery
- Feature type classification results
- One-hot encoding progress
- Feature selection (RFECV) progress
- BigQuery upload status

### Common Issues and Solutions

**Issue: BigQuery Connection Errors**
- Verify GCP project and service account permissions
- Check that BigQuery Storage API is enabled
- Ensure SQL queries are valid and tables exist

**Issue: Memory Errors**
- Increase machine type (e.g., n1-standard-16 to n1-standard-32)
- Reduce data size in SQL queries (add LIMIT clause for testing)
- Process data in chunks

**Issue: Feature Selection Takes Too Long**
- Reduce number of CV folds in RFECV
- Increase step size in RFECV (remove more features per iteration)
- Use smaller sample of data for feature selection

**Issue: One-Hot Encoding Creates Too Many Features**
- Increase minimum occurrence threshold
- Reduce number of categories kept per feature
- Consider alternative encoding strategies (target encoding, etc.)

## Best Practices

- **Start Small**: Test with limited data (use LIMIT in SQL) before processing full datasets
- **Monitor Costs**: BigQuery queries and storage can be expensive for large datasets
- **Version Control**: Use base64 embedding for reproducibility, GCS paths for flexibility
- **Feature Selection**: Start with fewer CV folds and smaller step sizes, then scale up
- **Data Validation**: Always validate data shapes and feature counts after each step
- **Incremental Development**: Test data loading first, then preprocessing, then feature selection
- **Document Changes**: Keep track of SQL query changes and parameter modifications
- **Resource Planning**: Choose machine types based on data size (larger datasets need more memory)
- **Error Handling**: Add try-except blocks in your script for graceful failure handling
- **Output Validation**: Verify BigQuery table schemas and data quality after upload

## Advantages

**Full Customization**: Both the feature engineering script and all parameters can be changed on demand for each pipeline run. This flexibility allows you to experiment with different preprocessing approaches, feature sets, and encoding strategies.

**Self-Contained Pipelines**: Using base64 embedding creates pipelines with no external file dependencies, making them easier to version control and share.

**Scalable Data Processing**: Leverages BigQuery Storage API for efficient data loading, capable of handling large datasets.

**Automated Feature Engineering**: Automatically handles feature type classification, encoding, and selection, reducing manual work.

**Integration with Vertex AI**: Seamlessly integrates with other Vertex AI Pipeline components, allowing you to build end-to-end ML workflows.

**Reproducibility**: All feature engineering steps are logged and can be reproduced. Selected features are saved for reference.

**Flexible Data Sources**: Supports any BigQuery table structure through parameterized SQL queries.

**Managed Infrastructure**: No need to manage compute resources or data storage. Vertex AI handles infrastructure management.

## Disadvantages and Limitations

While the component offers many benefits, there are some limitations and considerations:

**BigQuery Query Costs**: Each pipeline run executes SQL queries against BigQuery, which incurs query costs. For large datasets or frequent runs, costs can accumulate.

**Data Reloading**: Data must be loaded from BigQuery for every pipeline run, even if the source data hasn't changed. This creates overhead in terms of:
- Network bandwidth consumption (BigQuery reads)
- Time spent on data loading (can be substantial for large datasets)
- BigQuery query costs (each run executes separate queries)

**Potential Solution**: For frequently used datasets, consider:
- Caching preprocessed data in GCS (Parquet format)
- Creating materialized views in BigQuery
- Using BigQuery scheduled queries to pre-aggregate data

**Memory Constraints**: Large datasets may require significant memory. Very large feature sets after one-hot encoding can cause memory issues.

**Feature Selection Time**: RFECV can be time-consuming for datasets with many features, especially with many CV folds. This increases compute costs.

**Limited Parallelization**: The feature engineering process runs sequentially. Data loading, preprocessing, encoding, and feature selection happen one after another.

**SQL Query Maintenance**: SQL queries need to be maintained and updated as source table schemas change. This requires coordination with data engineering teams.

**No Incremental Processing**: The component processes the entire dataset each time. There's no built-in support for incremental feature engineering on new data.

**Dependency on BigQuery**: The component is tightly coupled to BigQuery for data loading. If you need to use other data sources, you'll need to modify the script.

**Manual Feature Engineering Logic**: While the component automates common tasks, you still need to write custom feature engineering logic in the script for domain-specific features.

**Output Table Management**: Output tables are created/overwritten each run. You need to manage table naming and versioning manually if you want to keep historical versions.