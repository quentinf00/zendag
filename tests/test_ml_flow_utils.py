# tests/test_mlflow_utils.py
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path
import os
from omegaconf import OmegaConf

from zenflow.mlflow_utils import mlflow_run


# A simple function to be decorated
def sample_stage_function(some_arg="default"):
    # print(f"Function called with {some_arg}")
    if some_arg == "fail":
        raise ValueError("Simulated failure")
    return "success"


@pytest.fixture
def mock_mlflow_env(monkeypatch):
    """Sets up a mocked MLflow environment."""
    monkeypatch.setenv("MLFLOW_PROJECT_NAME", "TestProject")
    monkeypatch.setenv("DVC_STAGE", "test_group/test_stage")
    # For hydra config loading inside mlflow_run
    monkeypatch.setenv("HYDRA_CONFIG_DIR", "artifacts/test_group")  # Mock where configs are
    monkeypatch.setenv("HYDRA_CONFIG_NAME", "test_stage")


@patch("zenflow.mlflow_utils.mlflow")  # Mock the entire mlflow module
@patch("zenflow.mlflow_utils.OmegaConf")
@patch("zenflow.mlflow_utils.pd")
@patch("zenflow.mlflow_utils.Path")  # To control Path().exists() etc.
def test_mlflow_run_success(MockPath, MockPandas, MockOmegaConf, mock_mlflow_module, mock_mlflow_env, temp_cwd):
    # --- Setup Mocks ---
    # Mock MLflow context managers
    mock_parent_run = MagicMock()
    mock_parent_run.info.run_id = "parent_run_123"
    mock_child_run = MagicMock()
    mock_child_run.info.run_id = "child_run_456"

    mock_mlflow_module.start_run.return_value.__enter__.side_effect = [
        mock_parent_run,
        mock_child_run,
    ]
    mock_mlflow_module.start_run.return_value.__exit__.return_value = None

    # Mock config loading
    mock_config_content = OmegaConf.create({"param1": "value1", "nested": {"param2": 10}})
    MockOmegaConf.load.return_value = mock_config_content
    MockOmegaConf.to_container.return_value = {
        "param1": "value1",
        "nested.param2": 10,
    }  # Flattened
    MockPandas.json_normalize.return_value.to_dict.return_value = [{"param1": "value1", "nested.param2": 10}]

    # Mock Path for .pipeline_id, config file, and log file
    mock_pipeline_id_path_instance = MagicMock(spec=Path)
    mock_pipeline_id_path_instance.exists.return_value = False  # Test creating .pipeline_id
    mock_pipeline_id_path_instance.read_text.return_value = "old_parent_run_id"  # If it existed

    mock_config_path_instance = MagicMock(spec=Path)
    mock_config_path_instance.exists.return_value = True
    mock_config_path_instance.as_posix.return_value = "artifacts/test_group/test_stage.yaml"
    mock_config_path_instance.read_text.return_value = "artifacts/test_group/test_stage.yaml"

    # Mock hydra for log path (this is tricky as it uses Hydra's global state)
    # For simplicity, assume Hydra is initialized and provides the output_dir
    mock_hydra_config_get = MagicMock()
    mock_hydra_config_get.get.return_value.runtime.output_dir = Path(temp_cwd / "artifacts/test_group/test_stage")
    mock_log_path_instance = MagicMock(spec=Path)
    mock_log_path_instance.as_posix.return_value = str(temp_cwd / "artifacts/test_group/test_stage/run.log")

    def path_side_effect(path_arg):
        if str(path_arg) == ".pipeline_id":
            return mock_pipeline_id_path_instance
        elif str(path_arg) == "artifacts/test_group/test_stage.yaml":
            return mock_config_path_instance
        elif "run.log" in str(path_arg):  # General match for log path
            # This needs to be more specific if Hydra path is complex
            return mock_log_path_instance
        return MagicMock(spec=Path)  # Default mock for other Path calls

    MockPath.side_effect = path_side_effect

    # --- Decorate and Call ---
    decorated_function = mlflow_run(sample_stage_function, project_name="TestProject")
    with patch(
        "zenflow.mlflow_utils.hydra.core.hydra_config.HydraConfig",
        mock_hydra_config_get,
    ):  # Mock Hydra's runtime
        result = decorated_function("test_arg")

    # --- Assertions ---
    assert result == "success"
    mock_mlflow_module.set_experiment.assert_called_once_with("TestProject")
    assert mock_mlflow_module.start_run.call_count == 2  # Parent and child

    # Check parent run start (first call to start_run)
    first_start_run_call = mock_mlflow_module.start_run.call_args_list[0]
    assert first_start_run_call[1]["run_id"] is None  # No .pipeline_id initially

    # Check child run start (second call to start_run)
    second_start_run_call = mock_mlflow_module.start_run.call_args_list[1]
    assert second_start_run_call[1]["run_name"] == "test_group/test_stage"
    assert second_start_run_call[1]["nested"] is True

    MockOmegaConf.load.assert_called_once_with(mock_config_path_instance)
    mock_mlflow_module.log_param.assert_any_call("param1", "value1")
    mock_mlflow_module.log_param.assert_any_call("nested.param2", 10)
    mock_mlflow_module.log_artifact.assert_any_call("artifacts/test_group/test_stage.yaml")
    mock_mlflow_module.log_artifact.assert_any_call(str(temp_cwd / "artifacts/test_group/test_stage/run.log"))

    # Check .pipeline_id was written
    mock_pipeline_id_path_instance.write_text.assert_called_once_with(mock_parent_run.info.run_id + "\n")


