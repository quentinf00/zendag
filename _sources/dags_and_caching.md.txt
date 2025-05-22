# Automatic DAGs & DVC Caching with ZenDag

In the [Quickstart Notebook](quickstart.md), we saw how to create a single-stage pipeline. ZenDag truly shines when building multi-stage pipelines, as its `deps_path` and `outs_path` utilities automatically define the Directed Acyclic Graph (DAG) for DVC. We'll also see DVC's powerful caching mechanism in action.

## Building a Multi-Stage Pipeline

Let's create a three-stage pipeline:
1.  **`generate_data`**: Creates some raw data.
2.  **`process_data`**: Takes raw data, processes it.
3.  **`summarize_data`**: Takes processed data, creates a summary.

### Stage 1: Generate Data

```python
# src/my_project/stages/generate_data_stage.py
import pandas as pd
from pathlib import Path
import logging
import mlflow
from zendag.mlflow_utils import mlflow_run

log = logging.getLogger(__name__)

@mlflow_run
def generate_data(output_csv_path: str, num_rows: int = 100, base_value: int = 5):
    log.info(f"Generating {num_rows} rows of data to {output_csv_path}")
    df = pd.DataFrame({
        'id': range(num_rows),
        'value': [(i % 10) * base_value for i in range(num_rows)]
    })
    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    mlflow.log_param("num_rows_generated", num_rows)
    mlflow.log_param("base_value", base_value)
    log.info("Data generation complete.")
    return {"generated_file": output_csv_path}
```

Config (`configs/generate_data_config.py`):
```python
# configs/generate_data_config.py
from hydra_zen import builds, store
from zendag.config_utils import outs_path
from my_project.stages.generate_data_stage import generate_data

GenerateDataConfig = builds(
    generate_data,
    output_csv_path=outs_path("generated_data.csv"), # This is an output of this stage
    num_rows=50
)
store(GenerateDataConfig, group="generate_data", name="default_gen")
```

### Stage 2: Process Data

This stage will take the output of `generate_data` as its input.

```python
# src/my_project/stages/process_data_stage.py
import pandas as pd
from pathlib import Path
import logging
import mlflow
from zendag.mlflow_utils import mlflow_run

log = logging.getLogger(__name__)

@mlflow_run
def process_data(input_csv_path: str, processed_output_csv_path: str, scale_factor: float = 0.5):
    log.info(f"Processing data from {input_csv_path}")
    # Ensure dummy input exists if generate_data wasn't run or its output isn't available
    if not Path(input_csv_path).exists():
        log.warning(f"Input {input_csv_path} not found for process_data. Creating dummy for example.")
        pd.DataFrame({'id': range(10), 'value': range(0,100,10)}).to_csv(input_csv_path, index=False)

    df = pd.read_csv(input_csv_path)
    df['processed_value'] = df['value'] * scale_factor
    Path(processed_output_csv_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(processed_output_csv_path, index=False)
    mlflow.log_param("processing_scale_factor", scale_factor)
    mlflow.log_metric("processed_rows", len(df))
    log.info(f"Processed data saved to {processed_output_csv_path}")
    return {"processed_file": processed_output_csv_path}
```

Config (`configs/process_data_config.py`):
```python
# configs/process_data_config.py
from hydra_zen import builds, store
from zendag.config_utils import deps_path, outs_path
from my_project.stages.process_data_stage import process_data

ProcessDataConfig = builds(
    process_data,
    populate_full_signature=True,
    # Crucial: input_csv_path depends on the output of the 'generate_data/default_gen' stage
    input_csv_path=deps_path( "generated_data.csv", "generate_data","default_gen",),
    processed_output_csv_path=outs_path("main_processed_data.csv"),
    scale_factor=3.0
)
store(ProcessDataConfig, group="process_data", name="default_proc")
```
**Note the `deps_path`:**
*   `deps_path("generated_data.csv", gererate_data", "default_gen")` tells ZenDag/DVC that this input comes from the `output_csv_path` (which was `generated_data.csv`) of the stage instance named `default_gen` in the `generate_data` group.
*   The `stage_dir` interpolation provides the base output directory of the dependency stage.

### Stage 3: Summarize Data

