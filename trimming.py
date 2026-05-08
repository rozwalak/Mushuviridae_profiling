import os
import subprocess
import argparse
from pathlib import Path
from multiprocessing import Pool, cpu_count
from datetime import timedelta
import time

def run_trim_galore(input_file, output_dir, is_paired=False, paired_file=None, threads=1):
    cmd = [
        "trim_galore",
        "--quality", "20",
        "--length", "20",
        "--stringency", "1",
        "--gzip",
        "--cores", str(threads),
        "--output_dir", str(output_dir),
    ]

    if is_paired and paired_file:
        cmd.extend(["--paired", str(input_file), str(paired_file)])
    else:
        cmd.append(str(input_file))

    try:
        subprocess.run(cmd, check=True)
        return (input_file.name, True)
    except subprocess.CalledProcessError as e:
        print(f"Error processing {input_file.name}: {e}")
        return (input_file.name, False)

def check_trimmed_files_exist(input_file, output_dir, is_paired=False, paired_file=None):
    if is_paired and paired_file:
        base_name_1 = input_file.name.replace('_1.f', '_1_val_1.f').replace('_R1.f', '_R1_val_1.f')
        base_name_2 = paired_file.name.replace('_2.f', '_2_val_2.f').replace('_R2.f', '_R2_val_2.f')
        trimmed_file_1 = output_dir / base_name_1
        trimmed_file_2 = output_dir / base_name_2
        return trimmed_file_1.exists() and trimmed_file_2.exists()
    else:
        trimmed_name = input_file.name.replace('.fastq', '_trimmed.fastq').replace('.fq', '_trimmed.fq')
        trimmed_file = output_dir / trimmed_name
        return trimmed_file.exists()

def process_files(fastq_dir, threads_per_job=1):
    fastq_dir = Path(fastq_dir).resolve()
    output_dir = fastq_dir / f"{fastq_dir.name}_trimmed"
    output_dir.mkdir(exist_ok=True)

    fastq_files = sorted(fastq_dir.glob('*.fastq.gz')) + sorted(fastq_dir.glob('*.fq.gz'))
    processed_files = set()
    tasks = []
    skipped_files = set()

    for file in fastq_files:
        if file.name in processed_files or output_dir in file.parents:
            continue

        is_paired = False
        paired_file = None
        for suffix in ['_R1', '_1']:
            if suffix in file.name:
                paired_suffix = file.name.replace(suffix, '_R2' if suffix == '_R1' else '_2')
                paired_file = file.parent / paired_suffix
                if paired_file.exists():
                    is_paired = True
                    break

        if check_trimmed_files_exist(file, output_dir, is_paired, paired_file):
            skipped_files.add(file.name)
            if is_paired:
                skipped_files.add(paired_file.name)
            continue

        if is_paired:
            tasks.append((file, output_dir, True, paired_file, threads_per_job))
            processed_files.update([file.name, paired_file.name])
        else:
            tasks.append((file, output_dir, False, None, threads_per_job))
            processed_files.add(file.name)

    if skipped_files:
        print(f"\nSkipping {len(skipped_files)} already trimmed files: {', '.join(sorted(skipped_files))}")

    if not tasks:
        print("\nAll samples already processed. Nothing to do.")
        return []

    print(f"\nProcessing {len(tasks)} samples from: {fastq_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Using {min(cpu_count(), len(tasks))} parallel jobs with {threads_per_job} threads each")

    start_time = time.time()
    with Pool(processes=min(cpu_count(), len(tasks))) as pool:
        results = pool.starmap(run_trim_galore, tasks)

    success = sum(1 for _, status in results if status)
    print(f"\n=== Trim Galore Summary for {fastq_dir.name} ===")
    print(f"Total samples processed: {len(tasks)}")
    print(f"Successful: {success}")
    print(f"Failed: {len(tasks) - success}")
    print(f"Skipped (already processed): {len(skipped_files)}")
    print(f"Time elapsed: {timedelta(seconds=time.time() - start_time)}")

    log_file = output_dir / "trimming_log.txt"
    with open(log_file, 'w') as f:
        f.write("Filename\tStatus\n")
        for name in skipped_files:
            f.write(f"{name}\tSkipped (already processed)\n")
        for name, status in results:
            f.write(f"{name}\t{'Success' if status else 'Failed'}\n")

    return results

def main(study_names, sample_ids, threads_per_job, data_root="data"):
    if len(study_names) != len(sample_ids):
        raise ValueError("Number of study names must match number of sample IDs.")

    data_root = Path(data_root).resolve()

    for study, sample in zip(study_names, sample_ids):
        sample_dir = None
        potential_dir = data_root / study / sample
        if potential_dir.exists():
            sample_dir = potential_dir
        else:
            for parent_dir in data_root.glob('*'):
                potential_dir = parent_dir / study / sample
                if potential_dir.exists():
                    sample_dir = potential_dir
                    break

        if not sample_dir:
            print(f"⚠️  Warning: Directory for sample {sample} from study {study} not found in {data_root}. Skipping.")
            continue

        print(f"\n=== Processing sample: {sample} from study: {study} ===")
        print(f"Found sample directory at: {sample_dir}")
        process_files(sample_dir, threads_per_job)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run Trim Galore on manually provided sample directories',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--study_name', nargs='+', required=True,
                        help='One or more study names (space-separated)')
    parser.add_argument('--sample_id', nargs='+', required=True,
                        help='One or more sample IDs (space-separated, matching order of study names)')
    parser.add_argument('-t', '--threads_per_job', type=int, default=1,
                        help='Threads per Trim Galore job')
    parser.add_argument('-d', '--data_root', default="data",
                        help='Root directory containing the data folders')

    args = parser.parse_args()

    print("Starting manual Trim Galore processing...")
    main(args.study_name, args.sample_id, args.threads_per_job, args.data_root)
