import logging
import os
from functools import wraps
from pathlib import Path

import hydra  # To access Hydra's runtime config
import mlflow
import pandas as pd
from omegaconf import OmegaConf
from .core import default_configs_dir_fn, default_stage_dir_fn


_log = logging.getLogger(__name__)

ARTIFACTS_ROOT = os.getenv("ARTIFACTS_DIR", "artifacts")  # Default to "artifacts"


def mlflow_run(
    project_name=os.environ.get("MLFLOW_PROJECT_NAME", "DefaultProject"),
    stage_dir_fn=default_stage_dir_fn,
    configs_dir_fn=default_configs_dir_fn,
):
    """
    Decorator to wrap a function execution within nested MLflow runs.

    - Establishes a parent run using MLFLOW_RUN_ID (if set via .pipeline_id).
    - Creates a nested child run named after the DVC stage or function name.
    - Logs Hydra configuration parameters from the corresponding composed config file.
    - Logs the composed config file itself as an artifact.
    - Logs the Hydra run log file (run.log) as an artifact upon completion or failure.
    - Handles exceptions and ensures logs are captured if possible.
    """

    def decorator(wrapped_function):
        @wraps(wrapped_function)
        def wrapper(*args, **kwargs):
            parent_run_id = None
            pipeline_id_file = Path(".pipeline_id")
            if pipeline_id_file.exists():
                parent_run_id = pipeline_id_file.read_text().strip()
                os.environ["MLFLOW_RUN_ID"] = parent_run_id
                _log.info(f"Found parent run ID in .pipeline_id: {parent_run_id}")
            current_mlflow_project_name = project_name
            if not current_mlflow_project_name:
                _log.warning("MLFLOW_PROJECT_NAME not set. Using 'DefaultProject'.")
                current_mlflow_project_name = "DefaultZenDagProject"
            # TODO check if pipeline id exists in project
            mlflow.set_experiment(current_mlflow_project_name)
            _log.info(f"Using MLflow experiment: '{current_mlflow_project_name}'")

            # DVC sets this environment variable during `dvc repro` or `dvc exp run`
            dvc_stage_name = os.environ.get("DVC_STAGE")  # e.g., "training/train-interburst"
            run_name = dvc_stage_name or wrapped_function.__name__

            try:
                # Start the parent run context (or reuse if ID exists)
                with mlflow.start_run(run_id=parent_run_id) as parent_run:
                    _log.info(f"Active MLflow parent run ID: {parent_run.info.run_id}")
                    # Store the potentially *new* parent run ID if one wasn't provided
                    if not parent_run_id:
                        pipeline_id_file.write_text(parent_run.info.run_id + "\n")
                        _log.info(f"Wrote new parent run ID to .pipeline_id: {parent_run.info.run_id}")

                    # Start the nested child run for the specific stage/function
                    with mlflow.start_run(run_name=run_name, nested=True) as child_run:
                        _log.info(f"Started nested MLflow run '{run_name}' (ID: {child_run.info.run_id})")

                        # Log parameters and config artifact if running as a DVC stage
                        hydra_cfg = None
                        if dvc_stage_name:
                            try:
                                # Infer config path from dvc_stage_name and standard structure
                                stage, config_name = dvc_stage_name.split("/", 1)
                                # Use the same logic as configure_pipeline (needs access to configs_dir_fn)
                                # Simplification: Assume standard 'artifacts/' structure for now
                                # TODO: Make config path resolution more robust (maybe pass via env?)
                                config_path = Path(configs_dir_fn(stage)) / f"{config_name}.yaml"

                                if config_path.exists():
                                    _log.info(f"Logging config from: {config_path}")
                                    hydra_cfg = OmegaConf.load(config_path)
                                    # Flatten the dictionary for MLflow params
                                    params_flat = pd.json_normalize(
                                        OmegaConf.to_container(
                                            hydra_cfg, resolve=True
                                        ),  # Resolve interpolations before logging
                                        sep=".",
                                    ).to_dict(orient="records")[0]
                                    # Log parameters (MLflow truncates long values)
                                    for k, v in params_flat.items():
                                        mlflow.log_param(k, v)
                                    # Log the config file itself
                                    mlflow.log_artifact(config_path.as_posix())
                                else:
                                    _log.warning(f"Config file not found at expected path: {config_path}")
                            except Exception as e:
                                _log.error(
                                    f"Failed to load or log config for stage {dvc_stage_name}. Error: {e}",
                                    exc_info=True,
                                )
                        else:
                            # If not a DVC stage, try to get config from Hydra's context if available
                            # This requires the decorated function to be the Hydra entry point
                            try:
                                if hydra.core.hydra_config.HydraConfig.initialized():
                                    hydra_cfg = hydra.core.hydra_config.HydraConfig.get()
                                    # Log runtime config params maybe? Careful, can be large.
                                    # mlflow.log_params(OmegaConf.to_container(hydra_cfg.runtime, resolve=True))
                                    _log.info("Running outside DVC context, Hydra config might be available.")
                                else:
                                    _log.info("Running outside DVC and Hydra context.")
                            except Exception:  # Catch potential errors if Hydra not init
                                _log.info("Hydra context not available.")

                        # Execute the wrapped function
                        try:
                            # Pass the loaded config to the function if it expects it?
                            # Or rely on Hydra to inject it if the function is the @hydra.main entry point.
                            # For simplicity, let's assume the function uses Hydra context or loads config itself.
                            result = wrapped_function(*args, **kwargs)
                            _log.info(f"Function '{run_name}' executed successfully.")
                        except Exception as e:
                            _log.exception(f"Execution failed for '{run_name}'.")
                            # Log run.log artifact even on failure
                            log_path = Path(stage_dir_fn(stage, config_name)) / "run.log"
                            if log_path and log_path.exists():
                                _log.info(f"Logging run log on failure: {log_path}")
                                mlflow.log_artifact(log_path.as_posix())
                            raise e  # Re-raise the exception

                        # Log run.log artifact on success
                        log_path = Path(stage_dir_fn(stage, config_name)) / "run.log"
                        if log_path and log_path.exists():
                            _log.info(f"Logging run log on success: {log_path}")
                            mlflow.log_artifact(log_path.as_posix())

                        return result  # Return the function's result

            except Exception as e:
                # Catch errors starting MLflow runs etc.
                _log.exception(f"An error occurred in the mlflow_run wrapper for '{run_name}'.")
                raise e

        return wrapper

    return decorator
