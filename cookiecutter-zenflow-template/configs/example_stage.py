# configs/process_data_config.py
from hydra_zen import builds, store

# Import the stage function
# This assumes your src/{{cookiecutter.project_slug}} is on PYTHONPATH
# which pixi.toml should handle via `{{cookiecutter.project_slug}} = { path = "./src/{{cookiecutter.project_slug}}", editable = true }`
from {{cookiecutter.project_slug}}.stages.example_stage import process_data_stage

# Import ZenFlow utils for declaring deps/outs
from zenflow.config_utils import deps_path, outs_path



# --- Main config for the process_data stage ---
# It will include the stage function itself and its specific sub-configs
ProcessDataConfig = builds(
    process_data_stage, # The function to be called for this stage
    input_file=deps_path("data/input_data.csv"), # DVC dependency
    output_file=outs_path("processed/processed_data.csv"), # DVC output
    processing_factor=2.0, # Default value
)

# --- Add to Hydra-Zen store ---
# This makes the config discoverable by `configure.py`
# The group name 'example_stage' will correspond to a top-level key in `dvc.yaml` stages
process_data_store = store(group="example_stage")
process_data_store(ProcessDataConfig, name="default") # A named config instance

# Example of a variation of the config
process_data_store(
    ProcessDataConfig,
    name="high_factor",
    params=builds(dict, processing_factor=10.0) # Override just the factor
)

# You can also add configs to the global store directly if preferred
# store(ProcessDataConfig, group="process_data", name="default")