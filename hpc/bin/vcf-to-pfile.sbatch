#!/usr/bin/env bash
# Optional, once per dataset: convert VCFs to plink2 pfiles so pgsc_calc doesn't
# re-import the VCFs in every batch. Then set FORMAT=pfile in the dataset file.
#
#   sbatch --array=1-22 --export=ALL,HPC_DIR=$PWD,DATASET=biobank-a bin/vcf-to-pfile.sbatch
#SBATCH --job-name=pgsatlas-pfile
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
source "$HPC_DIR/bin/common.sh"
load_dataset "$DATASET"
c="$SLURM_ARRAY_TASK_ID"
in="${VCF_PATTERN//\{chrom\}/$c}"
out="${PFILE_PATTERN//\{chrom\}/$c}"
mkdir -p "$(dirname "$out")"
if [[ "$VCF_FIELD" == "DS" ]]; then field="dosage=DS"; else field=""; fi
plink2 --threads "$SLURM_CPUS_PER_TASK" --vcf "$in" $field \
  --set-all-var-ids '@:#:$r:$a' --new-id-max-allele-len 1000 truncate \
  --make-pgen --out "$out"
