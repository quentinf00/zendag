import hydra


@hydra.main(version_base="1.3")
def run(cfg):
    return hydra.utils.call(cfg)


if __name__ == "__main__":
    run()
