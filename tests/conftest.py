# tests/conftest.py
import hydra
import pytest
from pathlib import Path
import shutil
import os
from omegaconf import OmegaConf
import hydra_zen


# --- Fixtures for Temporary Directories ---
@pytest.fixture
def temp_cwd(tmp_path):
    """Create a temporary current working directory for tests."""
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture
def temp_artifacts_dir(temp_cwd: Path):
    """Create a temporary 'artifacts' directory within the temp_cwd."""
    artifacts_dir = temp_cwd / "test_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


@pytest.fixture
def temp_configs_root_dir(temp_cwd: Path):
    """Create a temporary root for config files if they are outside CWD."""
    configs_root = temp_cwd / "project_configs"
    configs_root.mkdir(parents=True, exist_ok=True)
    return configs_root


# --- Fixture for Hydra-Zen Store ---
@pytest.fixture
def zen_store():
    """Provides a clean Hydra-Zen store for each test."""
    store = hydra_zen.ZenStore()
    # It's good practice to clear the global store if tests might affect it,
    # though using a local instance like this is better.
    # hydra_zen.store.clear() # If you were using the global hydra_zen.store directly
    return store


# --- Helper for creating dummy config content ---
def create_dummy_hydra_config_content(
    target_path: str,
    output_file: str = None,
    input_file: str = None,
    param_value: int = 1,
):
    content_parts = [f"_target_: {target_path}"]
    if output_file:
        content_parts.append(
            f"output_path: ${{outs:{output_file}}}"
        )  # Use outs for DVC output
    if input_file:
        content_parts.append(
            f"input_path: ${{deps:{input_file}}}"
        )  # Use deps for DVC dependency
    content_parts.append(f"some_param: {param_value}")
    return "\n".join(content_parts)


# --- Custom Project Directory Functions for Testing ---
def test_project_stage_dir_fn(temp_artifacts_dir: Path):
    def fn(stage: str, name: str) -> str:
        return str(temp_artifacts_dir / stage / name)

    return fn


def test_project_configs_dir_fn(temp_artifacts_dir: Path):
    def fn(stage: str) -> str:
        return str(temp_artifacts_dir / stage)

    return fn


@pytest.fixture(autouse=True)  # autouse=True will apply this to all tests by default
def hydra_global_state_cleanup():
    """
    Ensures Hydra's global state is clean before and after each test
    if it was initialized.
    """
    # Before the test:
    # Optional: Could clear here if a previous non-test interaction left it initialized,
    # but typically, tests initialize it themselves if needed.

    yield  # This is where the test runs

    # After the test:
    if hydra.core.global_hydra.GlobalHydra.instance().is_initialized():
        hydra.core.global_hydra.GlobalHydra.instance().clear()
