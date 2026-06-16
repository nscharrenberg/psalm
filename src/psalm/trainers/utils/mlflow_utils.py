import shutil
import tempfile
import time
from typing import Any, Optional

import mlflow
from mlflow import MlflowClient, ActiveRun
from mlflow.entities import Metric, RunStatus

from psalm.configs.utils.mlflow_config import MLFlowConfig


def mlflow_run_start(mlflow_config: MLFlowConfig) -> Optional[ActiveRun]:
    """
    Starts and initializes an MLflow run with the provided configuration.

    This function sets the MLflow tracking URI and experiment name using the
    provided configuration and starts a new MLflow run with a specified run
    name and logging system metrics option. It returns the active MLflow run
    to allow logging of artifacts, metrics, and parameters.

    Args:
        mlflow_config: Configuration settings for the MLflow session which includes
            tracking URI, experiment name, run name, and a flag to log system metrics.

    Returns:
        ActiveRun: The newly started MLflow run instance.
    """
    mlflow.set_tracking_uri(mlflow_config.tracking_url)
    mlflow.set_experiment(mlflow_config.experiment_name)

    run = mlflow.start_run(run_name=mlflow_config.run_name, log_system_metrics=mlflow_config.log_system_metrics)

    return run

def mlflow_get_run() -> ActiveRun:
    """
    Retrieves the current active MLflow run.

    Raises an error if no MLflow run is currently active. This function is used
    to ensure that there is an ongoing MLflow run to log parameters, metrics,
    or artifacts. If no active run exists, the calling function must have
    previously triggered the start of an MLflow run.

    Returns:
        ActiveRun: The current active MLflow run.

    Raises:
        RuntimeError: If no MLflow run is currently active.
    """
    run: Optional[ActiveRun] = mlflow.active_run()

    if not run:
        raise RuntimeError("MLFlow run not started. Call `mlflow_run_start` first.")

    return run

def mlflow_get_run_id() -> str:
    """
    Fetches the run ID of the current active MLflow run.

    This function retrieves the run ID of the currently active MLflow
    run by accessing the run information through the `mlflow_get_run`
    function. The run ID uniquely identifies the run in MLflow tracking.

    Returns:
        str: The run ID of the current active MLflow run.
    """
    return mlflow_get_run().info.run_id

def mlflow_log_params(params: dict[str, Any]) -> None:
    """
    Logs a dictionary of parameters into the current MLflow run.

    This function takes a dictionary of parameters and logs each key-value pair to the
    current MLflow experiment run. If the value cannot be logged directly, it will be
    converted to a string before logging to ensure compatibility with MLflow.

    Args:
        params (dict[str, Any]): A dictionary where keys are parameter names and values
            are the corresponding parameter values to log.

    """
    run_id = mlflow_get_run_id()
    client = MlflowClient()

    for k, v in params.items():
        try:
            client.log_param(run_id, k, v)
        except Exception:
            client.log_param(run_id, k, str(v))

def mlflow_log_metrics(metrics: dict[str, float], step: Optional[int] = None) -> None:
    """
    Logs a batch of metrics to an MLflow tracking server.

    This function takes a dictionary of metric names and values, along with an
    optional step parameter, and logs them to the current MLflow run. Each metric
    is recorded with a timestamp representing the current time of logging. If any
    metric cannot be converted to a valid float value, it is skipped. The function
    makes use of the MLflow client's feature for batch logging, ensuring that all
    valid metrics are sent efficiently as a group.

    Args:
        metrics (dict[str, float]): A dictionary where keys are metric names and
            values are their corresponding numerical values.
        step (Optional[int]): The step at which the metrics are logged. If not
            provided, defaults to 0.

    Returns:
        None
    """
    run_id = mlflow_get_run_id()
    client = MlflowClient()

    ts = int(time.time() * 1000)

    metric_list = []

    for k, v in metrics.items():
        try:
            metric_list.append(
                Metric(key=k, value=float(v), timestamp=ts, step=step or 0)
            )
        except Exception:
            pass

    if metric_list:
        client.log_batch(run_id=run_id, metrics=metric_list)

def mlflow_log_artifact_dir(local_dir: str, artifact_dir: str) -> None:
    """
    Logs all artifacts in a directory to the artifact repository associated with an MLflow run.

    This function utilizes the MlflowClient to log files from a specified local
    directory into the MLflow artifact repository under a specified artifact path.
    The current active MLflow run is determined, and artifacts are logged
    accordingly.

    Args:
        local_dir: The path to the directory containing local files to be logged as
            artifacts.
        artifact_dir: The destination directory in the MLflow artifact repository
            where files from the local directory will be stored.

    Returns:
        None
    """
    run_id = mlflow_get_run_id()
    client = MlflowClient()

    client.log_artifacts(
        run_id=run_id,
        local_dir=local_dir,
        artifact_path=artifact_dir)

def mlflow_transformer_log_model(model, tokenizer, artifact_path: str) -> None:
    """
    Logs a pre-trained transformer model and its tokenizer to MLflow.

    This function saves the provided transformer model and tokenizer to a temporary
    directory, then logs them as artifacts to MLflow under the specified artifact path.

    Args:
        model: The pre-trained transformer model to be logged.
        tokenizer: The tokenizer associated with the transformer model.
        artifact_path: The path within the MLflow artifact store where the
            model and tokenizer will be logged.

    Returns:
        None
    """
    # Check if there is an active run.
    mlflow_get_run_id()

    temp_dir = tempfile.mkdtemp(prefix="mlflow_transformers_")

    try:
        model.save_pretrained(temp_dir)
        tokenizer.save_pretrained(temp_dir)

        mlflow_log_artifact_dir(temp_dir, artifact_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def mlflow_run_end(status: str = RunStatus.to_string(RunStatus.FINISHED)) -> None:
    """
    Ends the current MLflow run with the specified status.

    This function checks if there is an active MLflow run and attempts
    to end it with the provided status. If an error occurs while ending
    the run, it will be silently ignored.

    Args:
        status (str): The status to set for the MLflow run when it is ended. Defaults to "FINISHED".
    """
    # Check if there is an active run.
    mlflow_get_run_id()

    try:
        mlflow.end_run(status=status)
    except Exception:
        pass
