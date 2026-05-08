#!/bin/bash
set -euo pipefail

# ─── Usage ────────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") --input <csv> --config <config_file> [OPTIONS]

Required:
  -i, --input   <file>   Input CSV  (columns: study_name,sample_id,NCBI_accession)
  -c, --config  <file>   Config file (see config.cfg for template)

Optional:
  -j, --jobs    <int>    Max parallel jobs          (default: MAX_JOBS in config, else 8)
  -r, --results <dir>    Results directory           (default: RESULTS_DIR in config, else ./results)
  -D, --data-dir <dir>   Data base directory         (default: DATA_DIR in config, else ./data)
  -l, --logs    <dir>    Logs directory              (default: LOGS_DIR in config, else ./logs)
  -h, --help             Show this help message

Config file keys (see config.cfg):
  DATABASE          Path to sylph .syldb database file         [required]
  METADATA_UHGG     Path to uhgg2_metadata.tsv                 [required]
  METADATA_PHAGE    Path to all_phage_genomes_taxo.tsv         [required]
  METADATA_EXTRA    Path to additional metadata .tsv (optional)
  RESULTS_DIR       Output results directory
  DATA_DIR          Working data directory
  LOGS_DIR          Log files directory
  MAX_JOBS          Max parallel jobs

Example:
  bash $(basename "$0") --input test.csv --config config.cfg
  bash $(basename "$0") --input test.csv --config config.cfg --jobs 4
EOF
    exit 1
}

# ─── Argument parsing ─────────────────────────────────────────────────────────
input_csv=""
config_file=""
arg_max_jobs=""
arg_results_dir=""
arg_data_dir=""
arg_logs_dir=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--input)    input_csv="$2";       shift 2 ;;
        -c|--config)   config_file="$2";     shift 2 ;;
        -j|--jobs)     arg_max_jobs="$2";    shift 2 ;;
        -r|--results)  arg_results_dir="$2"; shift 2 ;;
        -D|--data-dir) arg_data_dir="$2";    shift 2 ;;
        -l|--logs)     arg_logs_dir="$2";    shift 2 ;;
        -h|--help)     usage ;;
        *) echo "❌ Unknown option: $1"; usage ;;
    esac
done

# ─── Validate CLI inputs ──────────────────────────────────────────────────────
[[ -z "$input_csv" ]]     && { echo "❌ --input is required.";              usage; }
[[ -z "$config_file" ]]   && { echo "❌ --config is required.";             usage; }
[[ ! -f "$input_csv" ]]   && { echo "❌ Input CSV not found: $input_csv";   exit 1; }
[[ ! -f "$config_file" ]] && { echo "❌ Config file not found: $config_file"; exit 1; }

