
import hydra
from hydra.core.config_store import ConfigStore
from hydra.experimental.callback import Callback
import logging

_log = logging.getLogger(__name__)


class LinkCwd(Callback):
    def on_job_start(self, *args, **kwargs):
        import os
        from hydra.utils import get_original_cwd
        _log.info(f"Linking cwd to {get_original_cwd()}")
        os.symlink(get_original_cwd(), 'cwd', target_is_directory=True)
        