```python
# src/my_project/stages/summarize_data_stage.py
import pandas as pd
from pathlib import Path
import logging
import mlflow
from zendag.mlflow_utils import mlflow_run

log = logging.getLogger(__name__)

@mlflow_run
def summarize_data(processed_input_csv_path: str, summary_output_txt_path: str):
    log.info(f"Summarizing data from {processed_input_csv_path}")
    # Ensure dummy input exists if process_data wasn't run or its output isn't available
    if not Path(processed_input_csv_path).exists():
        log.warning(f"Input {processed_input_csv_path} not found for summarize_data. Creating dummy for example.")
        pd.DataFrame({'id': range(5), 'processed_value': range(0,50,10)}).to_csv(processed_input_csv_path, index=False)

    df = pd.read_csv(processed_input_csv_path)
    mean_val = df['processed_value'].mean()
    max_val = df['processed_value'].max()
    summary_content = f"Data Summary:\nMean Processed Value: {mean_val}\nMax Processed Value: {max_val}\nRows: {len(df)}"
    Path(summary_output_txt_path).parent.mkdir(parents=True, exist_ok=True)
    with open(summary_output_txt_path, 'w') as f:
        f.write(summary_content)
    mlflow.log_metric("mean_processed", mean_val)
    mlflow.log_metric("max_processed", max_val)
    log.info(f"Summary saved to {summary_output_txt_path}")
    return {"summary_file": summary_output_txt_path}
```
Config (`configs/summarize_data_config.py`):
```python
# configs/summarize_data_config.py
from hydra_zen import builds, store
from zendag.config_utils import deps_path, outs_path
from my_project.stages.summarize_data_stage import summarize_data

SummarizeDataConfig = builds(
    summarize_data,
    populate_full_signature=True,
    processed_input_csv_path=deps_path( "main_processed_data.csv", "process_data","default_proc",),
    summary_output_txt_path=outs_path("summary_report.txt")
)
store(SummarizeDataConfig, group="summarize_data", name="default_summary")
```

## Updated `configure.py`

Modify your `configure.py` to include these new stage groups and their config imports:

```python
# configure.py (modified)
import hydra_zen
import os
import logging
from pathlib import Path
from zendag.core import configure_pipeline

# Import your config modules
import configs.generate_data_config
import configs.process_data_config
import configs.summarize_data_config


store = hydra_zen.store
STAGE_GROUPS = [
    "generate_data",
    "process_data",
    "summarize_data"
]

if __name__ == "__main__":
    # Configure the ZenDag pipeline
    logging.info(f"Configuring ZenDag pipeline to generate {DVC_FILENAME}...")
    configure_pipeline(
        store=store, stage_groups=STAGE_GROUPS,
    )
    logging.info(f"{DVC_FILENAME} generated for multi-stage pipeline.")

```

## Running `configure` and Inspecting the DAG

1.  Run `python configure.py` (or `pixi run configure`).
2.  Open `dvc.yaml`. You'll see all three stages. Notice how the `deps` of `process_data/default_proc` correctly points to the output path of `generate_data/default_gen`, and similarly for `summarize_data`. ZenDag resolved these paths.
3.  Visualize the DAG:

    ```bash
    dvc dag
    ```
    You should see a graph like:
    `generate_data/default_gen -> process_data/default_proc -> summarize_data/default_summary`

## Running the Pipeline & DVC Caching

1.  **First Run:**
    ```bash
    dvc exp run
    ```
    All three stages will execute. Outputs will be generated in their respective `artifacts` subdirectories.

2.  **Second Run (Caching):**
    Run it again immediately:
    ```bash
    dvc exp run
    ```
    DVC will report that all stages are "cached" or "up-to-date" and won't re-execute the Python code. This is because no inputs or parameters have changed.

3.  **Modifying a Parameter & Selective Re-run:**
    *   Open `configs/process_data_config.py` and change `scale_factor` in `ProcessDataConfig` (e.g., to `4.0`).
    *   Run `python configure.py` again. This updates `artifacts/process_data/default_proc.yaml`.
    *   Now, run the pipeline:
        ```bash
        dvc exp run
        ```
        Observe the output:
        *   `generate_data/default_gen` will likely be "Pipeline-cached".
        *   `process_data/default_proc` will re-run because its parameter file (`default_proc.yaml`) changed.
        *   `summarize_data/default_summary` will also re-run because its input (the output of `process_data`) changed.

## Conclusion

ZenDag's use of `deps_path` and `outs_path` allows DVC to automatically understand the relationships between your pipeline stages, forming a DAG. DVC's caching mechanism then ensures that only necessary parts of your pipeline are re-executed when inputs or parameters change, saving significant time and computational resources. The `${stage_dir:...}` interpolation is key for linking outputs of one stage to inputs of another in a clean way.