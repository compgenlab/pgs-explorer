#!/usr/bin/env bash
# Split a Catalog snapshot into batches of BATCH_SIZE scoring files for one dataset.
#
#   bin/make-batches.sh <dataset> [snapshot-dir]
#   ONLY=PGS000001,PGS000002 RUN_NAME=2026-11-19-test bin/make-batches.sh <dataset>   # a test run
#
# Writes $ATLAS_ROOT/runs/<dataset>/<snapshot>/batches/batch-0000/ with symlinks
# to that batch's scoring files, and samplesheet.csv for the dataset.
source "$(dirname "$0")/common.sh"
load_dataset "$1"
SNAP="${2:-}"; [[ -n "$SNAP" ]] || SNAP="$(latest_catalog)"
[[ -d "$SNAP/files" ]] || { echo "no snapshot at $SNAP; run fetch-catalog.sh" >&2; exit 1; }
ONLY="${ONLY:-}"

RUN="$(run_dir "$SNAP")"
rm -rf "$RUN/batches"; mkdir -p "$RUN/batches"

# Samplesheet (pgsc_calc v2 columns), one row per chromosome.
{
  if [[ "$FORMAT" == "vcf" ]]; then echo "sampleset,path_prefix,chrom,format,vcf_genotype_field"
  else echo "sampleset,path_prefix,chrom,format"; fi
  for c in $CHROMS; do
    if [[ "$FORMAT" == "vcf" ]]; then
      p="${VCF_PATTERN//\{chrom\}/$c}"; p="${p%.vcf.gz}"
      echo "$DATASET,$p,$c,vcf,$VCF_FIELD"
    else
      p="${PFILE_PATTERN//\{chrom\}/$c}"
      echo "$DATASET,$p,$c,pfile"
    fi
  done
} > "$RUN/samplesheet.csv"

ls -1 "$SNAP/files" | grep '\.txt\.gz$' | sort > "$RUN/all-files.txt"
if [[ -n "$ONLY" ]]; then
  tr ',' '\n' <<<"$ONLY" | sed 's/$/_/' > "$RUN/only.txt"
  grep -F -f "$RUN/only.txt" "$RUN/all-files.txt" > "$RUN/all-files.txt.new" && mv "$RUN/all-files.txt.new" "$RUN/all-files.txt"
fi
split -d -a 4 -l "$BATCH_SIZE" "$RUN/all-files.txt" "$RUN/batches/list-"
n=0
for l in "$RUN"/batches/list-*; do
  b="$RUN/batches/batch-$(printf %04d "$n")"; mkdir -p "$b"
  while read -r f; do ln -sf "$SNAP/files/$f" "$b/$f"; done < "$l"
  mv "$l" "$b/files.txt"; n=$((n+1))
done
echo "$n" > "$RUN/batches/count"
echo "dataset $DATASET: $(wc -l < "$RUN/all-files.txt") scores in $n batches → $RUN"
