import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import hydra
from hydra.core.global_hydra import GlobalHydra
import hydra_zen
from omegaconf import OmegaConf

_log = logging.getLogger(__name__)

ARTIFACTS_ROOT = os.getenv("ARTIFACTS_DIR", "workbench")  # Default to "workbench"


# Default stage dir function, can be overridden
def default_stage_dir_fn(stage: str | None, name: str) -> str:
    """Generates the default path for a stage's output directory."""
    if stage is None:
        return f"{ARTIFACTS_ROOT}/{name}"
    return f"{ARTIFACTS_ROOT}/{stage}/{name}"


# Default config dir function, can be overridden
def default_configs_dir_fn(stage: str | None) -> str:
    """Generates the default path for storing composed stage configs."""
    if stage is None:
        return ARTIFACTS_ROOT
    return f"{ARTIFACTS_ROOT}/{stage}"


def configure_pipeline(
    store: hydra_zen.ZenStore | None = None,
    stage_groups: List[str | None] | None = None,
    stage_dir_fn: Callable[[str | None, str], str] = default_stage_dir_fn,
    configs_dir_fn: Callable[[str | None], str] = default_configs_dir_fn,
    dvc_filename: str = "dvc.yaml",
    run_script: str = "zendag.run",  # Changed from xp_workflow.run
    config_root: Optional[str] = None,  # Optional root for hydra initialization
    manual_dvc: Optional[dict] = None,
    wdir=None,
    dvc_stage_name_fn: Callable | None = None,
    dry: bool = False,
) -> dict[str, Path]:
    """
    Configures the DVC pipeline based on Hydra-Zen stored configurations.

    Generates composed Hydra configs for each stage instance and creates a
    dvc.yaml file defining the pipeline stages, dependencies, and outputs.

    Dependencies and outputs are automatically discovered during Hydra config
    resolution via specially registered resolvers for 'deps' and 'outs'.

    Args:
        store: The Hydra-Zen store containing the configured stage components.
        stage_groups: A list of stage group names (e.g., 'training', 'data_prep')
                      present in the store. Stages within these groups will be
                      processed.
        stage_dir_fn: A function `fn(stage_name, config_name) -> str` that returns
                      the base output directory path for a given stage instance.
                      Defaults to `workbench/<stage_name>/<config_name>`.
        configs_dir_fn: A function `fn(stage_name) -> str` that returns the directory
                        path where composed Hydra configs for a stage group will be
                        stored. Defaults to `workbench/<stage_name>`.
        dvc_filename: The name of the DVC pipeline file to generate. Defaults to 'dvc.yaml'.
        run_script: The Python module path to execute for running a stage (e.g., 'my_project.run').
                    Defaults to 'zendag.run'.
        config_root: The path relative to which Hydra should initialize (defaults to cwd).
                     Needed if configs are stored outside the cwd.
    """

    dvc_stages: Dict[str, Dict[str, Any]] = {}
    all_deps: Dict[Tuple[str, str], List[str]] = {}
    all_outs: Dict[Tuple[str, str], List[str]] = {}
    stage_config_paths: Dict[str, Path] = {}

    if store is None:
        store = hydra_zen.store

    if dvc_stage_name_fn is None:
        dvc_stage_name_fn = (lambda g, n: f"{g}/{n}") if stage_groups is not None else (lambda _, n: n)

    if stage_groups is None:
        stage_groups = [None]

    if wdir is None:
        wdir = stage_dir_fn(None, "")

    Path(wdir).mkdir(exist_ok=True, parents=True)  # Ensure the working directory exists
    if not (Path(wdir) / "projroot").exists():
        os.symlink(
            Path(*([".."] * len(Path(wdir).parts))), Path(wdir) / "projroot", target_is_directory=True
        )  # Link projroot to working directory

    def wdir_p(p, w=True, lk="projroot"):
        if w:
            if wdir is None:
                return p
            return str(Path(p).absolute().relative_to(Path(wdir).absolute()))
        return lk + "/" + str(p)

    _log.info("Initializing Hydra (version_base=1.3) for configuration composition.")
    # Initialize Hydra once if needed, respecting config_root

    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    if config_root:
        hydra.initialize(version_base="1.3", config_path=config_root)
    else:
        hydra.initialize(version_base="1.3")

    try:
        store.add_to_hydra_store(overwrite_ok=True)
        _log.debug("  Successfully added store configurations to hydra")
    except Exception as e:
        _log.error(
            f"  Failed add store configurations to hydra'. Error: {e}",
            exc_info=True,
        )
        raise e
    _log.info(f"Processing stage groups: {stage_groups}")

    for stage in stage_groups:
        cfg_dir = Path(configs_dir_fn(stage))
        cfg_dir.mkdir(exist_ok=True, parents=True)
        _log.debug(f"Ensured configuration directory exists: {cfg_dir}")

        stage_items = list(store[stage])  # Get all items (configs) for this stage group
        if not stage_items:
            _log.warning(f"No configurations found in store for stage group: '{stage}'")
            continue

        _log.info(f"Processing stage group '{stage}' with {len(stage_items)} configuration(s)...")

        for _, name in stage_items:
            stage_key = (stage, name)
            _log.info(f"  Processing configuration: '{name}'")

            # 1. Compose the configuration
            try:
                if stage is None:
                    cfg = hydra.compose(name)
                else:
                    cfg = hydra.compose(overrides=[f"+{stage}={name}"])
                    cfg = OmegaConf.select(cfg, stage)
                _log.debug(f"  Successfully composed configuration for '{stage}/{name}'.")
            except Exception as e:
                _log.error(
                    f"  Failed to compose configuration for '{stage}/{name}'. Error: {e}",
                    exc_info=True,
                )
                continue

            # 3. Resolve config to discover deps/outs via side-effects
            current_deps: List[str] = []
            current_outs: List[str] = []

            # IMPORTANT: Register resolvers *before* resolve call
            # These resolvers have side-effects (appending to lists)

            hydra_run_dir = wdir_p(stage_dir_fn(stage, name))
            OmegaConf.register_new_resolver(
                "outs", lambda k: current_outs.append(hydra_run_dir + "/" + k) or k, replace=True
            )

            OmegaConf.register_new_resolver(
                "deps", lambda k, w: current_deps.append(wdir_p(k, w)) or wdir_p(k, w), replace=True
            )
            # Hydra resolver needs the runtime context for the *specific* stage instance

            _log.debug(f"  Resolving configuration for '{stage}/{name}' to discover dependencies and outputs...")
            try:
                OmegaConf.resolve(cfg)
                # Make unique and sort for consistency
                unique_deps = sorted(list(set(current_deps)))
                unique_outs = sorted(list(set(current_outs)))
                all_deps[stage_key] = unique_deps
                all_outs[stage_key] = unique_outs
                _log.info(f"    Discovered Deps: {unique_deps}")
                _log.info(f"    Discovered Outs: {unique_outs}")
            except Exception as e:
                _log.error(
                    f"  Failed during config resolution for '{stage}/{name}'. Check interpolations (esp. deps/outs). Error: {e}",
                    exc_info=True,
                )
                # Store empty lists to avoid crashing later, but log error
                all_deps[stage_key] = []
                all_outs[stage_key] = []

            # 2. Write the composed config (for DVC params tracking)
            composed_config_path = cfg_dir / f"{name}.yaml"
            try:
                composed_config_path.write_text(hydra_zen.to_yaml(cfg))
                _log.debug(f"  Wrote composed configuration to: {composed_config_path}")
            except Exception as e:
                _log.error(
                    f"  Failed to write composed configuration to {composed_config_path}. Error: {e}",
                    exc_info=True,
                )
                continue

            # 4. Define DVC stage entry
            dvc_stage_name = dvc_stage_name_fn(stage, name)
            stage_config_paths[dvc_stage_name] = composed_config_path
            # Ensure the output directory path uses the function, not hardcoded 'workbench'
            dvc_stages[dvc_stage_name] = dict(
                cmd=(
                    f"python -m {run_script} "
                    f"-cd {wdir_p(configs_dir_fn(stage))} -cn {name} "
                    "+zendag=base "
                    f"hydra.run.dir='{hydra_run_dir}'"  # Use quotes for safety
                ),
                **(dict() if wdir is None else dict(wdir=wdir)),
                deps=all_deps[stage_key],
                outs=all_outs[stage_key],
                params=[{f"{wdir_p(composed_config_path)}": None}],  # Use as_posix for consistency
            )
            _log.debug(f"  Defined DVC stage '{dvc_stage_name}'.")

    # 5. Write dvc.yaml
    dvc_file = Path(dvc_filename)
    try:
        # Use OmegaConf to dump YAML for consistency and potentially better handling
        dvc_data = {"stages": dvc_stages}
        if manual_dvc is not None:
            OmegaConf.merge(dvc_data, manual_dvc)

        # Convert DictConfig back to primitive types suitable for pyyaml dump if needed
        # or use OmegaConf.save if hydra_zen.to_yaml doesn't handle it well (it should)
        dvc_file.write_text(hydra_zen.to_yaml(dvc_data))  # hydra-zen's yaml dump is generally good
        _log.info(f"Successfully wrote DVC pipeline configuration to: {dvc_file}")
    except Exception as e:
        _log.error(f"Failed to write DVC pipeline file {dvc_file}. Error: {e}", exc_info=True)
    GlobalHydra.instance().clear()
    return stage_config_paths
