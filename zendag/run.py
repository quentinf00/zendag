import hydra
from omegaconf import OmegaConf

OmegaConf.register_new_resolver("outs", lambda p: p)
OmegaConf.register_new_resolver("deps", lambda p: p)


@hydra.main(version_base="1.3")
def run(cfg):
    return hydra.utils.call(cfg)


if __name__ == "__main__":
    run()
