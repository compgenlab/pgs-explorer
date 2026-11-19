#!/usr/bin/env bash
# One Slurm array task = one batch of scores for one dataset. This job is the
# Nextflow head process; pgsc_calc submits its own Slurm jobs via nextflow/slurm.config.
# Submitted by bin/submit-dataset.sh, which sets RUN and DATASET.
#SBATCH --job-name=pgsatlas-pgsc
#SBATCH --cpus-per-task=1
#SBATCH --output=%x-%A_%a.log
source "$HPC_DIR/bin/common.sh"
load_dataset "$DATASET"

B="$(printf %04d "$SLURM_ARRAY_TASK_ID")"
BATCH="$RUN/batches/batch-$B"
OUT="$RUN/results/batch-$B"
WORK="$RUN/work/batch-$B"
SNAPNAME="$(basename "$RUN")"
DEST="$S3_BUCKET/runs/$DATASET/$SNAPNAME/batch-$B"

if s3 ls "$DEST/_SUCCESS" >/dev/null 2>&1; then
  echo "batch $B already done ($DEST/_SUCCESS)"; exit 0
fi
mkdir -p "$OUT" "$WORK"; cd "$RUN"

# --min_overlap 0: keep every score whatever its match rate; we filter by
# match rate when viewing, using the match summary pgsc_calc writes.
nextflow run pgscatalog/pgsc_calc -r "$PGSC_CALC_VERSION" \
  -profile "$NXF_PROFILE" -c "$NXF_CONFIG" \
  -work-dir "$WORK" -resume \
  --input "$RUN/samplesheet.csv" \
  --target_build "$TARGET_BUILD" \
  --scorefile "$BATCH/*.txt.gz" \
  --min_overlap 0 \
  --run_ancestry "$REF_PANEL" \
  --outdir "$OUT"

cp "$BATCH/files.txt" "$OUT/scorefiles.txt"
printf 'dataset=%s\nsnapshot=%s\nbatch=%s\npgsc_calc=%s\nref_panel=%s\nfinished=%s\n' \
  "$DATASET" "$SNAPNAME" "$B" "$PGSC_CALC_VERSION" "$(basename "$REF_PANEL")" "$(date -Is)" > "$OUT/run.txt"
s3 sync "$OUT" "$DEST" --only-show-errors
s3 cp "$OUT/run.txt" "$DEST/_SUCCESS" --only-show-errors
echo "batch $B uploaded to $DEST"
