# Taxonomic profiling of low-abundant phages

This repository documents a pipeline used for phage-inclusive taxonomic profiling of human gut metagenomes in the publication "Cosmopolitan gut bacteriophages expand the phenotype of health-related bacteria".

# Software
- Downloading: [fastq-dl v3.0.1](https://github.com/rpetit3/fastq-dl)
- Preprocessing: [Cutadapt v5.1](https://github.com/marcelm/cutadapt) via [TrimGalore v0.6.10](https://github.com/felixkrueger/trimgalore).
- Taxonomic profiling: [sylph v0.9.0](https://github.com/bluenote-1577/sylph) and [sylph-tax v1.2.0](https://github.com/bluenote-1577/sylph)

# Environment Setupy
Make a copy of the repository:
```
git clone https://github.com/rozwalak/Mushuviridae_profiling.git
```
Unpack metadata files and download the sylph database from Zenodo:
```
cd Mushuviridae_profiling

gunzip ./sylph_tax_metadata/*.gz

wget -O sylph_100c_db.syldb "https://zenodo.org/records/20084670/files/sylph_100c_db.syldb?download=1"
```

Install and activate the conda environment:
```
conda env create -f environment.yml

conda activate sylph_profiling
```
# Generating taxonomic profiles
To run sylph, three input files are necessary:
- sylph database (sylph_100c_db.syldb with 102,336 species-like vOTUs and 4,744 prokaryotic-species representatives from UHGG v2.0.2). 
- metadata with taxonomic info about phages (all_phage_genomes_taxo.tsv).
- metadata with taxonomic info about bacteria (uhgg2_metadata.tsv).

Run pipeline on the test dataset (< 1 minute):

```
bash pipeline.sh --input test.csv --config config.cfg
```

Run pipeline on the full dataset (weeks, depending on available resources): 

```
bash pipeline.sh --input all_accessions.csv --config config.cfg
```

The expected output is a /results folder containing subfolders named after study_name, and Sylph output files named after sample_id as defined in the input CSV file.
