import logging
from typing import Optional
from .core import default_stage_dir_fn

_log = logging.getLogger(__name__)


# Keep these simple functions that just format strings
# The "magic" happens via the resolver registration in configure_pipeline
def outs_path(s: str, root_dir: bool = False) -> str:
    """Returns the formatted string for DVC outputs."""
    base_dir = str(s) if root_dir else "${hydra:runtime.output_dir}" + "/" + str(s)
    return "${outs:" + base_dir + "}"


def deps_path(
    s: str,
    input_stage: Optional[str] = None,
    input_name: Optional[str] = None,
    stage_dir_fn=default_stage_dir_fn,
) -> str:
    """
    Returns the formatted string for DVC dependencies.

    Requires stage_dir_fn to be passed or resolved if input_stage/input_name are used.
    Example: stage_dir_fn = lambda stage, name: f"artifacts/{stage}/{name}"
    """
    if input_stage is not None:
        if input_name is None:
            raise ValueError("input_name must be specified if input_stage is provided.")
        if stage_dir_fn is None:
            raise ValueError("stage_dir_fn must be provided if input_stage/input_name are used.")
        base_dir = stage_dir_fn(input_stage, input_name) + "/"
    else:
        base_dir = ""
    return "${deps:" + base_dir + str(s) + "}"
