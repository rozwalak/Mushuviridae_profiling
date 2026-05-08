#!/usr/bin/env python3
import subprocess
import argparse
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys


def find_sample_directory(study_name, sample_id, data_root):
    """Find sample directory, preferring the trimmed subdirectory if present."""
    base_path = Path(data_root) / study_name / sample_id
    trimmed_path = base_path / f"{sample_id}_trimmed"
    if trimmed_path.exists():
        return trimmed_path
    elif base_path.exists():
        return base_path
    return None


def run_sylph_processing(args):
    """Sketch and profile a single sample with sylph."""
    study_name, sample_id, database_path, data_root = args

    results_dir = Path("results") / study_name
    results_dir.mkdir(parents=True, exist_ok=True)

    sample_dir = find_sample_directory(study_name, sample_id, data_root)
    if not sample_dir:
        return (False, f"Sample directory not found for {sample_id}")

    sketch_dir = sample_dir / f"{sample_id}_sketches"
    sketch_dir.mkdir(parents=True, exist_ok=True)
    profile_output = results_dir / f"{sample_id}_profile.tsv"

    input_files = list(sample_dir.glob("*.fq.gz")) or list(sample_dir.glob("*.fastq.gz"))
    if not input_files:
        return (False, f"No input files found for {sample_id}")

    sketch_cmd = (
        f"sylph sketch -r <(zcat {' '.join(str(f) for f in input_files)}) "
        f"-S {sample_id} -c 100 -t 50 -d {sketch_dir}"
    )
    profile_cmd = (
        f"sylph profile {database_path} {sketch_dir}/{sample_id}.sylsp "
        f"-o {profile_output} -c 100 -t 50 --min-number-kmers 30 -u"
    )

    shell_script = f"""
set -eo pipefail
echo "Sketching {sample_id}"
{sketch_cmd}
echo "Profiling {sample_id}"
{profile_cmd}
"""

    try:
        subprocess.run(
            shell_script,
            shell=True,
            executable="/bin/bash",
            check=True,
        )
        return (True, f"Successfully processed {sample_id}")
    except subprocess.CalledProcessError as e:
        return (False, f"Failed to process {sample_id}: {e}")


def main(study_names, sample_ids, database_path, data_root="data"):
    if len(study_names) != len(sample_ids):
        raise ValueError("Number of study names must match number of sample IDs")

    tasks = [
        (study, sample, database_path, data_root)
        for study, sample in zip(study_names, sample_ids)
    ]

    num_processes = min(len(tasks), max(1, int(cpu_count() * 0.75)))
    success_count = 0

    with Pool(num_processes) as pool:
        for success, message in pool.imap_unordered(run_sylph_processing, tasks):
            print(message)
            if success:
                success_count += 1

    print(f"\nSuccessfully processed {success_count}/{len(tasks)} samples")
    if success_count < len(tasks):
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run sylph sketch + profile on one or more samples.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--study_name", nargs="+", required=True,
        help="Study name(s) for the samples",
    )
    parser.add_argument(
        "--sample_id", nargs="+", required=True,
        help="Sample ID(s) to process (must match order of --study_name)",
    )
    parser.add_argument(
        "--database", required=True,
        help="Path to sylph database (.syldb)",
    )
    parser.add_argument(
        "--data_root", default="data",
        help="Root directory containing sample data",
    )

    args = parser.parse_args()
    main(args.study_name, args.sample_id, args.database, args.data_root)
