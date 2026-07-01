#!/usr/bin/env bash
set -euo pipefail

RUNS="${RUNS:-100}"
DRY_RUNS="${DRY_RUNS:-}"
SPRINTS="${SPRINTS:-6}"
SCENARIOS="${SCENARIOS:-F G H I}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ROOT_DIR="outputs/validation_runs/${TIMESTAMP}"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

RUNS_EFFECTIVE="${RUNS}"
if [ -n "${DRY_RUNS}" ]; then
  RUNS_EFFECTIVE="${DRY_RUNS}"
fi

on_error() {
  local status="$1"
  local line="$2"
  echo "ERROR: validation failed at line ${line} with status ${status}" | tee -a "${LOG_DIR}/validation_error.log" >&2
  exit "${status}"
}
trap 'on_error "$?" "$LINENO"' ERR

log_env_error() {
  echo "ERROR: $*" | tee -a "${LOG_DIR}/environment_error.log" >&2
}

if ! command -v conda >/dev/null 2>&1; then
  log_env_error "conda command not found. Please ensure conda is installed and available in PATH."
  exit 1
fi

if ! CONDA_BASE="$(conda info --base 2>>"${LOG_DIR}/environment_error.log")"; then
  log_env_error "conda info --base failed. Please check conda initialization."
  exit 1
fi

CONDA_SH="${CONDA_BASE}/etc/profile.d/conda.sh"
if [ ! -f "${CONDA_SH}" ]; then
  log_env_error "conda activation script not found: ${CONDA_SH}"
  exit 1
fi

# shellcheck disable=SC1090
source "${CONDA_SH}"
if ! conda activate abm_env 2>>"${LOG_DIR}/environment_error.log"; then
  log_env_error "failed to activate conda environment abm_env. Please check conda initialization and that abm_env exists."
  exit 1
fi

{
  echo "Python executable: $(which python)"
  echo "Python version: $(python --version 2>&1)"
  echo "Conda environment: ${CONDA_DEFAULT_ENV:-unknown}"
  echo "Project directory: ${PROJECT_DIR}"
  echo "RUNS: ${RUNS}"
  echo "DRY_RUNS: ${DRY_RUNS:-not_set}"
  echo "RUNS_EFFECTIVE: ${RUNS_EFFECTIVE}"
  echo "SPRINTS: ${SPRINTS}"
  echo "SCENARIOS: ${SCENARIOS}"
  echo "Calibration rerun guide: RUNS=30 SCENARIOS=\"F G H I\" ./run_validation_experiments.sh"
} | tee "${LOG_DIR}/environment.log"

if [ "${CONDA_DEFAULT_ENV:-}" != "abm_env" ]; then
  log_env_error "expected conda env abm_env but got ${CONDA_DEFAULT_ENV:-unknown}"
  exit 1
fi

REQUIRED_FILES=(
  "experiment_runner.py"
  "run_final_experiments.py"
  "model.py"
  "agents.py"
  "tasks.py"
  "sampling.py"
  "simulate.py"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "${file}" ]; then
    log_env_error "required file not found: ${file}"
    exit 1
  fi
done

GIT_COMMIT="not_available"
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo not_available)"
fi

seed_start_for() {
  case "$1" in
    A) echo "1000" ;;
    B) echo "2000" ;;
    C) echo "3000" ;;
    D) echo "4000" ;;
    E) echo "5000" ;;
    F) echo "10000" ;;
    G) echo "20000" ;;
    H) echo "30000" ;;
    I) echo "40000" ;;
    *)
      echo "ERROR: Unsupported scenario: $1" | tee -a "${LOG_DIR}/environment_error.log" >&2
      return 1
      ;;
  esac
}

run_scenario() {
  local scenario="$1"
  local seed_start="$2"
  local out_dir="${ROOT_DIR}/scenario_${scenario}"
  local log_file="${LOG_DIR}/scenario_${scenario}.log"

  mkdir -p "${out_dir}"

  {
    echo "Running scenario ${scenario}"
    echo "RUNS=${RUNS_EFFECTIVE}"
    echo "SPRINTS=${SPRINTS}"
    echo "SEED_START=${seed_start}"
    echo "OUTPUT_DIR=${out_dir}"
  } | tee "${log_file}"

  if ! python experiment_runner.py \
    --scenario "${scenario}" \
    --runs "${RUNS_EFFECTIVE}" \
    --sprints "${SPRINTS}" \
    --seed-start "${seed_start}" \
    --output-dir "${out_dir}" \
    >> "${log_file}" 2>&1; then
    echo "ERROR: Scenario ${scenario} failed. See ${log_file}" | tee -a "${log_file}" >&2
    return 1
  fi

  echo "Completed scenario ${scenario}" | tee -a "${log_file}"

  if [ ! -f "${out_dir}/experiment_results.csv" ]; then
    echo "ERROR: Missing ${out_dir}/experiment_results.csv" | tee -a "${log_file}" >&2
    return 1
  fi
  if [ ! -f "${out_dir}/experiment_summary.csv" ]; then
    echo "ERROR: Missing ${out_dir}/experiment_summary.csv" | tee -a "${log_file}" >&2
    return 1
  fi

  local csv_count
  csv_count="$(find "${out_dir}" -maxdepth 1 -name "*.csv" | wc -l | tr -d " ")"
  if [ "${csv_count}" = "0" ]; then
    echo "ERROR: No CSV files generated for scenario ${scenario}" | tee -a "${log_file}" >&2
    return 1
  fi
}

