# Taxonomic profiling of low-abundant phages

This repository documents a pipeline used for taxonomic profiling of human gut metagenomes in the publication "Cosmopolitan gut bacteriophages expand the phenotype of health-related bacteria".

### 1. Environment installation
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

Install and activate conda environment:
```
conda env create -f environment.yml

conda activate sylph_profiling
```

Run pipeline on the test dataset:

```
bash pipeline.sh --input test.csv --config config.cfg
```

Run pipeline on full dataset: 
