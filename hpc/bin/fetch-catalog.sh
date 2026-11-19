#!/usr/bin/env bash
# Download every PGS Catalog score's harmonized GRCh38 (or GRCh37) scoring file.
# Run on a node with internet access (login or transfer node), not a compute node.
#
#   bin/fetch-catalog.sh [GRCh38|GRCh37]
#
# Writes $CATALOG_DIR/<YYYY-MM-DD>/:
#   scores.tsv        pgs_id, url, license (from the REST API)
#   files/            <PGS_ID>_hmPOS_<build>.txt.gz
#   manifest.sha256   checksums of everything in files/
#   failed.txt        IDs whose download failed (re-run to retry)
source "$(dirname "$0")/common.sh"
BUILD="${1:-GRCh38}"
API="https://www.pgscatalog.org/rest"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

SNAP="$CATALOG_DIR/$(date +%Y-%m-%d)"
mkdir -p "$SNAP/files"
echo "snapshot: $SNAP"

# Page through /score/all. Each record carries ftp_harmonized_scoring_files.<build>.positions.
tmp="$SNAP/scores.tsv.tmp"; : > "$tmp"
url="$API/score/all?limit=250"
while [[ -n "$url" && "$url" != "null" ]]; do
  page="$(curl -fsS --retry 5 --retry-delay 10 "$url")"
  jq -r --arg b "$BUILD" '.results[] |
      [.id, (.ftp_harmonized_scoring_files[$b].positions // ""), (.license // "" | gsub("[\t\n]"; " "))] | @tsv' \
      <<<"$page" >> "$tmp"
  url="$(jq -r '.next' <<<"$page")"
  echo "  listed $(wc -l < "$tmp") scores"
done
sort -u "$tmp" > "$SNAP/scores.tsv"; rm -f "$tmp"
curl -fsS "$API/release/current" > "$SNAP/release.json" || true

# Fill in any missing URL from the known FTP layout.
awk -F'\t' -v b="$BUILD" 'BEGIN{OFS="\t"} $2=="" {$2="https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/" $1 "/ScoringFiles/Harmonized/" $1 "_hmPOS_" b ".txt.gz"} {print}' \
  "$SNAP/scores.tsv" > "$SNAP/scores.tsv.new" && mv "$SNAP/scores.tsv.new" "$SNAP/scores.tsv"

# Download in parallel; skip files already present (re-runnable).
: > "$SNAP/failed.txt"
cut -f1,2 "$SNAP/scores.tsv" | sed 's#^ftp://#https://#; s#\tftp://#\thttps://#' |
  xargs -P 8 -L 1 bash -c '
    id="$0"; u="$1"; out="'"$SNAP"'/files/$(basename "$u")"
    [[ -s "$out" ]] && exit 0
    curl -fsSL --retry 5 --retry-delay 10 -o "$out.part" "$u" && mv "$out.part" "$out" \
      || { rm -f "$out.part"; echo "$id" >> "'"$SNAP"'/failed.txt"; }'

(cd "$SNAP/files" && sha256sum -- *.txt.gz) > "$SNAP/manifest.sha256"
echo "scores listed:     $(wc -l < "$SNAP/scores.tsv")"
echo "files downloaded:  $(ls "$SNAP/files" | wc -l)"
echo "failed downloads:  $(wc -l < "$SNAP/failed.txt")  (re-run to retry)"
