#!/usr/bin/env bash
set -euo pipefail

RUNS=100
SPRINTS=6
RUN_LABEL="calibrated"
SCENARIOS=("F" "G" "H" "I")

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)_${RUN_LABEL}"
ROOT_DIR="outputs/validation_runs/${TIMESTAMP}"
LOGS_DIR="${ROOT_DIR}/logs"
MANIFEST_PATH="${ROOT_DIR}/manifest.json"
INVENTORY_PATH="${ROOT_DIR}/file_inventory.csv"
COMPLETION_PATH="${ROOT_DIR}/completion_status.json"
ZIP_PATH="outputs/validation_runs/${TIMESTAMP}.zip"
SMOKE_DIR="outputs/_smoke_calibrated_F"
SMOKE_LOG="${LOGS_DIR}/smoke_F.log"
ENV_LOG="${LOGS_DIR}/environment.log"

mkdir -p "${LOGS_DIR}"

COMPLETED_SCENARIOS=()
FAILED_SCENARIOS=()
SUCCESS="true"

write_completion_status() {
  local success_value="$1"
  export COMPLETION_SUCCESS="${success_value}"
  export COMPLETED_SCENARIOS_TEXT="${COMPLETED_SCENARIOS[*]:-}"
  export FAILED_SCENARIOS_TEXT="${FAILED_SCENARIOS[*]:-}"
  export VALIDATION_ROOT_DIR="${ROOT_DIR}"
  export VALIDATION_LOGS_DIR="${LOGS_DIR}"
  export VALIDATION_ZIP_PATH="${ZIP_PATH}"
  export VALIDATION_COMPLETION_PATH="${COMPLETION_PATH}"
  python - <<'PY'
import csv
import json
import os
from pathlib import Path

root = Path(os.environ["VALIDATION_ROOT_DIR"])
logs_dir = Path(os.environ["VALIDATION_LOGS_DIR"])
zip_path = os.environ["VALIDATION_ZIP_PATH"]
completion_path = Path(os.environ["VALIDATION_COMPLETION_PATH"])
completed = [item for item in os.environ.get("COMPLETED_SCENARIOS_TEXT", "").split() if item]
failed = [item for item in os.environ.get("FAILED_SCENARIOS_TEXT", "").split() if item]

scenario_csv_files = {}
scenario_row_counts = {}
for scenario_dir in sorted(root.glob("scenario_*")):
    scenario = scenario_dir.name.replace("scenario_", "")
    scenario_csv_files[scenario] = []
    scenario_row_counts[scenario] = {}
    for csv_path in sorted(scenario_dir.glob("*.csv")):
        scenario_csv_files[scenario].append(str(csv_path))
        try:
            with csv_path.open(newline="", encoding="utf-8") as f:
                rows = max(0, sum(1 for _ in csv.reader(f)) - 1)
        except UnicodeDecodeError:
            with csv_path.open(newline="", encoding="utf-8-sig") as f:
                rows = max(0, sum(1 for _ in csv.reader(f)) - 1)
        scenario_row_counts[scenario][csv_path.name] = rows

payload = {
    "success": os.environ["COMPLETION_SUCCESS"].lower() == "true",
    "completed_scenarios": completed,
    "failed_scenarios": failed,
    "scenario_csv_files": scenario_csv_files,
    "scenario_row_counts": scenario_row_counts,
    "logs_dir": str(logs_dir),
    "root_dir": str(root),
    "zip_path": zip_path,
}
completion_path.parent.mkdir(parents=True, exist_ok=True)
completion_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
PY
}

on_error() {
  local status="$1"
  local line="$2"
  SUCCESS="false"
  echo "ERROR: calibrated validation failed at line ${line} with status ${status}" >> "${LOGS_DIR}/error.log"
  write_completion_status "false" || true
  exit "${status}"
}
trap 'on_error "$?" "$LINENO"' ERR

seed_start_for() {
  case "$1" in
    F) echo "51000" ;;
    G) echo "52000" ;;
    H) echo "53000" ;;
    I) echo "54000" ;;
    *)
      echo "ERROR: unsupported scenario: $1" >> "${LOGS_DIR}/environment_error.log"
      return 1
      ;;
  esac
}

