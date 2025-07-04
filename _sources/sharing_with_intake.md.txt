# Sharing Data & Models: DVC Versioning with Intake Catalogs (using fsspec)

Once you've used ZenDag and DVC to produce versioned datasets and models, how do you easily share and consume them? [Intake](https://intake.readthedocs.io/) is a lightweight Python library for finding, investigating, loading, and disseminating data. By leveraging `fsspec` and its DVC filesystem implementation (`dvcfs`), Intake provides a modern and flexible way to access DVC-versioned assets.

## Recap: DVC for Versioning Artifacts

As covered previously, ZenDag and DVC work together to version your data. When a stage produces an output like `artifacts/transform/default_transform/output.csv`, DVC creates a `.dvc` file tracking its metadata and content hash.

## Step 1: Push DVC Data to a Remote

To share data, it must be in a DVC remote storage (S3, GCS, SSH, etc.).

1.  **Add a remote** (if not done already):
    ```bash
    # Example for a local directory remote (for testing)
    mkdir -p /tmp/my_dvc_remote 
    dvc remote add -d mylocalremote /tmp/my_dvc_remote
    ```
2.  **Push data to the remote:**
    ```bash
    dvc push -r mylocalremote
    ```

## Step 2: Tag a Specific Version in Git

Git tags mark specific, stable versions of your DVC metadata (`.dvc` files and `dvc.lock`).

1.  Commit all relevant `.dvc` files and `dvc.lock`.
2.  Create and push a tag:
    ```bash
    git tag v1.0.0-data -m "Stable processed dataset version 1.0.0 from quickstart"
    git push origin v1.0.0-data
    ```

## Step 3: Install Intake and fsspec DVC support

In the environment where you'll *consume* the data, ensure you have:
```bash
pip install intake pandas # For CSV reading
# For DVC fsspec support, DVC needs to be installed with fsspec extras, or dvcfs separately
pip install "dvc[fsspec]" # Or ensure dvcfs is available if dvc is already installed
# If you plan to read other formats, install relevant intake plugins, e.g.:
# pip install intake-xarray intake-parquet
```

## Step 4: Creating an Intake Catalog (`catalog.yaml`) with fsspec

An Intake catalog (YAML file) describes your data sources. We'll use the `fsspec` `dvc://` URL scheme.

Create `catalog.yaml`:
```yaml
# catalog.yaml (using fsspec dvc:// syntax)
sources:
  processed_dataset_v1_fsspec:
    driver: csv # Intake driver for CSV files (uses pandas by default)
    description: "Version 1.0.0 of the processed dataset (fsspec dvc access)."
    args:
      # urlpath uses the dvc:// fsspec protocol.
      # The part after dvc:// (e.g., your_username/your_project/) is often conventional
      # as target_options.url primarily defines the Git repo.
      urlpath: "dvc://your_username_placeholder/your_zendag_project_placeholder/artifacts/transform/default_transform/data/processed/output.csv" # !!! REPLACE owner/repo part !!!
      storage_options:
        # target_options specifies the Git repository details for dvcfs
        target_options:
          url: "https://github.com/your_username_placeholder/your_zendag_project_placeholder.git" # !!! REPLACE THIS !!!
        # rev is the Git revision (tag, branch, or commit hash)
        rev: "v1.0.0-data"
        # remote: "mylocalremote" # Optional: DVC remote if not default/auto-discoverable
      # Arguments for the 'csv' driver (passed to pandas.read_csv)
      csv_kwargs: 
        dtype: {"id": "int", "value": "float", "scaled_value": "float"}

  # Example for a NetCDF file, assuming intake-xarray is installed
  # weather_model_output_v2_fsspec:
  #   driver: netcdf 
  #   description: "Weather model output v2 (NetCDF via fsspec dvc)."
  #   args:
  #     urlpath: "dvc://your_username_placeholder/your_zendag_project_placeholder/data/models/weather_v2.nc" # !!! REPLACE !!!
  #     chunks: {} # Argument for xarray.open_dataset
  #     storage_options:
  #       target_options:
  #         url: "https://github.com/your_username_placeholder/your_zendag_project_placeholder.git" # !!! REPLACE !!!
  #       rev: "weather-model-v2-tag"
```
**Important:**
*   Replace placeholders like `your_username_placeholder/your_zendag_project_placeholder` with your actual Git repository owner and name.
*   The `path` part of the `urlpath` must be the exact path to the data file as tracked by DVC within that repository structure.
*   Ensure the Git `rev` (e.g., tag `v1.0.0-data`) exists in your Git repository.

## Step 5: Using the Intake Catalog (fsspec version)

In any Python script or Jupyter Notebook:

