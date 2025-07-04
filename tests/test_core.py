# tests/test_core.py
from pathlib import Path

import hydra  # For hydra.initialize if needed, though configure_pipeline does it
import hydra_zen
import omegaconf
import pytest
import yaml  # For parsing dvc.yaml
from omegaconf import OmegaConf

from zendag.core import (
    configure_pipeline,
)

from .conftest import (
    fixture_project_configs_dir_fn,
    fixture_project_stage_dir_fn,
)


# A dummy target function for hydra-zen builds
def dummy_stage_function(output_path: str, input_path: str = None, some_param: int = 0):
    ...
    # In a real scenario, this function would do something.
    # For testing configure_pipeline, its existence is enough.
    # print(f"Dummy stage: out={output_path}, in={input_path}, param={some_param}")
    print(f"Processed {input_path} to {output_path} with {some_param}")


@pytest.fixture
def setup_hydra_for_compose(temp_cwd):
    """Ensure hydra can compose from the temp directory"""
    # configure_pipeline does hydra.initialize itself, but if individual tests need it:
    if not hydra.core.global_hydra.GlobalHydra.instance().is_initialized():
        hydra.initialize(version_base="1.3", config_path=None)  # Initialize relative to CWD
    yield
    if hydra.core.global_hydra.GlobalHydra.instance().is_initialized():
        hydra.core.global_hydra.GlobalHydra.instance().clear()


def test_configure_pipeline_single_stage_no_deps(
    temp_cwd: Path,  # Changes CWD to temp_cwd
    temp_artifacts_dir: Path,
    zen_store: hydra_zen.ZenStore,
):
    # --- Define a simple stage config ---
    stage_name = "data_prep"
    config_name = "process_a"
    output_file = "processed_a.csv"

    # Create a builds config for the dummy function
    ProcessAConfig = hydra_zen.builds(
        dummy_stage_function,
        output_path=f"${{outs:{output_file}}}",  # Using the string directly for ZenBuildsConf
        some_param=10,
        populate_full_signature=True,  # Ensure all args are in the config
    )
    # Add to store (mimicking user's configure.py)
    stage_store = zen_store(group=stage_name)
    stage_store(ProcessAConfig, name=config_name)

    # --- Call configure_pipeline ---
    # Use the test-specific directory functions that point to temp_artifacts_dir
    stage_dir_func = fixture_project_stage_dir_fn(temp_artifacts_dir)
    configs_dir_func = fixture_project_configs_dir_fn(temp_artifacts_dir)

    configure_pipeline(
        store=zen_store,
        stage_groups=[stage_name],
        stage_dir_fn=stage_dir_func,
        configs_dir_fn=configs_dir_func,
        dvc_filename="dvc_test.yaml",
        run_script="my_project.run_stage",
    )

    # --- Assertions ---
    # 1. Check composed config was written
    composed_config_path = Path(stage_name) / f"{config_name}.yaml"
    assert (Path(temp_artifacts_dir) / composed_config_path).exists()
    composed_cfg = OmegaConf.load(Path(temp_artifacts_dir) / composed_config_path)
    print(OmegaConf.to_yaml(composed_cfg))
    assert composed_cfg._target_ == "tests.test_core.dummy_stage_function"  # Path to dummy_stage_function
    assert composed_cfg.some_param == 10
    # Check that 'outs' resolved correctly during write (it won't be in the written file, but was used for path)
    # The path in the config should be the resolved one (relative to its own output dir)
    assert composed_cfg.output_path == output_file  # outs should resolve to the filename itself

    # 2. Check dvc.yaml was written
    dvc_file_path = temp_cwd / "dvc_test.yaml"
    assert dvc_file_path.exists()
    with open(dvc_file_path, "r") as f:
        dvc_data = yaml.safe_load(f)

    # 3. Check dvc.yaml content
    dvc_stage_key = f"{stage_name}/{config_name}"
    assert dvc_stage_key in dvc_data["stages"]
    stage_info = dvc_data["stages"][dvc_stage_key]

    expected_cmd_part = (
        f"python -m my_project.run_stage "
        f"-cd {stage_name} -cn {config_name} "
        "+zendag=base "
        f"hydra.run.dir='{Path(stage_name) / config_name}'"
    )
    assert expected_cmd_part in stage_info["cmd"]
    assert stage_info["deps"] == []  # No dependencies
    assert stage_info["outs"] == [str(Path(stage_name) / config_name / Path(output_file).name)]
    assert stage_info["params"] == [{str(composed_config_path): None}]


