from hydra.experimental.callback import Callback
import logging
import os
from pathlib import Path

_log = logging.getLogger(__name__)

def get_original_root(targets=['pyproject.toml', '.git'], relative=True) -> Path:
    """
    Return the root directory of the project.
    Find the first parent directory that contains one of the targets passed as input.
    If relative is True, return the path relative to the current working directory (number of ..).
    """
    current_dir = Path.cwd().resolve()
    for parent in [current_dir] + list(current_dir.parents):
        for target in targets:
            if (parent / target).exists():
                if relative:
                    # If relative is True, determine the depth of the current directory relative to the parent
                    depth = len(current_dir.relative_to(parent).parts)
                    return Path(*(['..'] * depth))
                else:
                    return parent
    raise FileNotFoundError(f"None of the targets {targets} found in {current_dir} or its parents.")

class LinkProjectRoot(Callback):
    def on_job_start(self, *args, **kwargs):
        import os

        if  Path('projroot').exists():
            _log.info(f"Symlink exists doing nothing")
            return

        proj_root = get_original_root()

        _log.info(f"Linking projroot to {proj_root} wich resolves to {os.path.abspath(proj_root)}")
        os.symlink(proj_root, 'projroot', target_is_directory=True)
        



class BasicLogging(Callback):
    def on_job_start(self, *args, **kwargs):
        _log.info(f"Starting job with dir: {os.getcwd()}")

    def on_job_end(self, *args, **kwargs):
        _log.info(f"Ending job with dir: {os.getcwd()}")


