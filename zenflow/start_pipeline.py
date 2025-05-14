from pathlib import Path

import hydra_zen
import mlflow


def start_pipeline(run_name, project_name, dvc_root):
    mlflow.set_experiment(project_name)
    with mlflow.start_run(run_name=run_name):
        Path(".pipeline_id").write_text(mlflow.active_run().info.run_id)
        mlflow.log_artifact(Path(dvc_root) / "dvc.yaml")


if __name__ == "__main__":
    hydra_zen.store(start_pipeline)
    hydra_zen.store.add_to_hydra_store()
    hydra_zen.zen(start_pipeline).hydra_main(config_name="start_pipeline", version_base="1.3")