for scenario in ${SCENARIOS}; do
  seed_start="$(seed_start_for "${scenario}")"
  run_scenario "${scenario}" "${seed_start}"
done

export VALIDATION_TIMESTAMP="${TIMESTAMP}"
export VALIDATION_ROOT_DIR="${ROOT_DIR}"
export VALIDATION_LOG_DIR="${LOG_DIR}"
export VALIDATION_RUNS="${RUNS}"
export VALIDATION_DRY_RUNS="${DRY_RUNS}"
export VALIDATION_RUNS_EFFECTIVE="${RUNS_EFFECTIVE}"
export VALIDATION_SPRINTS="${SPRINTS}"
export VALIDATION_SCENARIOS="${SCENARIOS}"
export VALIDATION_CONDA_ENV="${CONDA_DEFAULT_ENV:-unknown}"
export VALIDATION_PYTHON_EXECUTABLE="$(which python)"
export VALIDATION_PYTHON_VERSION="$(python --version 2>&1)"
export VALIDATION_GIT_COMMIT="${GIT_COMMIT}"

python - <<'PY'
import csv
import json
import os
from pathlib import Path

root = Path(os.environ["VALIDATION_ROOT_DIR"])
log_dir = Path(os.environ["VALIDATION_LOG_DIR"])
inventory_path = root / "file_inventory.csv"
manifest_path = root / "manifest.json"
scenarios = os.environ["VALIDATION_SCENARIOS"].split()
seed_starts = {
    "A": 1000,
    "B": 2000,
    "C": 3000,
    "D": 4000,
    "E": 5000,
    "F": 10000,
    "G": 20000,
    "H": 30000,
    "I": 40000,
}


def csv_row_count(path: Path) -> int:
    try:
        with path.open(newline="", encoding="utf-8") as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)
    except UnicodeDecodeError:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)


scenario_outputs = {}
for scenario in scenarios:
    scenario_dir = root / f"scenario_{scenario}"
    csv_files = sorted(scenario_dir.glob("*.csv"))
    scenario_outputs[scenario] = {
        "directory": str(scenario_dir),
        "csv_files": [
            {
                "path": str(path),
                "filename": path.name,
                "bytes": path.stat().st_size,
                "rows": csv_row_count(path),
            }
            for path in csv_files
        ],
        "log_file": str(log_dir / f"scenario_{scenario}.log"),
        "seed_start": seed_starts.get(scenario),
    }

manifest = {
    "timestamp": os.environ["VALIDATION_TIMESTAMP"],
    "root_dir": str(root),
    "runs": int(os.environ["VALIDATION_RUNS"]),
    "dry_runs": os.environ["VALIDATION_DRY_RUNS"] or None,
    "runs_effective": int(os.environ["VALIDATION_RUNS_EFFECTIVE"]),
    "sprints": int(os.environ["VALIDATION_SPRINTS"]),
    "scenarios": scenarios,
    "conda_env": os.environ["VALIDATION_CONDA_ENV"],
    "python_executable": os.environ["VALIDATION_PYTHON_EXECUTABLE"],
    "python_version": os.environ["VALIDATION_PYTHON_VERSION"],
    "git_commit": os.environ["VALIDATION_GIT_COMMIT"],
    "seed_starts": {scenario: seed_starts.get(scenario) for scenario in scenarios},
    "scenario_outputs": scenario_outputs,
    "file_inventory": str(inventory_path),
    "logs_dir": str(log_dir),
}
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def write_inventory():
    files = sorted(path for path in root.rglob("*") if path.is_file())
    with inventory_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "filename", "bytes", "rows"])
        writer.writeheader()
        for path in files:
            rows = csv_row_count(path) if path.suffix == ".csv" else ""
            writer.writerow({
                "path": str(path),
                "filename": path.name,
                "bytes": path.stat().st_size,
                "rows": rows,
            })


write_inventory()
write_inventory()
PY

ZIP_PATH="${ROOT_DIR}.zip"
python - <<'PY'
import os
import shutil

root = os.environ["VALIDATION_ROOT_DIR"]
zip_path = shutil.make_archive(root, "zip", root_dir=root)
print(f"Created zip: {zip_path}")
PY

echo "DONE"
echo "Result root: ${ROOT_DIR}"
echo "Zip file: ${ZIP_PATH}"
echo "Inventory: ${ROOT_DIR}/file_inventory.csv"
echo "Manifest: ${ROOT_DIR}/manifest.json"
echo "Logs: ${LOG_DIR}"
