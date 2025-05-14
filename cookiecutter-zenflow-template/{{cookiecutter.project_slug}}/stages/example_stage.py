import logging
import time
from pathlib import Path

import pandas as pd
from omegaconf import DictConfig
import mlflow # Direct MLflow usage within stage

# Assuming zenflow is importable (from pixi environment)
from zenflow.mlflow_utils import mlflow_run

# Configure a logger for this module
log = logging.getLogger(__name__)


@mlflow_run # ZenFlow decorator handles MLflow run setup, param logging from config, etc.
def process_data_stage(input_file, output_file, processing_factor):
    """
    Example data processing stage.

    Reads an input CSV, adds a new column based on a config parameter,
    and saves the processed data to an output CSV. It also logs a custom
    parameter and metric to MLflow.
    """
    log.info("Starting example data processing stage...")
    log.info(f"Full configuration for this stage:\n{cfg}")

    input_file_path = Path(input_file)
    output_file_path = Path(output_file)

    log.info(f"Input data file: {input_file_path}")
    log.info(f"Output data file: {output_file_path}")
    log.info(f"Processing factor from config: {processing_factor}")

    # --- Stage Logic ---
    if not input_file_path.exists():
        # For the example, let's create a dummy input if it doesn't exist
        log.warning(f"Input file {input_file_path} not found. Creating dummy data.")
        dummy_df = pd.DataFrame({
            'id': range(1, 11),
            'value': [i * 10 for i in range(1, 11)]
        })
        input_file_path.parent.mkdir(parents=True, exist_ok=True)
        dummy_df.to_csv(input_file_path, index=False)
        log.info(f"Created dummy input file at {input_file_path}")

    try:
        data_df = pd.read_csv(input_file_path)
        log.info(f"Successfully read {len(data_df)} rows from {input_file_path}")
    except Exception as e:
        log.error(f"Failed to read input file {input_file_path}: {e}", exc_info=True)
        raise

    # Simulate some processing
    start_time = time.time()
    data_df['processed_value'] = data_df['value'] * processing_factor
    time.sleep(0.5) # Simulate work
    end_time = time.time()
    processing_time = end_time - start_time

    log.info(f"Data processed. Added 'processed_value' column.")

    # Ensure output directory exists
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data_df.to_csv(output_file_path, index=False)
        log.info(f"Successfully saved processed data to {output_file_path}")
    except Exception as e:
        log.error(f"Failed to save output file {output_file_path}: {e}", exc_info=True)
        raise

    # --- MLflow Logging (custom for this stage) ---
    # The @mlflow_run decorator already logs parameters from the Hydra config.
    # Here we can log additional, stage-specific things.
    mlflow.log_metric("rows_processed", len(data_df))
    mlflow.log_metric("processing_time_seconds", processing_time)

    mlflow.log_text(
        f"Processed {len(data_df)} rows.\n"
        f"Processing factor used: {processing_factor}\n"
        f"Output file: {output_file_path.name}\n", "stage_summary.txt"
    )

    log.info("Example data processing stage completed successfully.")

    # Stages can optionally return values, but it's often cleaner
    # to rely on artifacts (files) for inter-stage communication via DVC.
    return {"output_path": str(output_file_path), "rows": len(data_df)}
