# Shared setup for hpc/bin scripts. Source, don't run.
set -euo pipefail
HPC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HPC_DIR
if [[ ! -f "$HPC_DIR/config.env" ]]; then
  echo "missing $HPC_DIR/config.env (copy config.env.example)" >&2; exit 1
fi
set -a; source "$HPC_DIR/config.env"; set +a

load_dataset() {
  local f="$HPC_DIR/datasets/$1.env"
  [[ -f "$f" ]] || { echo "unknown dataset: $1 (no $f)" >&2; exit 1; }
  set -a; source "$f"; set +a
  [[ "$DATASET" =~ ^[A-Za-z0-9-]+$ ]] || { echo "dataset slug must be letters, digits, hyphens" >&2; exit 1; }
}

s3() {
  if [[ -n "${S3_ENDPOINT:-}" ]]; then aws --endpoint-url "$S3_ENDPOINT" s3 "$@"; else aws s3 "$@"; fi
}

latest_catalog() {
  local d; d="$( (ls -1d "$CATALOG_DIR"/*/ 2>/dev/null || true) | sort | tail -n1 | sed 's:/$::')"
  [[ -n "$d" ]] || { echo "no Catalog snapshot in $CATALOG_DIR; run bin/fetch-catalog.sh" >&2; return 1; }
  echo "$d"
}

# Run directory for a dataset and snapshot. RUN_NAME overrides the name, so a
# test run (RUN_NAME=<date>-test) never collides with the full run's batches.
run_dir() { echo "$ATLAS_ROOT/runs/$DATASET/${RUN_NAME:-$(basename "$1")}"; }
