#!/usr/bin/env bash
# Show which batches of a dataset have finished (by the _SUCCESS marker in S3).
#   bin/status.sh <dataset> [snapshot-dir]
source "$(dirname "$0")/common.sh"
load_dataset "$1"
SNAP="${2:-}"; [[ -n "$SNAP" ]] || SNAP="$(latest_catalog)"
RUN="$(run_dir "$SNAP")"; NAME="$(basename "$RUN")"
n="$(cat "$RUN/batches/count")"; done=0
for ((i=0; i<n; i++)); do
  B="$(printf %04d "$i")"
  if s3 ls "$S3_BUCKET/runs/$DATASET/$NAME/batch-$B/_SUCCESS" >/dev/null 2>&1; then done=$((done+1)); else echo "pending: batch-$B"; fi
done
echo "$DATASET $NAME: $done / $n batches done"
