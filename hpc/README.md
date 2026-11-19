# Scoring every PGS Catalog score, by hand on the cluster

This is the first step of PGS Atlas: score every current PGS Catalog score on
every dataset with pgsc_calc, and put the results in S3 for ingest. These
scripts do it with plain Slurm. Later the Slurm delegate
(`pgsatlas slurm-delegate`) runs the same batch script from the queue, so
nothing here is thrown away.

## What you need

- On the cluster: Nextflow, Singularity or Apptainer, `plink2` (only for the
  optional pfile conversion), the AWS CLI with credentials for the bucket, and
  `jq` and `curl` on a node with internet access.
- The pgsc_calc ancestry reference panel, downloaded once:
  `pgsc_HGDP+1kGP_v1.tar.zst` (see the pgsc_calc docs). Compute nodes then need
  no network access, apart from S3.
- **pgsc_calc v2.3.0.** v2.x is required for `--run_ancestry`, which produces
  the ancestry-normalized scores (Z_norm1, Z_norm2). The v3 alphas don't
  support it yet.

## One-time setup

```bash
cd hpc
cp config.env.example config.env          # edit paths, Slurm partition, S3 bucket
cp datasets/1kg-30x.env.example datasets/1kg-30x.env
cp datasets/biobank-a.env.example datasets/biobank-a.env   # one file per dataset
```

`config.env` and `datasets/*.env` are site-specific and git-ignored.

Optional but recommended for large datasets: convert each dataset's VCFs to
plink2 pfiles once, so pgsc_calc doesn't re-import the VCFs in every batch.

```bash
sbatch --array=1-22 --export=ALL,HPC_DIR=$PWD,DATASET=biobank-a bin/vcf-to-pfile.sbatch
# then set FORMAT=pfile in datasets/biobank-a.env
```

## 1. Fetch the Catalog (login or transfer node)

```bash
bin/fetch-catalog.sh GRCh38
```

This pages through the PGS Catalog REST API (`/rest/score/all`) and downloads
each score's harmonized file
(`<PGS_ID>_hmPOS_GRCh38.txt.gz`) into `$CATALOG_DIR/<date>/files/`. It also
writes `scores.tsv`, `manifest.sha256` and `failed.txt`. It can be re-run:
files already present are skipped. That dated snapshot is the "Catalog
version" recorded with every result.

## 2. Test on 1000 Genomes with a few scores

The test uses its own run name, so it never marks batches of the full run as
done.

```bash
ONLY=PGS000001,PGS000004,PGS000018 RUN_NAME=$(date +%F)-test bin/make-batches.sh 1kg-30x
RUN_NAME=$(date +%F)-test bin/submit-dataset.sh 1kg-30x
```

Check before going further:

- the run finished, and `results/batch-0000/` has the aggregated scores, the
  match summary and the ancestry outputs;
- passing harmonized Catalog files with `--scorefile` works as expected with
  your genome build;
- `--min_overlap 0` keeps low-match scores, and the match summary records their
  rates;
- how long the run took and how much memory it used, to set `BATCH_SIZE`.

## 3. Run everything

```bash
bin/make-batches.sh 1kg-30x        # BATCH_SIZE scores per batch
bin/submit-dataset.sh 1kg-30x      # Slurm array, MAX_PARALLEL batches at a time
bin/status.sh 1kg-30x

bin/make-batches.sh biobank-a && bin/submit-dataset.sh biobank-a
# … and the other biobank datasets
```

Each array task is a Nextflow head job for one batch. pgsc_calc submits its
own Slurm jobs through `nextflow/slurm.config`. When a batch finishes, its
results go to `$S3_BUCKET/runs/<dataset>/<snapshot>/batch-NNNN/` with a
`_SUCCESS` marker. Re-submitting is safe: finished batches exit straight away,
and unfinished ones resume from Nextflow's work directory (`-resume`).

## Choices and things to watch

- **Score everything:** `--min_overlap 0` keeps every score whatever its
  variant match rate. Low-match scores are filtered when viewing, using the
  match summary, never at scoring time.
- **Zero-match scores:** a score with no matching variants at all may still
  stop a batch (pgsc_calc's `ZeroMatchesError`). If a batch fails that way,
  take the IDs from the log, drop those files from that batch directory, and
  re-submit just that batch: `bin/submit-dataset.sh <dataset> "" --array N-N`.
- **Ancestry is recomputed in every batch.** It's identical each time, so
  larger batches waste less. Raise `BATCH_SIZE` as far as the memory seen in
  the test run allows.
- **Comparability:** every batch in a run uses the same pgsc_calc version and
  reference panel (recorded in `run.txt`), so all scores in a dataset release
  are comparable. Changing either one means a new run name, a new release, and
  re-scoring every batch.
- **Refresh:** at least every 6 months, fetch a new Catalog snapshot and update
  `PGSC_CALC_VERSION` to the latest v2 release, then run steps 2 and 3 again.
  Each refresh becomes a new release of every dataset.

## 1000 Genomes 30×

These are the NYGC high-coverage phased panel files (3,202 samples, GRCh38),
one per chromosome:
`…/1000G_2504_high_coverage/working/20220422_3202_phased_SNV_INDEL_SV/1kGP_high_coverage_Illumina.chr{N}.filtered.SNV_INDEL_SV_phased_panel.vcf.gz`
on the 1000 Genomes FTP. Check the file names against the directory listing
when you download them, then point `VCF_PATTERN` at your copy. Use
`VCF_FIELD=GT`, since these are hard calls.