def test_configure_pipeline_with_inter_stage_deps(
    temp_cwd: Path,
    temp_artifacts_dir: Path,
    zen_store: hydra_zen.ZenStore,
):
    # --- Stage 1: generate_data ---
    stage1_name = "generate_data"
    config1_name = "source_x"
    stage1_output = "raw_x.csv"

    GenDataConfig = hydra_zen.builds(
        dummy_stage_function,
        output_path=f"${{outs:{stage1_output}}}",
        populate_full_signature=True,
    )
    zen_store(group=stage1_name)(GenDataConfig, name=config1_name)

    # --- Stage 2: process_data ---
    stage2_name = "process_data"
    config2_name = "transform_x"
    stage2_output = "processed_x.parquet"
    # Stage 2 depends on stage 1's output
    # For deps to resolve correctly, the hydra resolver for 'stage_dir' needs to be active
    # and the stage_dir_fn for that needs to be the one used by configure_pipeline
    stage_dir_func = fixture_project_stage_dir_fn(temp_artifacts_dir)  # This will be used by deps resolver

    ProcessDataConfig = hydra_zen.builds(
        dummy_stage_function,
        # Correctly refer to stage1 output.
        # The `${deps:...}` resolver will use the base_dir part if input_stage/name are given.
        # The `${stage_dir(stage1_name, config1_name)}` will be resolved by the 'stage_dir' resolver.
        input_path=f"${{deps:{stage_dir_func(stage1_name, config1_name)}/{stage1_output},True}}",
        output_path=f"${{outs:{stage2_output}}}",
        some_param=22,
        populate_full_signature=True,
    )
    zen_store(group=stage2_name)(ProcessDataConfig, name=config2_name)

    # --- Call configure_pipeline ---
    configs_dir_func = fixture_project_configs_dir_fn(temp_artifacts_dir)

    configure_pipeline(
        store=zen_store,
        stage_groups=[stage1_name, stage2_name],
        stage_dir_fn=stage_dir_func,  # Passed to configure_pipeline, will be used by its 'stage_dir' resolver
        configs_dir_fn=configs_dir_func,
        dvc_filename="dvc_deps_test.yaml",
    )

    # --- Assertions ---
    dvc_file_path = temp_cwd / "dvc_deps_test.yaml"
    assert dvc_file_path.exists()
    with open(dvc_file_path, "r") as f:
        dvc_data = yaml.safe_load(f)

    # Check stage 2 (process_data)
    dvc_stage2_key = f"{stage2_name}/{config2_name}"
    assert dvc_stage2_key in dvc_data["stages"]
    stage2_info = dvc_data["stages"][dvc_stage2_key]

    expected_stage1_output_path_in_dvc_deps = str(Path(stage1_name) / config1_name / stage1_output)
    print(dvc_data)
    print(stage2_info)
    assert stage2_info["deps"] == [expected_stage1_output_path_in_dvc_deps]
    assert stage2_info["outs"] == [str(Path(stage2_name) / config2_name / stage2_output)]

    # Check composed config for stage 2
    composed_stage2_config_path = temp_artifacts_dir / stage2_name / f"{config2_name}.yaml"
    assert composed_stage2_config_path.exists()
    s2_cfg = OmegaConf.load(composed_stage2_config_path)
    # The input_path in the *written* config file should be resolved relative to nothing (i.e., the full path)
    # because the `${deps:...}` resolver just returns `k` after appending to the list.
    # And `${stage_dir...}` resolves to the path.
    assert s2_cfg.input_path == str(Path(stage1_name) / config1_name / stage1_output)


def test_configure_pipeline_empty_stage_group(
    temp_cwd: Path,
    temp_artifacts_dir: Path,
    zen_store: hydra_zen.ZenStore,
    caplog,  # To capture log messages
):
    caplog.set_level("WARNING")
    configure_pipeline(
        store=zen_store,  # Empty store for this group
        stage_groups=["non_existent_stage"],
        stage_dir_fn=fixture_project_stage_dir_fn(temp_artifacts_dir),
        configs_dir_fn=fixture_project_configs_dir_fn(temp_artifacts_dir),
    )
    assert "No configurations found in store for stage group: 'non_existent_stage'" in caplog.text
    dvc_file = temp_cwd / "dvc.yaml"  # Default name
    assert dvc_file.exists()  # Should still create an empty dvc.yaml
    with open(dvc_file, "r") as f:
        dvc_data = yaml.safe_load(f)
    assert dvc_data["stages"] == {}


def test_configure_pipeline_config_resolution_failure(
    temp_cwd: Path, temp_artifacts_dir: Path, zen_store: hydra_zen.ZenStore, caplog
):
    caplog.set_level("ERROR")
    stage_name = "failing_stage"
    config_name = "bad_config"

    # Config with a missing mandatory value that will fail OmegaConf.resolve()
    # We need to use a structure that Hydra-Zen builds where a part is MISSING
    # This specific way of making it fail resolution is tricky with just string interpolation.
    # Let's make it fail due to a bad interpolation for 'outs' or 'deps'.
    BadConf = hydra_zen.make_config(
        bad_output="${outs:${this_is_not_closed}"  # Malformed interpolation
    )
    zen_store(group=stage_name)(BadConf, name=config_name)

    with pytest.raises(omegaconf.errors.GrammarParseError):
        configure_pipeline(
            store=zen_store,
            stage_groups=[stage_name],
            stage_dir_fn=fixture_project_stage_dir_fn(temp_artifacts_dir),
            configs_dir_fn=fixture_project_configs_dir_fn(temp_artifacts_dir),
        )

    assert " Failed add store configurations to hydra" in caplog.text
