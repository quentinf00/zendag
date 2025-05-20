3. Framework Project Documentation (zendag/README.md)

      
# ZenDag

**ZenDag** is a Python framework designed to streamline Machine Learning experimentation workflows by integrating:

*   **Configuration Management:** [Hydra](https://hydra.cc/) and [Hydra-Zen](https://mit-ll-responsible-ai.github.io/hydra-zen/) for modular, reusable, and composable configuration-as-code.
*   **Pipeline Orchestration & Versioning:** [DVC](https://dvc.org/) for defining experiment pipelines (DAGs) and versioning data, artifacts, and models.
*   **Experiment Tracking:** [MLflow](https://mlflow.org/) for logging parameters, metrics, artifacts, and comparing runs.

The core idea is to **drive the DVC pipeline definition directly from your Hydra configurations**, minimizing redundancy and ensuring consistency between your code, configuration, and the execution pipeline.

## Core Concepts

1.  **Configuration as Code:** Define all aspects of your experiment (data sources, preprocessing steps, model architecture, training parameters, evaluation metrics, logger settings) using Python code via Hydra-Zen and store them in a structured way (e.g., using `hydra_zen.ZenStore`).
2.  **Stage-Based Pipelines:** Structure your ML workflow into logical stages (e.g., `data_prep`, `feature_eng`, `train`, `evaluate`, `deploy`). Each stage corresponds to a node in the DVC pipeline graph.
3.  **Automatic DAG Generation:** ZenDag automatically generates the `dvc.yaml` file. It discovers dependencies (`deps`) and outputs (`outs`) by inspecting your Hydra configurations during a resolution step. You declare these using `${deps:...}` and `${outs:...}` interpolations directly within your configuration values (e.g., file paths).
4.  **Integrated Experiment Tracking:** A simple decorator (`@zendag.mlflow_run`) wraps your stage execution functions to automatically handle MLflow setup, log parameters from the Hydra config, capture artifacts (including logs and the config itself), and manage nested runs within a parent pipeline run.
5.  **Environment & Task Management:** While ZenDag itself is framework-agnostic regarding environment management, it's designed to work seamlessly with tools like [Pixi](https://pixi.sh/) or Conda/Poetry. A [Cookiecutter template](#cookiecutter-template) is provided to quickly set up a project using Pixi.

## Installation

```bash
pip install zendag # Or install from source/git if needed
```
    

## API Reference

**zendag.core.configure_pipeline(...)**

      
```python
def configure_pipeline(
    store: hydra_zen.ZenStore,
    stage_groups: List[str],
    stage_dir_fn: Callable[[str, str], str] = default_stage_dir_fn,
    configs_dir_fn: Callable[[str], str] = default_configs_dir_fn,
    dvc_filename: str = "dvc.yaml",
    run_script: str = "zendag.run",
    config_root: Optional[str] = None,
) -> None:
    # ... (Full signature in docstring above) ...
```
    


* Purpose: The main function to generate the dvc.yaml file.

* How it works:

    * Iterates through specified stage_groups in the hydra_zen.ZenStore.

    * For each configuration (name) within a stage group (stage):

        *Composes the full Hydra config (e.g., hydra.compose(overrides=[f"+{stage}={name}"])).

        *Writes the composed config to <configs_dir_fn(stage)>/<name>.yaml. This file is tracked as a param by DVC.

        *Registers temporary Hydra resolvers for ${deps:...} and ${outs:...}.

        *Calls OmegaConf.resolve(cfg). During resolution, any ${deps:path} or ${outs:path} encountered trigger the resolvers, which append the path to internal lists (side-effect).

        *Collects the unique dependencies and outputs discovered during resolution.

        *Defines a DVC stage entry in a dictionary (e.g., stages['stage/name'] = {...}). The cmd calls the specified run_script using the composed config. deps, outs, and params are populated.

    * Writes the complete stage dictionary to the dvc_filename.

* Logging: Provides INFO and DEBUG level logs about the process, including discovered deps/outs. Configure Python's logging to see these.


**zendag.config_utils.deps_path(...) & zendag.config_utils.outs_path(...)**

```python   
def deps_path(s: str, input_stage: Optional[str] = None, input_name: Optional[str] = None, stage_dir_fn=None) -> str:
    # ...

def outs_path(s: str) -> str:
    # ...
```
    


* Purpose: These functions format strings suitable for Hydra interpolation to declare DVC dependencies and outputs within your configuration values.

* Mechanism: They return strings like "${deps:path/to/dependency}" or "${outs:path/to/output}". When configure_pipeline calls OmegaConf.resolve, the registered resolvers detect these prefixes and capture the path (path/to/dependency or path/to/output) for the dvc.yaml generation. The resolver also returns the path part (k in the lambda lambda k: current_list.append(k) or k) so that the config value itself resolves to the intended path after interpolation (relative to the stage's output directory for outs).

* Usage: Use these inside your Hydra-Zen configurations where file paths are defined:

```python      
    from zendag.config_utils import deps_path, outs_path
    from hydra_zen import builds

    DataConfig = builds(
        MyDataset,
        data_file=deps_path("raw_data.csv", input_stage="data_fetch", input_name="fetch_europe"),
        processed_file=outs_path("processed_data.parquet"),
        # Need stage_dir_fn for deps_path resolution if using input_stage/name
        zen_meta=dict(stage_dir_fn=my_stage_dir_function) # Or rely on default/global
    )
```

        


**@zendag.mlflow_utils.mlflow_run(...)**

```python
@mlflow_run(project_name: str = os.environ.get("MLFLOW_PROJECT_NAME", "DefaultProject"))
def my_training_stage(cfg: DictConfig):
    # ... stage logic ...
```
    

* Purpose: Decorator for your main stage functions.

* Functionality:

    * Sets the MLflow experiment.

    * Handles parent/nested MLflow runs using .pipeline_id and DVC_STAGE env var.

    * If run via DVC (DVC_STAGE is set), loads the corresponding composed Hydra config (artifacts/<stage>/<name>.yaml).

    * Logs parameters from the resolved Hydra config to the nested MLflow run.

    * Logs the composed config .yaml file as an artifact.

    * Executes the decorated function.

    * Logs the run.log file from the Hydra output directory as an artifact on success or failure.

    * Manages exceptions and MLflow run states.

## Recommended Project Structure (See Cookiecutter Template)

```
my_project/
├── artifacts/             # DVC-managed outputs (configs, logs, models...)
│   ├── data_prep/
│   │   ├── config_a.yaml
│   │   └── config_a/      # Stage output dir
│   │       └── run.log
│   └── training/
│       ├── config_b.yaml
│       └── config_b/
│           ├── checkpoints/
│           ├── model.onnx
│           └── run.log
├── configs/               # Hydra-Zen config definitions (structured)
│   ├── __init__.py
│   ├── common.py
│   ├── data.py
│   ├── model.py
│   └── training.py
├── data/                  # Raw data (potentially DVC-managed)
├── src/                   # Project source code
│   └── my_project_pkg/
│       ├── __init__.py
│       ├── stages/        # Stage logic functions (decorated)
│       │   ├── __init__.py
│       │   ├── data_prep.py
│       │   └── train.py
│       └── utils.py       # Utility functions
├── tests/                 # Unit/integration tests
├── .dvc/                  # DVC internal files
├── .dvcignore
├── .gitignore
├── .pipeline_id           # Stores current parent MLflow run ID (auto-managed)
├── configure.py           # Script to run zendag.configure_pipeline
├── dvc.yaml               # Generated by configure.py (defines pipeline)
├── pixi.toml              # Environment and task definitions (Pixi)
└── README.md
```
    

* configs/: Organize your Hydra-Zen builds calls here, grouped by functionality (data, model, trainer, logger, etc.). Use hydra_zen.make_custom_builds_fn for brevity. Import these into configure.py.

* src/my_project_pkg/stages/: Implement the core logic for each pipeline stage here. Decorate the main function for each stage with @zendag.mlflow_run. These functions typically accept the Hydra DictConfig as an argument.

* configure.py: The script that:

    * Imports configs from configs/.

    * Populates a hydra_zen.ZenStore.

    * Defines the list of stage_groups to process.

    * Calls zendag.core.configure_pipeline(store, stage_groups, ...).

* pixi.toml: Defines the environment (dependencies like python, dvc, mlflow, hydra-core, hydra-zen, zendag, your src package) and tasks (configure, pipeline, save, etc.).

## How Automatic DAG Generation Works Internally

The key is the interaction between configure_pipeline, OmegaConf.resolve, and the custom deps/outs resolvers:

1. configure_pipeline registers temporary resolvers for deps and outs just before calling OmegaConf.resolve(cfg) for a specific stage config.

2. resolvers are simple lambdas, e.g., lambda k: my_list.append(k) or k.

3. OmegaConf.resolve encounters ${deps:some/path} within the config structure:

    * It calls the deps resolver with k = "some/path".

    * The resolver appends "some/path" to the current_deps list (side-effect).

    * The resolver returns k ("some/path").

    * OmegaConf uses this returned value to replace the ${deps:some/path} interpolation.

4. The same happens for ${outs:other/path}.

5. After OmegaConf.resolve(cfg) finishes, the current_deps and current_outs lists contain all paths discovered via these interpolations for that specific stage configuration.

6. These lists are then used to populate the deps and outs fields in the generated dvc.yaml.

This avoids manual duplication of paths between the config where they are used and the DVC pipeline definition.


## 4. [Cookiecutter Template Documentation (`README.md` for template users)](./cookiecutter-zendag-template/README.md)

## License
Apache 2.0