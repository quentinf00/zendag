# tests/test_config_utils.py

import pytest

from zendag.config_utils import deps_path, outs_path


def test_outs_path_simple():
    assert outs_path("model.pkl") == "${outs:./model.pkl}"


def test_deps_path_simple():
    assert deps_path("raw_data.csv") == "${deps:raw_data.csv,False}"


def test_deps_path_with_stage_and_name():
    # Dummy stage_dir_fn for testing this specific utility
    def dummy_stage_dir_fn(stage, name):
        return f"mock_artifacts/{stage}/{name}"

    expected = "${deps:mock_artifacts/prev_stage/config1/input.txt,True}"
    assert deps_path("input.txt", "prev_stage", "config1", stage_dir_fn=dummy_stage_dir_fn) == expected


def test_deps_path_missing_input_name():
    with pytest.raises(ValueError, match="input_name must be specified"):
        deps_path("input.txt", input_stage="prev_stage", stage_dir_fn=lambda s, n: "")
