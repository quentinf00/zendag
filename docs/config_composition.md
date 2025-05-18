# Config Composition & Reusable Components with ZenFlow

Hydra is powerful for configuration management, especially its ability to compose configurations from smaller, reusable pieces. ZenFlow leverages this: you can define common components (like loggers, trainers, data modules) as separate configurations and then include them in your main stage configs. ZenFlow will still discover any `deps_path` or `outs_path` declarations within these composed parts.

## Example: A Reusable File Logger

Let's define a configuration for a simple file logger. This logger will write to a file, and we want DVC to track this log file as an output of any stage that uses this logger.

### Defining the Logger Configuration

Create `configs/loggers_config.py`:
```python
# configs/loggers_config.py
from hydra_zen import builds, store
from zenflow.config_utils import outs_path # Logger's output file is a DVC output
from pathlib import Path
import logging # Standard logging

# This is a simplified function. In reality, it would configure the logging system.
# For ZenFlow's dvc.yaml generation, we primarily care that it defines an output path.
# The actual logging setup happens when the stage runs and Hydra instantiates this.
def setup_stage_file_logger(log_file_path_str: str, log_level: str = "INFO"):
    """
    (Mock) Sets up a file logger for a stage.
    The actual configuration of the Python logging system would happen here
    when Hydra instantiates this part of the config during stage execution.
    """
    log_file_path = Path(log_file_path_str)
    log_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists

    # Simulate logger setup for demonstration
    print(f"[LoggerSetup] Configuring file logger at: {log_file_path} with level {log_level}")
    
    # In a real scenario, you might return a configured logger object or just perform side effects.
    # For ZenFlow's config resolution, the important part is that `log_file_path_str` uses `outs_path`.
    return {"log_file": str(log_file_path), "level": log_level}

# Hydra-Zen config for our file logger
FileLoggerConfig = builds(
    setup_stage_file_logger,
    populate_full_signature=True,
    # The log file path is an output of the stage using this logger.
    # It will be relative to the stage's output directory.
    log_file_path_str=outs_path("logs/stage_execution.log"),
    log_level="DEBUG" # Default log level for this config
)

# Register it in a 'logger' group
store(FileLoggerConfig, group="logger", name="default_file_logger")

# Another variant
VerboseFileLoggerConfig = builds(
    setup_stage_file_logger,
    populate_full_signature=True,
    log_file_path_str=outs_path("logs/verbose_stage_execution.log"),
    log_level="NOTSET" # Using NOTSET which is more verbose than DEBUG for standard logging
)
store(VerboseFileLoggerConfig, group="logger", name="verbose_file_logger")
```

### Using the Logger in a Stage

Let's modify the `TransformConfig` from our [Quickstart Notebook](quickstart.md) to include this logger using Hydra's `hydra_defaults`.

Modify `configs/transform_config.py`:
```python
# configs/transform_config.py (modified)
from hydra_zen import builds, store, MISSING # Import MISSING
from zenflow.config_utils import deps_path, outs_path
# Assume transform_data is in my_project.stages.simple_transform
from my_project.stages.simple_transform import transform_data # Or your actual import

# Option 1: Stage function is unaware of the logger (Hydra instantiates it)
TransformConfigWithLogger = builds(
    transform_data, # transform_data itself doesn't take a logger argument here
    populate_full_signature=True,
    input_csv_path=deps_path("data/raw/input.csv"),
    output_csv_path=outs_path("data/processed/output_with_logging.csv"),
    scale_factor=2.5,
    # --- Hydra Defaults for Composition ---
    hydra_defaults=[
        "_self_",  # Always include this first
        {"logger": "default_file_logger"} # Load the 'default_file_logger' from the 'logger' group
        # To use the other logger: {"logger": "verbose_file_logger"}
        # The key 'logger' here will create a 'logger' node in the final composed config.
    ]
)
# Ensure the original default_transform (from quickstart) is also available if needed for other examples
# or update it to also use a logger if that's the new baseline.
# For this example, we create a new named config.
store(TransformConfigWithLogger, group="transform", name="logged_transform")

# If you had an original default_transform:
# OriginalTransformConfig = builds(
#     transform_data,
#     populate_full_signature=True,
#     input_csv_path=deps_path("data/raw/input.csv"),
#     output_csv_path=outs_path("data/processed/output.csv"),
#     scale_factor=1.5
# )
# store(OriginalTransformConfig, group="transform", name="default_transform")

```
For simplicity, we'll focus on the case where the logger is instantiated by Hydra, and the stage function `transform_data` doesn't need a `logger` argument directly. The `setup_stage_file_logger` function would typically configure a global/module logger that `transform_data` then uses via `logging.getLogger(__name__)`.

