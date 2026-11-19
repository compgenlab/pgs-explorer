#!/usr/bin/env bash
# Submit every batch for one dataset as a Slurm array (at most MAX_PARALLEL at once).
#
#   bin/submit-dataset.sh <dataset> [snapshot-dir] [--array 0-3]
#
# Batches already marked _SUCCESS in S3 exit immediately, so re-submitting is safe.
source "$(dirname "$0")/common.sh"
load_dataset "$1"
SNAP="${2:-}"; [[ -n "$SNAP" ]] || SNAP="$(latest_catalog)"
RUN="$(run_dir "$SNAP")"
[[ -f "$RUN/batches/count" ]] || { echo "no batches; run make-batches.sh $DATASET first" >&2; exit 1; }
n="$(cat "$RUN/batches/count")"
ARRAY="0-$((n-1))"; [[ "${3:-}" == "--array" ]] && ARRAY="$4"
mkdir -p "$RUN/logs"
sbatch --array="${ARRAY}%${MAX_PARALLEL}" \
  --partition="$SLURM_PARTITION" ${SLURM_ACCOUNT:+--account="$SLURM_ACCOUNT"} \
  --time="$HEAD_TIME" --mem="$HEAD_MEM" \
  --chdir="$RUN/logs" \
  --export=ALL,HPC_DIR="$HPC_DIR",RUN="$RUN",DATASET="$DATASET" \
  "$HPC_DIR/bin/pgsc_calc-batch.sbatch"