# ─── Load config file ─────────────────────────────────────────────────────────
# Strip comments/blanks and source key=value pairs safely
while IFS='=' read -r key value; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${key// }" ]]           && continue
    key="${key// /}"                    # trim whitespace from key
    value="${value%%#*}"                # strip inline comments
    value="${value%"${value##*[! ]}"}"  # rtrim value
    declare "$key=$value"
done < <(grep -v '^\s*#' "$config_file" | grep -v '^\s*$')

# ─── Apply defaults (config → CLI override → built-in default) ────────────────
max_jobs="${arg_max_jobs:-${MAX_JOBS:-8}}"
results_dir="${arg_results_dir:-${RESULTS_DIR:-./results_3}}"
data_base_dir="${arg_data_dir:-${DATA_DIR:-./data}}"
logs_dir="${arg_logs_dir:-${LOGS_DIR:-./logs}}"

# ─── Validate required config fields ─────────────────────────────────────────
errors=0
check_required() {
    local var_name="$1"
    local var_value="${!var_name:-}"
    if [[ -z "$var_value" ]]; then
        echo "❌ Config error: $var_name is not set in $config_file"
        (( errors++ )) || true
    elif [[ ! -f "$var_value" ]]; then
        echo "❌ Config error: $var_name file not found: $var_value"
        (( errors++ )) || true
    fi
}

check_required DATABASE
check_required METADATA_UHGG
check_required METADATA_PHAGE

if [[ -n "${METADATA_EXTRA:-}" && ! -f "$METADATA_EXTRA" ]]; then
    echo "❌ Config error: METADATA_EXTRA file not found: $METADATA_EXTRA"
    (( errors++ )) || true
fi

[[ $errors -gt 0 ]] && exit 1

# ─── Setup directories ────────────────────────────────────────────────────────
mkdir -p "$results_dir" "$data_base_dir" "$logs_dir"
overview_file="${logs_dir}/overview.csv"
echo "study,sample_id,status,timestamp" > "$overview_file"

# ─── Print config summary ─────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════"
echo "  Sylph Metagenomic Pipeline"
echo "════════════════════════════════════════════════════════"
printf "  %-22s %s\n" "Input CSV:"        "$input_csv"
printf "  %-22s %s\n" "Config file:"      "$config_file"
printf "  %-22s %s\n" "Database:"         "$DATABASE"
printf "  %-22s %s\n" "Metadata UHGG:"    "$METADATA_UHGG"
printf "  %-22s %s\n" "Metadata Phage:"   "$METADATA_PHAGE"
[[ -n "${METADATA_EXTRA:-}" ]] && \
printf "  %-22s %s\n" "Metadata extra:"   "$METADATA_EXTRA"
printf "  %-22s %s\n" "Results dir:"      "$results_dir"
printf "  %-22s %s\n" "Data dir:"         "$data_base_dir"
printf "  %-22s %s\n" "Logs dir:"         "$logs_dir"
printf "  %-22s %s\n" "Max parallel jobs:" "$max_jobs"
echo "════════════════════════════════════════════════════════"
echo ""

# ─── Helper functions ─────────────────────────────────────────────────────────
log_status() {
    echo "$1,$2,$3,$(TZ='Europe/Paris' date +"%Y-%m-%d %H:%M:%S")" >> "$overview_file"
}

cleanup_sample_files() {
    local study="$1"
    local sample="$2"
    local sample_dir="${data_base_dir}/${study}/${sample}"

    find "$sample_dir" -type f \( -name "*.fastq.gz" -o -name "*.fq.gz" \) -delete 2>/dev/null
    find "$sample_dir" -type d -name "*_sketches" -exec rm -rf {} + 2>/dev/null
    find "$sample_dir" -type d -empty -delete 2>/dev/null
}

cleanup_successful_study() {
    local study="$1"
    find "${results_dir}/${study}" -name "taxo-*.sylphmpa" -delete 2>/dev/null
}

run_taxonomic_processing() {
    local study="$1"
    local study_dir="${results_dir}/${study}"

    echo "  → Taxonomic processing for $study"

    # Build -t arguments from config: required + optional extra
    local meta_args=(-t "$METADATA_UHGG" "$METADATA_PHAGE")
    [[ -n "${METADATA_EXTRA:-}" ]] && meta_args+=("$METADATA_EXTRA")

    sylph-tax taxprof "${study_dir}"/*_profile.tsv \
        "${meta_args[@]}" \
        -o "${study_dir}/taxo-" >> "${logs_dir}/${study}_taxonomic.log" 2>&1
}

merge_study_results() {
    local study="$1"
    local study_dir="${results_dir}/${study}"
    local base_output="${study_dir}/${study}"

    echo "  → Merging results for $study"

    for col in ANI relative_abundance sequence_abundance; do
        sylph-tax merge "${study_dir}"/taxo-*.sylphmpa \
            --column "$col" \
            -o "${base_output}_${col}.tsv" >> "${logs_dir}/${study}_merge.log" 2>&1
    done
}

process_sample() {
    local study="$1"
    local sample="$2"
    local accession="$3"
    local log_file="${logs_dir}/${study}_${sample}.log"
    local profile_file="${results_dir}/${study}/${sample}_profile.tsv"
    local sample_dir="${data_base_dir}/${study}/${sample}"

    mkdir -p "${results_dir}/${study}" "$sample_dir"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing $study/$sample" > "$log_file"
    log_status "$study" "$sample" "STARTED"

    # Step 1: Download
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Downloading" >> "$log_file"
    if ! python download_data.py \
            --study_name "$study" \
            --sample_id  "$sample" \
            --accessions "$accession" \
            -p 4 >> "$log_file" 2>&1; then
        log_status "$study" "$sample" "FAILED_DOWNLOAD"; return 1
    fi
    log_status "$study" "$sample" "DOWNLOAD_COMPLETED"

    # Step 2: Trim
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Trimming" >> "$log_file"
    if ! python trimming.py \
            --study_name "$study" \
            --sample_id  "$sample" \
            -t 4 >> "$log_file" 2>&1; then
        log_status "$study" "$sample" "FAILED_TRIMMING"; return 1
    fi
    log_status "$study" "$sample" "TRIMMING_COMPLETED"

    # Step 3: Profile — DATABASE from config
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Profiling" >> "$log_file"
    if ! python sylph_run.py \
            --study_name  "$study" \
            --sample_id   "$sample" \
            --database    "$DATABASE" \
            --data_root   "$data_base_dir" >> "$log_file" 2>&1; then
        log_status "$study" "$sample" "FAILED_PROFILING"; return 1
    fi

    if [[ ! -f "$profile_file" ]]; then
        log_status "$study" "$sample" "FAILED_PROFILING"; return 1
    fi

    cleanup_sample_files "$study" "$sample"
    log_status "$study" "$sample" "CLEANUP_COMPLETED"
    log_status "$study" "$sample" "PROFILING_COMPLETED"
    echo "  ✓ $study/$sample done"
    return 0
}

# ─── Main processing loop ─────────────────────────────────────────────────────
study_list=$(tail -n +2 "$input_csv" | cut -d',' -f1 | sort -u)
total_samples=$(( $(wc -l < "$input_csv") - 1 ))

for study in $study_list; do
    echo "┌─ Study: $study"
    study_samples=0

    while IFS=, read -r s sample accession; do
        [[ "$s" != "$study" ]] && continue
        (( study_samples++ )) || true

        while [[ $(jobs -rp | wc -l) -ge $max_jobs ]]; do
            sleep 1
        done

        process_sample "$study" "$sample" "$accession" &
    done < <(tail -n +2 "$input_csv")

    wait

    study_failures=$(grep "^${study}," "$overview_file" | grep -c "FAILED_" || true)

    if [[ $study_failures -eq 0 && $study_samples -gt 0 ]]; then
        if run_taxonomic_processing "$study"; then
            log_status "$study" "ALL" "TAXONOMIC_PROCESSING_COMPLETED"
            if merge_study_results "$study"; then
                log_status "$study" "ALL" "MERGING_COMPLETED"
                cleanup_successful_study "$study"
                log_status "$study" "ALL" "STUDY_COMPLETED"
                echo "└─ ✓ Study $study complete"
            else
                log_status "$study" "ALL" "FAILED_MERGING"
                echo "└─ ✗ Study $study failed at merging" >&2
            fi
        else
            log_status "$study" "ALL" "FAILED_TAXONOMIC_PROCESSING"
            echo "└─ ✗ Study $study failed at taxonomic processing" >&2
        fi
    else
        log_status "$study" "ALL" "STUDY_INCOMPLETE"
        echo "└─ ✗ Study $study incomplete ($study_failures failed samples)" >&2
    fi
    echo ""
done

# ─── Final report ─────────────────────────────────────────────────────────────
completed_studies=$(grep -c ",ALL,STUDY_COMPLETED,"  "$overview_file" || true)
completed_samples=$(grep -c ",PROFILING_COMPLETED," "$overview_file" || true)
failed_samples=$(( total_samples - completed_samples ))

echo "════════════════════════════════════════════════════════"
echo "  Pipeline complete"
echo "════════════════════════════════════════════════════════"
printf "  %-26s %s\n" "Total studies:"      "$(echo "$study_list" | wc -w)"
printf "  %-26s %s\n" "Completed studies:"  "$completed_studies"
printf "  %-26s %s\n" "Total samples:"      "$total_samples"
printf "  %-26s %s\n" "Completed samples:"  "$completed_samples"
printf "  %-26s %s\n" "Failed samples:"     "$failed_samples"
printf "  %-26s %s\n" "Status log:"         "$overview_file"
echo "════════════════════════════════════════════════════════"

[[ $failed_samples -gt 0 ]] && exit 1
exit 0
