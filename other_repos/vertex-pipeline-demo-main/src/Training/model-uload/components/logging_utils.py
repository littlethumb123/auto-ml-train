import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

def get_job_id_from_resource_name(resource_name: str) -> str:
    """Extracts the job ID from a Vertex AI resource name."""
    try:
        return resource_name.split('/')[-1]
    except Exception as e:
        logging.warning(f"Could not extract job ID from {resource_name}: {e}")
        return resource_name

def get_cloud_logs(
    project: str,
    job_id: str,
    start_time: str,
    # end_time: str,
    job_type: str = "hyperparameter_tuning_job",
    max_entries: int = 100
) -> List[Dict[str, Any]]:
    """Retrieves Cloud Logging entries for a specific job."""
    try:
        from google.cloud import logging as cloud_logging
        client = cloud_logging.Client(project=project)
        
        if job_type == "hyperparameter_tuning_job":
            filter_str = (
                f'resource.type="ml_job" AND resource.labels.job_id="{job_id}"'
            )
        else:
            filter_str = f'resource.labels.job_id="{job_id}"'
        filter_str += f' AND timestamp>="{start_time}"'
        # filter_str += f' AND timestamp<="{end_time}"'
        entries = client.list_entries(
            filter_=filter_str,
            order_by=cloud_logging.DESCENDING,
            max_results=max_entries
        )
        log_entries = []
        for entry in entries:
            log_data = {
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "severity": entry.severity,
                "message": str(entry.payload),
                "resource": dict(entry.resource) if entry.resource else {},
                "labels": dict(entry.labels) if entry.labels else {},
            }
            log_entries.append(log_data)
        return log_entries
    except Exception as e:
        logging.error(f"Error retrieving cloud logs: {e}")
        return []

def get_error_logs(
    project: str,
    job_id: str,
    start_time: str
    job_type: str = "hyperparameter_tuning_job",
) -> List[Dict[str, Any]]:
    """Returns only error-level logs for a job."""
    all_logs = get_cloud_logs(project, job_id, job_type, start_time)
    return [
        log for log in all_logs 
        if log.get("severity", "").upper() in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
    ]

def generate_cloud_logging_url(
    project: str,
    job_id: str,
    start_time: str,
    job_type: str = "hyperparameter_tuning_job"
) -> str:
    """Generates a Cloud Logging console URL for a specific job."""
    import urllib.parse
    base_url = "https://console.cloud.google.com/logs/query"
    if job_type == "hyperparameter_tuning_job":
        query = f'resource.type="ml_job" resource.labels.job_id="{job_id}"'
    else:
        query = f'resource.labels.job_id="{job_id}"'
    query += f' AND timestamp>="{start_time}"'
    encoded_query = urllib.parse.quote(query)
    return f"{base_url}?project={project}&query={encoded_query}"

def format_error_summary(
    job_id: str,
    job_type: str,
    error_logs: List[Dict[str, Any]],
    max_errors: int = 5
) -> str:
    """Formats error logs into a readable summary."""
    if not error_logs:
        return f"No errors found for {job_type} {job_id}"
    summary = f"Error Summary for {job_type} {job_id}:\n"
    summary += f"Total errors found: {len(error_logs)}\n\n"
    for i, error in enumerate(error_logs[:max_errors]):
        summary += f"Error {i+1}:\n"
        summary += f"  Time: {error.get('timestamp', 'Unknown')}\n"
        summary += f"  Severity: {error.get('severity', 'Unknown')}\n"
        summary += f"  Message: {error.get('message', 'No message')}\n"
        summary += f"  Resource: {error.get('resource', {}).get('type', 'Unknown')}\n\n"
    if len(error_logs) > max_errors:
        summary += f"... and {len(error_logs) - max_errors} more errors\n"
    return summary

