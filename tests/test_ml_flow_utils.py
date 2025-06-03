# tests/test_mlflow_utils.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from omegaconf import OmegaConf

from zendag.mlflow_utils import mlflow_run

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


class TestMlflowRun:
    """Test suite for the mlflow_run decorator."""

    CONTROLLED_CONFIG_DIR_STR = "controlled/configs/test_group"
    CONTROLLED_STAGE_DIR_STR = "controlled/artifacts/test_group/test_stage"
    # DVC_STAGE="test_group/test_stage" -> stage="test_group", config_name="test_stage"
    EXPECTED_STAGE_NAME = "test_group"
    EXPECTED_CONFIG_NAME = "test_stage"

    @pytest.fixture
    def mock_common_dependencies(self):
        """Sets up common mocks for mlflow, OmegaConf, pd, and Path."""
        with patch("zendag.mlflow_utils.mlflow") as mock_mlflow, \
             patch("zendag.mlflow_utils.OmegaConf") as mock_omega_conf, \
             patch("zendag.mlflow_utils.pd") as mock_pd, \
             patch("zendag.mlflow_utils.Path") as mock_path_constructor:

            # MLflow run contexts
            mock_parent_run = MagicMock()
            mock_parent_run.info.run_id = "test_parent_run_id_123"
            mock_child_run = MagicMock()
            mock_child_run.info.run_id = "test_child_run_id_456"
            mock_mlflow.start_run.return_value.__enter__.side_effect = [
                mock_parent_run, mock_child_run
            ]
            mock_mlflow.start_run.return_value.__exit__.return_value = None

            # OmegaConf loading
            mock_config_content = OmegaConf.create({"param1": "value1", "nested": {"param2": 10}})
            mock_omega_conf.load.return_value = mock_config_content
            # For pd.json_normalize
            mock_omega_conf.to_container.return_value = {"param1": "value1", "nested": {"param2": 10}}

            # Pandas normalization
            mock_pd.json_normalize.return_value.to_dict.return_value = [
                {"param1": "value1", "nested.param2": 10}
            ]

            yield {
                "mlflow": mock_mlflow,
                "OmegaConf": mock_omega_conf,
                "pd": mock_pd,
                "Path": mock_path_constructor,
                "parent_run": mock_parent_run,
                "child_run": mock_child_run,
            }

    def _setup_path_mocks(self, Path_mock, pipeline_id_exists, config_exists, log_exists):
        """Helper to configure Path mocks for different scenarios."""
        mock_pipeline_id_file = MagicMock(spec=Path)
        mock_config_dir_intermediate = MagicMock(spec=Path)
        mock_log_dir_intermediate = MagicMock(spec=Path)
        mock_final_config_file = MagicMock(spec=Path)
        mock_final_log_file = MagicMock(spec=Path)

        def path_constructor_side_effect(path_arg):
            path_str = str(path_arg)
            if path_str == ".pipeline_id":
                return mock_pipeline_id_file
            elif path_str == self.CONTROLLED_CONFIG_DIR_STR:
                return mock_config_dir_intermediate
            elif path_str == self.CONTROLLED_STAGE_DIR_STR:
                return mock_log_dir_intermediate
            return MagicMock(spec=Path) # Should not be hit with controlled fns

        Path_mock.side_effect = path_constructor_side_effect

        # Configure intermediate path divisions
        mock_config_dir_intermediate.__truediv__.return_value = mock_final_config_file
        mock_log_dir_intermediate.__truediv__.return_value = mock_final_log_file

        # Configure final path object behaviors
        mock_pipeline_id_file.exists.return_value = pipeline_id_exists
        mock_pipeline_id_file.read_text.return_value = "existing_parent_run_id_789"
        mock_pipeline_id_file.write_text = MagicMock()

        mock_final_config_file.exists.return_value = config_exists
        mock_final_config_file.as_posix.return_value = \
            f"{self.CONTROLLED_CONFIG_DIR_STR}/{self.EXPECTED_CONFIG_NAME}.yaml"

        mock_final_log_file.exists.return_value = log_exists
        mock_final_log_file.as_posix.return_value = \
            f"{self.CONTROLLED_STAGE_DIR_STR}/run.log"

        return {
            "pipeline_id_file": mock_pipeline_id_file,
            "config_dir_intermediate": mock_config_dir_intermediate,
            "log_dir_intermediate": mock_log_dir_intermediate,
            "final_config_file": mock_final_config_file,
            "final_log_file": mock_final_log_file,
        }

    def test_success_new_parent_run(self, mock_common_dependencies, mock_mlflow_env):
        """Test successful run, new parent ID, DVC stage, config & log exist."""
        deps = mock_common_dependencies
        path_mocks = self._setup_path_mocks(deps["Path"], pipeline_id_exists=False, config_exists=True, log_exists=True)

        mock_configs_dir_fn = MagicMock(return_value=self.CONTROLLED_CONFIG_DIR_STR)
        mock_stage_dir_fn = MagicMock(return_value=self.CONTROLLED_STAGE_DIR_STR)

        decorated_function = mlflow_run(
            project_name="TestProject",
            configs_dir_fn=mock_configs_dir_fn,
            stage_dir_fn=mock_stage_dir_fn
        )(sample_stage_function)
        result = decorated_function("test_arg")

        assert result == "success"
        deps["mlflow"].set_experiment.assert_called_once_with("TestProject")
        assert deps["mlflow"].start_run.call_count == 2

        # Parent run (new)
        parent_call_args = deps["mlflow"].start_run.call_args_list[0][1]
        assert parent_call_args["run_id"] is None
        path_mocks["pipeline_id_file"].write_text.assert_called_once_with(
            deps["parent_run"].info.run_id + "\n"
        )

        # Child run
        child_call_args = deps["mlflow"].start_run.call_args_list[1][1]
        assert child_call_args["run_name"] == f"{self.EXPECTED_STAGE_NAME}/{self.EXPECTED_CONFIG_NAME}"
        assert child_call_args["nested"] is True

        # Path function calls
        mock_configs_dir_fn.assert_called_once()
        # Called once for success log, once for potential failure log (though not hit here)
        mock_stage_dir_fn.assert_any_call(self.EXPECTED_STAGE_NAME, self.EXPECTED_CONFIG_NAME)
        assert mock_stage_dir_fn.call_count >= 1 # Can be 1 or 2 depending on exact code path for logging

        # Config loading and logging
        path_mocks["config_dir_intermediate"].__truediv__.assert_called_once_with(f"{self.EXPECTED_CONFIG_NAME}.yaml")
        deps["OmegaConf"].load.assert_called_once_with(path_mocks["final_config_file"])
        deps["mlflow"].log_param.assert_any_call("param1", "value1")
        deps["mlflow"].log_param.assert_any_call("nested.param2", 10)
        deps["mlflow"].log_artifact.assert_any_call(path_mocks["final_config_file"].as_posix())

        # Log file logging
        path_mocks["log_dir_intermediate"].__truediv__.assert_any_call("run.log")
        deps["mlflow"].log_artifact.assert_any_call(path_mocks["final_log_file"].as_posix())

    def test_success_existing_parent_run(self, mock_common_dependencies, mock_mlflow_env):
        """Test successful run with an existing parent ID."""
        deps = mock_common_dependencies
        path_mocks = self._setup_path_mocks(deps["Path"], pipeline_id_exists=True, config_exists=True, log_exists=True)

        mock_configs_dir_fn = MagicMock(return_value=self.CONTROLLED_CONFIG_DIR_STR)
        mock_stage_dir_fn = MagicMock(return_value=self.CONTROLLED_STAGE_DIR_STR)

        decorated_function = mlflow_run(
            configs_dir_fn=mock_configs_dir_fn,
            stage_dir_fn=mock_stage_dir_fn
        )(sample_stage_function)
        decorated_function("test_arg")

        path_mocks["pipeline_id_file"].read_text.assert_called_once()
        path_mocks["pipeline_id_file"].write_text.assert_not_called() # Should not write if ID existed

        parent_call_args = deps["mlflow"].start_run.call_args_list[0][1]
        assert parent_call_args["run_id"] == "existing_parent_run_id_789"

    def test_failure_in_wrapped_function(self, mock_common_dependencies, mock_mlflow_env):
        """Test failure in the wrapped function, ensuring log is still captured."""
        deps = mock_common_dependencies
        path_mocks = self._setup_path_mocks(deps["Path"], pipeline_id_exists=False, config_exists=True, log_exists=True)

        mock_configs_dir_fn = MagicMock(return_value=self.CONTROLLED_CONFIG_DIR_STR)
        mock_stage_dir_fn = MagicMock(return_value=self.CONTROLLED_STAGE_DIR_STR)

        decorated_function = mlflow_run(
            configs_dir_fn=mock_configs_dir_fn,
            stage_dir_fn=mock_stage_dir_fn
        )(sample_stage_function)

        with pytest.raises(ValueError, match="Simulated failure"):
            decorated_function("fail")

        # Ensure log artifact for run.log was attempted even on failure
        mock_stage_dir_fn.assert_any_call(self.EXPECTED_STAGE_NAME, self.EXPECTED_CONFIG_NAME)
        path_mocks["log_dir_intermediate"].__truediv__.assert_any_call("run.log")
        deps["mlflow"].log_artifact.assert_any_call(path_mocks["final_log_file"].as_posix())

        # Config artifact should also have been logged before failure
        deps["mlflow"].log_artifact.assert_any_call(path_mocks["final_config_file"].as_posix())

    def test_config_file_not_found(self, mock_common_dependencies, mock_mlflow_env):
        """Test scenario where the config file does not exist."""
        deps = mock_common_dependencies
        # Config does not exist, log file does (for this test)
        path_mocks = self._setup_path_mocks(deps["Path"], pipeline_id_exists=False, config_exists=False, log_exists=True)

        mock_configs_dir_fn = MagicMock(return_value=self.CONTROLLED_CONFIG_DIR_STR)
        mock_stage_dir_fn = MagicMock(return_value=self.CONTROLLED_STAGE_DIR_STR)

        decorated_function = mlflow_run(
            configs_dir_fn=mock_configs_dir_fn,
            stage_dir_fn=mock_stage_dir_fn
        )(sample_stage_function)
        decorated_function("test_arg")

        deps["OmegaConf"].load.assert_not_called()
        # Check that log_param was not called (as it depends on loaded config)
        # This requires checking that *no* call to log_param had these specific args,
        # or more simply, that its call_count for params is 0 if no other params are logged.
        # For simplicity, we assume no other params are logged by default.
        assert deps["mlflow"].log_param.call_count == 0

        # Check that config artifact was not logged
        # We need to iterate through calls to ensure the specific config path wasn't logged
        config_artifact_logged = any(
            call_args[0][0] == path_mocks["final_config_file"].as_posix()
            for call_args in deps["mlflow"].log_artifact.call_args_list
        )
        assert not config_artifact_logged

        # Log file should still be logged
        deps["mlflow"].log_artifact.assert_any_call(path_mocks["final_log_file"].as_posix())

    def test_log_file_not_found_on_success(self, mock_common_dependencies, mock_mlflow_env):
        """Test scenario where run.log does not exist on successful execution."""
        deps = mock_common_dependencies
        # Config exists, log file does NOT
        path_mocks = self._setup_path_mocks(deps["Path"], pipeline_id_exists=False, config_exists=True, log_exists=False)

        mock_configs_dir_fn = MagicMock(return_value=self.CONTROLLED_CONFIG_DIR_STR)
        mock_stage_dir_fn = MagicMock(return_value=self.CONTROLLED_STAGE_DIR_STR)

        decorated_function = mlflow_run(
            configs_dir_fn=mock_configs_dir_fn,
            stage_dir_fn=mock_stage_dir_fn
        )(sample_stage_function)
        decorated_function("test_arg")

        # Config artifact should be logged
        deps["mlflow"].log_artifact.assert_any_call(path_mocks["final_config_file"].as_posix())

        # Check that log file artifact was NOT logged
        log_artifact_logged = any(
            call_args[0][0] == path_mocks["final_log_file"].as_posix()
            for call_args in deps["mlflow"].log_artifact.call_args_list
        )
        assert not log_artifact_logged

    # Additional tests could cover:
    # - No DVC_STAGE environment variable (child run name uses function name, no config/log handling)
    # - Project name variations (from env, from arg, default)
    # - Exceptions during OmegaConf.load or pd.json_normalize
    # - Behavior when stage_dir_fn or configs_dir_fn themselves raise errors (though less likely)