@patch("zenflow.mlflow_utils.mlflow")
@patch("zenflow.mlflow_utils.OmegaConf")  # Mock less for failure path, focus on exception
@patch("zenflow.mlflow_utils.Path")
def test_mlflow_run_failure(
    MockPath,
    MockOmegaConf,
    mock_mlflow_module,
    mock_mlflow_env,
    temp_cwd,  # Use the env fixture
):
    mock_parent_run = MagicMock()
    mock_child_run = MagicMock()
    mock_mlflow_module.start_run.return_value.__enter__.side_effect = [
        mock_parent_run,
        mock_child_run,
    ]

    mock_pipeline_id_path_instance = MagicMock(spec=Path)
    mock_pipeline_id_path_instance.exists.return_value = False  # Test creating .pipeline_id
    mock_pipeline_id_path_instance.read_text.return_value = "old_parent_run_id"  # If it existed

    mock_config_path_instance = MagicMock(spec=Path)
    mock_config_path_instance.exists.return_value = True
    mock_config_path_instance.as_posix.return_value = "artifacts/test_group/test_stage.yaml"
    mock_config_path_instance.read_text.return_value = "artifacts/test_group/test_stage.yaml"

    mock_log_path_instance = MagicMock(spec=Path)
    mock_log_path_instance.as_posix.return_value = str(temp_cwd / "artifacts/test_group/test_stage/run.log")

    def path_side_effect(path_arg):
        if str(path_arg) == ".pipeline_id":
            return mock_pipeline_id_path_instance
        elif str(path_arg) == "artifacts/test_group/test_stage.yaml":
            return mock_config_path_instance
        elif "run.log" in str(path_arg):  # General match for log path
            # This needs to be more specific if Hydra path is complex
            return mock_log_path_instance
        return MagicMock(spec=Path)  # Default mock for other Path calls

    MockPath.side_effect = path_side_effect
    MockOmegaConf.load.return_value = OmegaConf.create({})  # Minimal config

    mock_hydra_config_get = MagicMock()
    mock_hydra_config_get.get.return_value.runtime.output_dir = str(temp_cwd / "artifacts/test_group/test_stage")

    mock_pipeline_id_path_instance = MagicMock(spec=Path)
    mock_pipeline_id_path_instance.exists.return_value = False  # Test creating .pipeline_id
    mock_pipeline_id_path_instance.read_text.return_value = "old_parent_run_id"  # If it existed

    decorated_function = mlflow_run(sample_stage_function)
    with pytest.raises(ValueError, match="Simulated failure"):
        with patch(
            "zenflow.mlflow_utils.hydra.core.hydra_config.HydraConfig",
            mock_hydra_config_get,
        ):
            decorated_function("fail")  # This argument makes sample_stage_function raise an error

    # Assert that log artifact was still attempted on failure
    # The path to run.log needs to be correctly mocked via MockPath or HydraConfig mock
    expected_log_path_str = str(Path(f"artifacts/test_group/test_stage") / "run.log")
    mock_mlflow_module.log_artifact.assert_any_call(str(temp_cwd / expected_log_path_str))