if ! command -v conda >/dev/null 2>&1; then
  echo "ERROR: conda command not found." >> "${LOGS_DIR}/environment_error.log"
  exit 1
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate abm_env

{
  echo "CONDA_DEFAULT_ENV=${CONDA_DEFAULT_ENV:-}"
  echo "python=$(which python)"
  echo "python_version=$(python --version 2>&1)"
} > "${ENV_LOG}"

if [ "${CONDA_DEFAULT_ENV:-}" != "abm_env" ]; then
  echo "ERROR: expected CONDA_DEFAULT_ENV=abm_env, got ${CONDA_DEFAULT_ENV:-unknown}" >> "${LOGS_DIR}/environment_error.log"
  exit 1
fi

python -c "import mesa" >> "${ENV_LOG}" 2>&1

REQUIRED_FILES=(
  "experiment_runner.py"
  "model.py"
  "agents.py"
  "tasks.py"
  "sampling.py"
  "simulate.py"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "${file}" ]; then
    echo "ERROR: required file not found: ${file}" >> "${LOGS_DIR}/environment_error.log"
    exit 1
  fi
done

GIT_COMMIT="not_available"
GIT_STATUS_SHORT="not_available"
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo not_available)"
  GIT_STATUS_SHORT="$(git status --short 2>/dev/null || echo not_available)"
fi

export VALIDATION_TIMESTAMP="${TIMESTAMP}"
export VALIDATION_RUN_LABEL="${RUN_LABEL}"
export VALIDATION_ROOT_DIR="${ROOT_DIR}"
export VALIDATION_RUNS="${RUNS}"
export VALIDATION_SPRINTS="${SPRINTS}"
export VALIDATION_SCENARIOS="${SCENARIOS[*]}"
export VALIDATION_SEED_STARTS_JSON="{\"F\":51000,\"G\":52000,\"H\":53000,\"I\":54000}"
export VALIDATION_CONDA_ENV="${CONDA_DEFAULT_ENV:-unknown}"
export VALIDATION_PYTHON_EXECUTABLE="$(which python)"
export VALIDATION_PYTHON_VERSION="$(python --version 2>&1)"
export VALIDATION_GIT_COMMIT="${GIT_COMMIT}"
export VALIDATION_GIT_STATUS_SHORT="${GIT_STATUS_SHORT}"
export VALIDATION_MANIFEST_PATH="${MANIFEST_PATH}"

python - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "timestamp": os.environ["VALIDATION_TIMESTAMP"],
    "run_label": os.environ["VALIDATION_RUN_LABEL"],
    "root_dir": os.environ["VALIDATION_ROOT_DIR"],
    "runs": int(os.environ["VALIDATION_RUNS"]),
    "sprints": int(os.environ["VALIDATION_SPRINTS"]),
    "scenarios": os.environ["VALIDATION_SCENARIOS"].split(),
    "seed_starts": json.loads(os.environ["VALIDATION_SEED_STARTS_JSON"]),
    "conda_env": os.environ["VALIDATION_CONDA_ENV"],
    "python_executable": os.environ["VALIDATION_PYTHON_EXECUTABLE"],
    "python_version": os.environ["VALIDATION_PYTHON_VERSION"],
    "git_commit": os.environ["VALIDATION_GIT_COMMIT"],
    "git_status_short": os.environ["VALIDATION_GIT_STATUS_SHORT"],
    "note": "Post-calibration 100-run validation for scenarios F/G/H/I. No interpretation generated.",
}
path = Path(os.environ["VALIDATION_MANIFEST_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
PY

rm -rf "${SMOKE_DIR}"
if ! python experiment_runner.py \
  --scenario F \
  --runs 1 \
  --sprints 1 \
  --seed-start 50999 \
  --output-dir "${SMOKE_DIR}" \
  > "${SMOKE_LOG}" 2>&1; then
  SUCCESS="false"
  FAILED_SCENARIOS+=("smoke_F")
  echo "ERROR: smoke test failed. Full validation was not started." >> "${LOGS_DIR}/error.log"
  write_completion_status "false"
  exit 1
fi

run_scenario() {
  local scenario="$1"
  local seed_start="$2"
  local out_dir="${ROOT_DIR}/scenario_${scenario}"
  local log_file="${LOGS_DIR}/scenario_${scenario}.log"
  mkdir -p "${out_dir}"

  if ! python experiment_runner.py \
    --scenario "${scenario}" \
    --runs "${RUNS}" \
    --sprints "${SPRINTS}" \
    --seed-start "${seed_start}" \
    --output-dir "${out_dir}" \
    > "${log_file}" 2>&1; then
    SUCCESS="false"
    FAILED_SCENARIOS+=("${scenario}")
    echo "ERROR: Scenario ${scenario} failed." >> "${log_file}"
    return
  fi

  shopt -s nullglob
  local csv_files=("${out_dir}"/*.csv)
  shopt -u nullglob
  if [ "${#csv_files[@]}" -eq 0 ]; then
    SUCCESS="false"
    FAILED_SCENARIOS+=("${scenario}")
    echo "ERROR: No CSV files generated for scenario ${scenario}." >> "${log_file}"
    return
  fi
  if [ ! -f "${out_dir}/experiment_results.csv" ]; then
    echo "WARNING: Missing experiment_results.csv for scenario ${scenario}." >> "${log_file}"
  fi
  if [ ! -f "${out_dir}/experiment_summary.csv" ]; then
    echo "WARNING: Missing experiment_summary.csv for scenario ${scenario}." >> "${log_file}"
  fi
  COMPLETED_SCENARIOS+=("${scenario}")
}

for scenario in "${SCENARIOS[@]}"; do
  run_scenario "${scenario}" "$(seed_start_for "${scenario}")"
done

export VALIDATION_INVENTORY_PATH="${INVENTORY_PATH}"
python - <<'PY'
import csv
import os
from pathlib import Path

root = Path(os.environ["VALIDATION_ROOT_DIR"])
inventory_path = Path(os.environ["VALIDATION_INVENTORY_PATH"])

def row_count(path: Path) -> int:
    try:
        with path.open(newline="", encoding="utf-8") as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)
    except UnicodeDecodeError:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)

rows = []
for path in sorted(root.rglob("*.csv")):
    rows.append({
        "path": str(path),
        "filename": path.name,
        "bytes": path.stat().st_size,
        "rows": row_count(path),
    })

inventory_path.parent.mkdir(parents=True, exist_ok=True)
with inventory_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["path", "filename", "bytes", "rows"])
    writer.writeheader()
    writer.writerows(rows)
PY

write_completion_status "${SUCCESS}"

(
  cd "$(dirname "${ROOT_DIR}")"
  zip -qr "$(basename "${ZIP_PATH}")" "$(basename "${ROOT_DIR}")"
)

write_completion_status "${SUCCESS}"

python - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["VALIDATION_ROOT_DIR"])
completion_path = root / "completion_status.json"
inventory_path = root / "file_inventory.csv"
payload = json.loads(completion_path.read_text(encoding="utf-8"))

print("DONE")
print(f"Result root: {root}")
print(f"Zip file: {payload['zip_path']}")
print(f"Inventory path: {inventory_path}")
print(f"Completion status path: {completion_path}")
print("Scenario CSV files:")
for scenario in ["F", "G", "H", "I"]:
    files = payload.get("scenario_csv_files", {}).get(scenario, [])
    print(f"  {scenario}:")
    for path in files:
        print(f"    {path}")
print("Scenario row counts:")
for scenario in ["F", "G", "H", "I"]:
    counts = payload.get("scenario_row_counts", {}).get(scenario, {})
    print(f"  {scenario}:")
    for filename, rows in counts.items():
        print(f"    {filename}: {rows}")
print("Log files:")
for path in sorted((root / "logs").glob("*.log")):
    print(f"  {path}")
PY