```python
import intake
import pandas as pd # For type hint and checking
import os

# --- Create a dummy catalog.yaml for this notebook execution ---
# In a real scenario, this file would exist independently.
# !!! REPLACE with your actual Git repo URL and path for this to work beyond this notebook !!!
DUMMY_GIT_OWNER = "your_username_placeholder"
DUMMY_GIT_REPO_NAME = "your_zendag_project_placeholder"
# Construct a file:// URL if your repo is local for testing, otherwise use https://
# For this example, we'll assume a local path could be used for placeholder.
# A real remote test would require cloning this ZenDag repo and pushing it to your own GitHub.
# For simplicity in a self-contained notebook, we'll mock the access or it will fail if placeholders aren't replaced.
DUMMY_GIT_REPO_URL_FOR_FSSPEC = f"https_IS_A_PLACEHOLDER_REPLACE_ME_github.com/{DUMMY_GIT_OWNER}/{DUMMY_GIT_REPO_NAME}.git"
# If testing locally against a checked-out version of the project (that has DVC setup):
# DUMMY_GIT_REPO_URL_FOR_FSSPEC = f"file://{os.path.abspath('.')}" # Points to current dir if it's the git repo root


if "PLACEHOLDER_REPLACE_ME" in DUMMY_GIT_REPO_URL_FOR_FSSPEC:
    print(f"WARNING: DUMMY_GIT_REPO_URL_FOR_FSSPEC ('{DUMMY_GIT_REPO_URL_FOR_FSSPEC}') is a placeholder.")
    print("Replace it with your actual Git repo URL and adjust paths for this example to fully work.")

catalog_fsspec_content = f"""
sources:
  processed_dataset_v1_fsspec:
    driver: csv 
    description: "Version 1.0.0 of the processed dataset (fsspec dvc access)."
    args:
      urlpath: "dvc://{DUMMY_GIT_OWNER}/{DUMMY_GIT_REPO_NAME}/artifacts/transform/default_transform/data/processed/output.csv"
      storage_options:
        target_options:
          url: "{DUMMY_GIT_REPO_URL_FOR_FSSPEC}"
        rev: "v1.0.0-data" # Ensure this tag exists in your repo, or use a valid commit/branch
      csv_kwargs: 
        dtype: {{"id": "int", "value": "float", "scaled_value": "float"}}
"""
with open("temp_fsspec_catalog.yaml", "w") as f:
    f.write(catalog_fsspec_content)
# --- End dummy catalog creation ---


# Ensure your temp_fsspec_catalog.yaml is in the current directory or provide its path
catalog_fsspec = None
try:
    catalog_fsspec = intake.open_catalog("temp_fsspec_catalog.yaml")
except Exception as e:
    print(f"Error opening fsspec catalog: {e}")
    print("This example may not fully run if the Git repo URL is a placeholder or the specified rev/path doesn't exist.")

if catalog_fsspec:
    print("Available sources in fsspec catalog:", list(catalog_fsspec))
    
    dataset_entry_name_fsspec = 'processed_dataset_v1_fsspec'
    if dataset_entry_name_fsspec in catalog_fsspec:
        dataset_entry_fsspec = catalog_fsspec[dataset_entry_name_fsspec]
        print(f"\nDataset entry '{dataset_entry_name_fsspec}' description:", dataset_entry_fsspec.description)
        
        print("Attempting to read data using fsspec dvc (this might take a moment for the first time if accessing a remote repo)...")
        try:
            df_fsspec: pd.DataFrame = dataset_entry_fsspec.read() # `read()` loads the data
            
            print("\nFirst 5 rows of the loaded DataFrame (via fsspec dvc):")
            print(df_fsspec.head())
            print(f"\nDataFrame shape: {df_fsspec.shape}")
        except Exception as e:
            print(f"\nERROR reading data source '{dataset_entry_name_fsspec}': {e}")
            print("This often happens if:")
            print(f"  - The Git repo URL ('{DUMMY_GIT_REPO_URL_FOR_FSSPEC}') is a placeholder, incorrect, or inaccessible.")
            print(f"  - The Git revision (tag/commit) 'v1.0.0-data' does not exist in that repo or doesn't contain the DVC metadata for the specified path.")
            print(f"  - The DVC remote (if needed) is not accessible or the data for the path has not been pushed to it.")
            print(f"  - 'dvc' CLI is not installed, or 'dvcfs' (required by fsspec's dvc:// protocol) is not available.")
            print(f"  - The 'driver: csv' needs pandas or an appropriate backend installed in your Python environment.")

    else:
        print(f"Data source '{dataset_entry_name_fsspec}' not found in catalog.")

# Clean up dummy catalog
if os.path.exists("temp_fsspec_catalog.yaml"):
    os.remove("temp_fsspec_catalog.yaml")
```

**What happens when you call `dataset_entry.read()` with this fsspec setup:**
1.  Intake identifies the `driver` (e.g., `csv`).
2.  It sees the `urlpath` starting with `dvc://`.
3.  It uses `fsspec` with the `dvcfs` implementation to open this URL.
4.  `dvcfs` uses the `storage_options` (like `target_options.url` for the Git repo and `rev` for the Git revision) to:
    *   Access the specified Git repository at the given revision (cloning/checking out to a temporary location if needed).
    *   Find the DVC metadata for the file path within the `urlpath`.
    *   Use DVC internally to make the actual data file available (pulling from a DVC remote if necessary).
    *   `dvcfs` then provides a file-like object to this data.
5.  Intake's chosen `driver` (e.g., the CSV driver) then reads from this file-like object, applying any specified `args` (like `csv_kwargs`).

## Benefits of the `fsspec` Approach

*   **Standardization:** Uses the widely adopted `fsspec` interface, making it compatible with many libraries.
*   **Flexibility:** You choose the Intake `driver` based on your data format (CSV, Parquet, NetCDF, Zarr, etc.), and `dvcfs` handles getting the DVC-versioned bytes to that driver.
*   **Ecosystem:** Leverages the strengths of both Intake (cataloging, unified API) and `fsspec` (versatile file system access).

This `fsspec`-based method is the modern and generally recommended way to use Intake with DVC-versioned data, offering greater flexibility and integration with the broader Python data ecosystem.