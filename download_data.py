#!/usr/bin/env python3
"""
Parallel FASTQ downloader from ENA using fastq-dl
Forces ENA as the only provider with --provider ena --only-provider flags
"""

import csv
import subprocess
import time
from pathlib import Path
from datetime import timedelta
from multiprocessing import Pool, cpu_count
import argparse
import sys

def already_downloaded(accession, output_dir):
    """Check if FASTQ files exist and are non-empty"""
    paths = [
        Path(output_dir) / f"{accession}_1.fastq.gz",
        Path(output_dir) / f"{accession}_2.fastq.gz",
        Path(output_dir) / f"{accession}.fastq.gz"
    ]
    return any(p.is_file() and p.stat().st_size > 0 for p in paths)

def is_paired_end(accession, output_dir):
    """Check if download resulted in paired-end files"""
    pe1 = Path(output_dir) / f"{accession}_1.fastq.gz"
    pe2 = Path(output_dir) / f"{accession}_2.fastq.gz"
    return pe1.exists() and pe2.exists()

def download_single_file(args):
    """Download a single accession from ENA"""
    accession, prefix, output_dir, study_name, sample_id = args

    if already_downloaded(accession, output_dir):
        print(f"✓ [{study_name}/{sample_id}] {accession} already downloaded")
        return (accession, True, timedelta(0), "ena", study_name, sample_id,
                is_paired_end(accession, output_dir))

    print(f"↓ [{study_name}/{sample_id}] Downloading {accession} from ENA")

    cmd = [
        "fastq-dl",
        "--accession", accession,
        "--prefix", prefix,
        "--provider", "ena",
        "--only-provider",
        "--outdir", output_dir,
        "--cpus", "2",
        "--verbose"
    ]

    try:
        start_time = time.time()
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        dl_time = timedelta(seconds=time.time() - start_time)

        if result.stdout:
            print(f"[{accession}] stdout:\n{result.stdout[:500]}...")
        if result.stderr:
            print(f"[{accession}] stderr:\n{result.stderr[:500]}...", file=sys.stderr)

        if not already_downloaded(accession, output_dir):
            raise ValueError("Download completed but files not found")

        return (accession, True, dl_time, "ena", study_name, sample_id,
                is_paired_end(accession, output_dir))

    except (subprocess.CalledProcessError, ValueError) as e:
        error_msg = str(e)
        if hasattr(e, 'stderr') and e.stderr:
            error_msg = e.stderr[:1000]
        print(f"✗ [{study_name}/{sample_id}] Failed {accession}: {error_msg}", file=sys.stderr)
        return (accession, False, None, "ena", study_name, sample_id, None)

def process_manual_input(study_name, sample_id, accessions_str, num_processes):
    """Process a list of accessions for a given study/sample"""
    data_dir = Path("data").absolute()
    sample_dir = data_dir / study_name / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    accessions = [acc.strip() for acc in accessions_str.split(';') if acc.strip()]
    tasks = [(acc, acc, str(sample_dir), study_name, sample_id) for acc in accessions]

    print(f"\n📦 Starting download of {len(accessions)} accessions to: {sample_dir}")
    print(f"⚙️  Using {num_processes} parallel processes")
    print(f"🔒 Forcing ENA as only provider for all downloads\n")

    stats = {
        'total': len(accessions),
        'success': 0,
        'failed': 0,
        'paired': 0,
        'single': 0,
        'total_time': timedelta()
    }
    failed_downloads = []

    start_total = time.time()
    with Pool(processes=num_processes) as pool:
        results = pool.imap_unordered(download_single_file, tasks)

        for i, (acc, success, dl_time, _, _, _, is_pe) in enumerate(results, 1):
            if success:
                stats['success'] += 1
                stats['total_time'] += dl_time
                read_type = "PE" if is_pe else "SE"
                if is_pe:
                    stats['paired'] += 1
                else:
                    stats['single'] += 1
                print(f"✓ [{i}/{stats['total']}] {acc} ({read_type}) | Time: {dl_time}")
            else:
                stats['failed'] += 1
                failed_downloads.append({
                    'study_name': study_name,
                    'sample_id': sample_id,
                    'accession': acc,
                    'provider': 'ena'
                })
                print(f"✗ [{i}/{stats['total']}] Failed {acc}")

    total_time = timedelta(seconds=time.time() - start_total)

    print("\n" + "="*40)
    print("📊 Download Summary".center(40))
    print("="*40)
    print(f"Total accessions:        {stats['total']}")
    print(f"Successfully downloaded: {stats['success']} ({stats['success']/stats['total']:.1%})")
    print(f"  - Paired-end:          {stats['paired']}")
    print(f"  - Single-end:          {stats['single']}")
    print(f"Failed downloads:        {stats['failed']}")
    print(f"\n⏱️  Total download time:  {stats['total_time']}")
    print(f"⏱️  Wall clock time:      {total_time}")
    if stats['success'] > 0:
        print(f"⏱️  Average per file:     {stats['total_time']/stats['success']}")

    if failed_downloads:
        failed_csv = data_dir / "failed_downloads.csv"
        with failed_csv.open('a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=failed_downloads[0].keys())
            if failed_csv.stat().st_size == 0:
                writer.writeheader()
            writer.writerows(failed_downloads)
        print(f"\n⚠️  Failed downloads logged to: {failed_csv}")

    return total_time

def main():
    parser = argparse.ArgumentParser(
        description='Download FASTQ files in parallel from ENA using fastq-dl',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--study_name', required=True, help='Study identifier')
    parser.add_argument('--sample_id', required=True, help='Sample identifier')
    parser.add_argument('--accessions', required=True,
                       help='Semicolon-separated list of accessions (e.g. "ERR123;ERR124")')
    parser.add_argument('-p', '--processes', type=int, default=None,
                       help='Number of parallel processes (default: 75%% of CPU cores)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode (just validate inputs)')

    args = parser.parse_args()

    num_proc = max(1, int(cpu_count() * 0.75)) if args.processes is None else args.processes

    if args.test:
        print("✅ Input validation passed (test mode)")
        print(f"Study: {args.study_name}")
        print(f"Sample: {args.sample_id}")
        print(f"Accessions: {args.accessions.split(';')}")
        print(f"Would use {num_proc} processes")
        return

    print(f"🚀 Starting download: {args.study_name}/{args.sample_id}")
    script_start = time.time()
    process_manual_input(args.study_name, args.sample_id, args.accessions, num_proc)
    print(f"\n🏁 Total script execution time: {timedelta(seconds=time.time() - script_start)}")

if __name__ == "__main__":
    main()
