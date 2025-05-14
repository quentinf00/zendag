# configure.py (in the project root)
import hydra_zen
import os
import logging

# Import your new config definitions. This registers them with the hydra_zen.store.
from configs import process_data_config # Assuming __init__.py in configs imports this
# Or be explicit:
# import configs.process_data_config

from zenflow.core import configure_pipeline



# Access the global default store where configs from `process_data_config.py` were registered
store = hydra_zen.store

# Define all stage groups to be processed by ZenFlow
# The order can matter if there are implicit dependencies not captured by DVC
# (though DVC should handle explicit file dependencies correctly regardless of order here)
STAGE_GROUPS = [
    # Add other stage groups as your pipeline grows, e.g.:
    "example_stage",
    # "fetch_data",
    # "process_data",
    # "train_model",
    # "evaluate_model",
]

if __name__ == "__main__":
    from pathlib import Path
    import pandas as pd
    (Path("data") / "raw").mkdir(parents=True, exist_ok=True) # If raw inputs are in project's data/ dir
    # Create a dummy raw input file for the example if it doesn't exist
    dummy_raw_input_path = Path("data/raw/input_data.csv")
    if not dummy_raw_input_path.exists() and "example_stage" in STAGE_GROUPS: # Only if stage is active
        log = logging.getLogger(__name__) # Local logger for configure.py
        log.info(f"Dummy raw input {dummy_raw_input_path} not found. Creating for example.")
        pd.DataFrame({'id': range(1,6), 'value': [i*5 for i in range(1,6)]}).to_csv(dummy_raw_input_path, index=False)


    log = logging.getLogger(__name__) # Local logger for configure.py
    log.info(f"Starting ZenFlow pipeline configuration using ARTIFACTS_DIR='artifacts'...")

    configure_pipeline(
        store=store,
        stage_groups=STAGE_GROUPS,
    )

    log.info(f"Configuration finished. 'dvc.yaml' generated/updated.")
    log.info("You can now run the pipeline, e.g., using 'pixi run pipeline' or the CLI 'pixi run cli'.")