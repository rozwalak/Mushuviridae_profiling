# Taxonomic profiling of low-abundant phages

This repository documents a pipeline used for phage-inclusive taxonomic profiling of human gut metagenomes in the publication "Cosmopolitan gut bacteriophages expand the phenotype of health-related bacteria".

# Software
XXX

XXX

### 1. Environment Setup
Make a copy of the repository:
```
git clone https://github.com/rozwalak/Mushuviridae_profiling.git
```
Unpack metadata files and download the sylph database from Zenodo:
```
cd Mushuviridae_profiling

gunzip ./sylph_tax_metadata/*.gz

XXX
```

Install and activate the conda environment:
```
conda env create -f environment.yml

conda activate sylph_profiling
```
### 2. Generating taxonomic profiles
To run sylph three input files are necessary:
- database (default: sylph_100c_db.syldb with 102,336 species-like vOTUs and 4,744 prokaryotic-species representatives from UHGG v2.0.2) 
- metadata with taxonomic info about phages (all_phage_genomes_taxo.tsv)
- metadata with taxonomic info about bacteria (uhgg2_metadata.tsv)

Run pipeline on the test dataset:

```
bash pipeline.sh --input test.csv --config config.cfg
```

Run pipeline on the full dataset: 

```
bash pipeline.sh --input all_accessions.csv --config config.cfg
```
