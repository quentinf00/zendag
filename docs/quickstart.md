# ZenFlow Quickstart: Your First Pipeline

Welcome to ZenFlow! This guide will walk you through creating a simple, single-stage ML pipeline. We'll cover:

1.  Writing a Python function for a pipeline stage.
2.  Defining its configuration using Hydra-Zen.
3.  Using ZenFlow to generate a DVC pipeline.
4.  Running the pipeline with DVC.
5.  Seeing basic data versioning and MLflow logging in action.

ZenFlow aims to simplify MLOps by integrating [Hydra](httpsa://hydra.cc/) for configuration, [DVC](https://dvc.org/) for data/pipeline versioning, and [MLflow](https://mlflow.org/) for experiment tracking.

## Prerequisites

Before you start, make sure you have:
*   A Python environment with `zenflow`, `pandas`, `hydra-core`, `hydra-zen`, `dvc`, and `mlflow` installed. If you used the ZenFlow Cookiecutter template, `pixi install` should set this up.
*   An MLflow tracking server running (or be prepared for MLflow to use local file storage). `mlflow ui` in a separate terminal can start a local server.

## Step 1: Write Your Python Stage Function

With ZenFlow, you write Python functions as you normally would. The main constraint is:

> **All file paths your function reads from or writes to must be arguments to that function.**

Let's create a simple function that reads a CSV, scales a column, and writes a new CSV. We'll also use the `@mlflow_run` decorator from ZenFlow to automatically handle MLflow setup.

Create a file `src/my_project/stages/simple_transform.py` (assuming your project is `my_project`):

```python
# src/my_project/stages/simple_transform.py
import pandas as pd
from pathlib import Path
import logging
import mlflow # We can use mlflow directly for custom logging

# Make sure zenflow is importable
from zenflow.mlflow_utils import mlflow_run

log = logging.getLogger(__name__)

@mlflow_run # ZenFlow decorator for MLflow integration
def transform_data(input_csv_path: str, output_csv_path: str, scale_factor: float = 2.0):
    """
    Reads data from input_csv_path, multiplies 'value' column by scale_factor,
    and saves to output_csv_path.
    """
    log.info(f"Starting data transformation...")
    Path(input_csv_path).parent.mkdir(parents=True, exist_ok=True) # Ensure dir exists for dummy data creation

    df = pd.read_csv(input_csv_path)

    df['scaled_value'] = df['value'] * scale_factor

    output_dir = Path(output_csv_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Writing {len(df)} rows to: {output_csv_path}")
    df.to_csv(output_csv_path, index=False)

    # Custom MLflow logging (parameters from config are logged automatically by @mlflow_run)
    mlflow.log_param("stage_specific_scale_factor", scale_factor)
    mlflow.log_metric("num_rows_processed", len(df))
    mlflow.log_metric("sum_scaled_value", df['scaled_value'].sum())

    log.info("Data transformation complete.")
    return {"output_file": output_csv_path, "rows_processed": len(df)}
```

## Step 2: Define Function Call as Configuration (Hydra-Zen)

Next, we'll use [Hydra-Zen](https://mit-ll-responsible-ai.github.io/hydra-zen/) to define the *call* to our `transform_data` function as a configuration. This is where we link the function arguments (our file paths) to DVC's dependency and output tracking using ZenFlow utilities.

> **Crucial:** Path arguments in your Hydra-Zen config must use `zenflow.config_utils.deps_path("path/to/input")` for inputs and `zenflow.config_utils.outs_path("path/to/output")` for outputs.

Create `configs/transform_config.py`:

```python
# configs/transform_config.py
from hydra_zen import builds, store
from zenflow.config_utils import deps_path, outs_path

from my_project.stages.simple_transform import transform_data

# Define the configuration for calling transform_data
TransformConfig = builds(
    transform_data,  # The Python function this config represents
    populate_full_signature=True,  # Includes all args from transform_data

    # Map function arguments to DVC tracked paths:
    input_csv_path=deps_path("data/raw/input.csv"),  # DVC dependency
    output_csv_path=outs_path("data/processed/output.csv"),  # DVC output

    # Set other parameters for the function call
    scale_factor=1.5
)

# Register this configuration with Hydra-Zen's store
# 'group' is the DVC stage group, 'name' is a specific config instance
store(TransformConfig, group="transform", name="default_transform")
```

## Step 3: Select Configs & Configure Pipeline (`configure.py`)

Now, we create a `configure.py` script in our project root. This script will:
1.  Import our defined configurations (which registers them with Hydra-Zen's global store).
2.  Tell ZenFlow which stage groups and config instances to include in our DVC pipeline.
3.  Call `zenflow.core.configure_pipeline` to generate `dvc.yaml`.

Here's a minimal `configure.py`:

```python
# configure.py (in project root)
import hydra_zen
import os
import logging
from pathlib import Path
import pandas as pd # For creating dummy data

from zenflow.core import configure_pipeline

import configs.transform_config

store = hydra_zen.store

# List of DVC stage groups to include in the pipeline
STAGE_GROUPS = ["transform"] # Corresponds to the group name in store()

if __name__ == "__main__":
    # Configure the ZenFlow pipeline
    log.info(f"Configuring ZenFlow pipeline to generate {DVC_FILENAME}...")
    configure_pipeline(
        store=store,
        stage_groups=STAGE_GROUPS,
        dvc_filename=DVC_FILENAME,
        run_script="my_project.run_hydra_stage" # Assumed script for running stages
    )
    log.info(f"dvc.yaml generated successfully.")
```


## Step 4: Run the Pipeline with DVC

Now we execute the workflow:

1.  **Run the configuration script:**
    This generates `dvc.yaml` and composed configs in `artifacts/`.

    ```bash
    python configure.py
    ```

2.  **Inspect `dvc.yaml`:**
    Open the generated `dvc.yaml`. You should see something like:

    ```yaml
    stages:
      transform/default_transform:
        cmd: python -m my_project.run_hydra_stage -cd artifacts/transform -cn default_transform hydra.run.dir='artifacts/transform/default_transform'
        deps:
        - data/raw/input.csv 
        outs:
        - artifacts/transform/default_transform/data/processed/output.csv # Path relative to artifacts root
        params:
        - artifacts/transform/default_transform.yaml
    ```
    Notice how `deps` and `outs` match what we specified with `deps_path` and `outs_path`. The output path is automatically prefixed with the stage's artifact directory.

3.  **Run the DVC pipeline:**

    ```bash
    dvc exp run
    ```
    DVC will execute the `cmd` defined for the `transform/default_transform` stage. You'll see output from your Python script and MLflow.

4.  **Check Outputs & Logs:**
    *   **DVC Output:** Look for `artifacts/transform/default_transform/data/processed/output.csv`. A corresponding `.dvc` file for this output will also be in that directory.
    *   **MLflow:** If your MLflow server is running (or using local `mlruns`), you should find a new run with parameters like `scale_factor` and metrics like `num_rows_processed`.

## Data Versioning in Action

DVC tracks your data. Let's see this:

1.  **Modify Input Data:**
    Open `data/raw/input.csv` and change some values.

2.  **Check DVC Status:**

    ```bash
    dvc status
    ```
    DVC will report that `data/raw/input.csv` has changed.

3.  **Re-run the Pipeline:**

    ```bash
    dvc exp run
    # Or, more specifically for reproduction:
    # dvc repro transform/default_transform
    ```
    DVC detects the input change and re-executes the `transform/default_transform` stage.

4.  **Commit Data and Pipeline Changes:**
    DVC works with Git. To save this version of your data and pipeline:

    ```bash
    git add dvc.yaml dvc.lock 
    # You might also add the composed config: artifacts/transform/default_transform.yaml
    git commit -m "Ran transform v1, updated input data"
    # If you have a DVC remote configured:
    # dvc push
    ```

## Conclusion

You've successfully created and run your first ZenFlow pipeline!
*   You wrote a standard Python function.
*   Used Hydra-Zen and ZenFlow utilities (`deps_path`, `outs_path`) to define its configuration and link it to DVC.
*   ZenFlow's `configure_pipeline` automatically generated the `dvc.yaml`.
*   DVC executed the stage, and `@mlflow_run` handled MLflow logging.
*   DVC tracked changes to your input data, enabling reproducible runs.

In the next notebook, we'll explore how ZenFlow helps build more complex, multi-stage pipelines (DAGs) automatically.