### How ZenFlow Discovers the Logger's Output

1.  **Update `configure.py`**:
    *   Import `configs.loggers_config`.
    *   Ensure `transform` (and specifically `logged_transform`) is processed.
    ```python
    # configure.py (snippet)
    import configs.transform_config # Has logged_transform
    import configs.loggers_config   # Defines logger configs
    # ...
    # If you are also running quickstart's default_transform, keep its dummy input logic
    # Path("data/raw/input.csv").parent.mkdir(parents=True, exist_ok=True) 
    # pd.DataFrame({'id': [1,2], 'value': [10,20]}).to_csv(Path("data/raw/input.csv"), index=False)
    # os.system(f"dvc add data/raw/input.csv")

    STAGE_GROUPS = ["transform"] # This will pick up all configs in the 'transform' group
    # ...
    ```

2.  **Run Configuration:**
    ```bash
    python configure.py
    ```

3.  **Inspect `dvc.yaml`:**
    Look at the entry for `transform/logged_transform`:
    ```yaml
    stages:
      transform/logged_transform:
        cmd: python -m my_project.run_hydra_stage -cd artifacts/transform -cn logged_transform hydra.run.dir='artifacts/transform/logged_transform'
        deps:
        - data/raw/input.csv
        outs:
        # Output from transform_data itself
        - artifacts/transform/logged_transform/data/processed/output_with_logging.csv
        # Output from the composed logger!
        - artifacts/transform/logged_transform/logs/stage_execution.log 
        params:
        - artifacts/transform/logged_transform.yaml
    ```
    ZenFlow's `configure_pipeline` calls `OmegaConf.resolve(cfg)` on the *fully composed* configuration for `transform/logged_transform`. This composed config includes the `logger` node (because of `hydra_defaults`), which itself contains `log_file_path_str=outs_path("logs/stage_execution.log")`. The `outs:` resolver is triggered, and the log file path is added to the `outs` for the `transform/logged_transform` DVC stage.

### Running the Stage

When you run `dvc exp run transform/logged_transform` (or `dvc exp run` if it's the only changed part):
*   Hydra will instantiate the `logger` part of its config, calling `setup_stage_file_logger`.
*   The (mock) `setup_stage_file_logger` will print its message. Because its `log_file_path_str` used `outs_path`, DVC now tracks this log file.
*   The `transform_data` function will run. Its own `log = logging.getLogger(__name__)` statements would go to the logger configured by `setup_stage_file_logger` if it configured the root logger or a relevant parent.
*   The file `artifacts/transform/logged_transform/logs/stage_execution.log` will be created (even if it's just empty or with minimal content in this mock, DVC tracks its existence as an output).

### Benefits
*   **Reusability:** Define logger (or trainer, optimizer, etc.) configs once, use them in many stages.
*   **Separation of Concerns:** Stage logic doesn't need to be cluttered with detailed setup for common components.
*   **Dynamic Outputs:** ZenFlow automatically picks up DVC outputs (`outs_path`) declared deep within composed configuration structures.
*   **Flexibility:** Easily swap out components by changing the `hydra_defaults` (e.g., switch to `verbose_file_logger`).

## Conclusion

Hydra's composition, combined with ZenFlow's `deps_path` and `outs_path` discovery, allows for building sophisticated and modular MLOps pipelines where even common components can have their outputs tracked by DVC without manual duplication in the `dvc.yaml`. This leads to cleaner, more maintainable, and highly reproducible workflows.