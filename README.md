# Synthon Enumeration Pipeline
A high-throughput, RDKit-based enumeration pipeline currently for generating single-step analogues by attaching one synthon to a seed at a selected reactive site (“mark” location), using a curated set of reaction templates.

This repository is designed to scale to many seeds and millions of synthons by:
- indexing synthons by mark type for fast retrieval
- pre-indexing reaction templates by compatible mark pairs
- batching outputs for downstream processing (e.g., docking, filtering, scoring)
- supporting both streaming and Parquet materialization

> Note: This repo includes a mention of SyntOn. Detailed SyntOn usage and background are documented in a separate [Readme](SyntOn/README.md) located under the SyntOn directory. It is recommended to read through that first, to get more context on how molecules are processed to annotate chemically significant reactive sites/marks and how they can be reconstructed using specific reaction templates.

---

## Key Concepts

### Marks / Reactive Sites
Seeds and synthons are annotated with reactive marks using atom-map tags in bracket atoms, e.g.:

- `[C:10]`, `[N:20]`, `[n:20]`, `[S:10]`

A “site” is a specific occurrence of a mark in a seed (not just the mark type). Site identity is deterministic and reproducible. These are chemically determined and can be made using [`mainsynthonsgenerator`](SyntOn/src/SyntOn_BBs.py) from the SyntOn codebase.

### Single-Step Enumeration
For each seed:
1. Canonicalize seed SMILES (stereochemistry preserved).
2. Identify all reactive sites and assign deterministically a `site_id`.
3. Choose one site to react (random by default, or user-specified).
4. Retrieve all compatible synthons (by mark).
5. Apply only compatible reaction templates (by mark pair) to produce products.

Each product corresponds to a route-level record (even if multiple routes lead to the same final SMILES).

---

## Features

- Deterministic reactive site IDs on canonicalized seeds
- Site selection by `site_id` or `MARK@ORDINAL` (e.g., `C:10@0`)
- Reaction template filtering via a precomputed mark-pair → reaction index
- Synthon indexing by mark type for fast candidate lookup
- Output modes:
  - `stream` (generator of batches)
  - `parquet` (sharded Parquet + manifest)
  - `stream+parquet` (yield batches while writing Parquet)
- Deterministic route_id for stable provenance keys
- Batched processing for scalability and downstream throughput

---

## Repository Structure
### SyntOn
As mentioned, synthonization of building blocks utilizes tools created in the SyntOn repository. Please refer to the [Readme](SyntOn/README.md) located in that directory for more information.

### Enumeration
This is the home to files necesary for enumeration
#### `standardization.py`
Seed canonicalization / preprocessing

- Parses the input seed SMILES into an RDKit Mol.
- Generates canonical SMILES while preserving stereochemistry.
- Re-parses canonical SMILES to ensure a stable canonical atom order.
- Produces a lightweight `StandardizedSeed` record.

Why it matters: reactive site IDs are defined only on canonicalized seeds, ensuring reproducibility.

---

#### `sites.py`
Reactive site inspection + user selection resolution (separate from enumeration)

- Finds atoms with atom-map numbers (`GetAtomMapNum()`).
- Builds normalized `mark_type` strings (`C:10`, `n:20`, etc.).
- Assigns deterministic `site_id` values using canonical atom ranking.
- Computes `mark_occurrence_index` and `site_label` (e.g., `C:10@0`).
- Resolves user constraints:
  - `allowed_sites=[0, 2]`
  - `allowed_site_specs=["C:10@1"]`
- Supports error/warn policies for invalid site requests.

Why it matters: users can target specific reactive sites unambiguously, even if mark types repeat.

---

#### `reactions.py`
Reaction template parsing + `ReactionIndex`

- Parses `Setup.xml` reaction definitions:
  - `Labels` → which mark types belong on each reactant side
  - `ReconstructionReaction` → SMARTS used for enumeration
- Pre-indexes templates by mark pair:
  - `(seed_mark, synthon_mark) -> [(reaction_id, order), ...]`
- Caches compiled RDKit reactions for reuse.
- Tracks reactant order:
  - `order=0`: (seed, synthon)
  - `order=1`: (synthon, seed)

Why it matters: avoids trying every reaction template for every candidate.

---

#### `synthons.py`
Synthon records + `SynthonIndex`

- Stores minimal synthon metadata:
  - `synthon_id`, `synthon_smiles`, extracted `marks`
- Builds an inverted index:
  - `mark_type -> [synthon_id, ...]`
- Designed for large libraries (millions of synthons).
- RDKit Mol creation is deferred until a synthon is actually tested in a reaction.

Why it matters: fast retrieval of candidates compatible with a seed site.

---

#### `output_sinks.py`
Parquet output writer + manifest

- `ParquetSink` writes one Parquet shard per batch.
- Includes `manifest.json` with shard list, counts, and run metadata.
- Uses PyArrow for efficient columnar output and compression.

Why it matters: enables checkpointing, replay, and decoupled downstream pipelines.

---

#### `enumeration_single_step.py`
Single-step enumeration engine

- Ties everything together:
  - canonicalize seed
  - inspect sites & resolve constraints
  - choose one site (deterministic RNG)
  - filter compatible marks
  - fetch compatible synthons
  - fetch applicable reaction templates
  - run RDKit reactions
  - emit route-level records in batches
- Supports:
  - `output_mode="stream" | "parquet" | "stream+parquet"`


### Analysis
Here is where you can find files related to analyis of generated molecules. This includes docking with associated preparation, as well as other common forms of scoring. Please refer to the [README](analysis/README.md) there for more information and what kind of scoring you can do.

---

## Installation and Usage
### Dependencies
<!-- The list of required packages for enumeration is fairly light, only requring the following: but still use the .yml file for installation and remove this
- Python 3.9+
- RDKit
- PyArrow (required for Parquet output modes)

If preferred you can install them using any package manager (conda/pixie) and version of preference. Additionally, you may install the conda env with the following command for a more comprehensive environment. -->
You can install the required dependencies for synthon generation and enumeration with the following command
```bash
conda env create -f environment.yaml
```

### Synthon Generation
The first step of this pipeline is synthon Generation. We assume you have either an sdf or smi file containing your database of desired building blocks. To synthonize, we will use a wrapper calling a modified version of the script [SyntOn_BBsBulkClassificationAndSynthonization.py](SyntOn/SynthOn_BBsBulkClassificationAndSynthonization.py) from the Synt-On repository. 

```bash
python bulksynthonization.py -h 
```

```text
Generate synthons and scaffolds from an SDF/SMI using Synt-On functions

options:
  -h, --help            show this help message and exit
  --input INPUT, -i INPUT
                        Path to sdf file with Building blocks (BBs)
  --out OUT, -o OUT     Output prefix (files will be prefix_synthons.smi, prefix_bb_scaffolds.smi, prefix_classification.tsv)
  -n N                  Number of BB's to process (Default to None, i.e. process all)
  --keepPG              Pass keepPG True to mainSynthonsGenerator (keep protected synthons)
  --Ro2Filtr            Filter produced synthons by Ro2 using Synt-On Ro2Filtration
  --n_cores N_CORES     Number of available cores for parallel calculations. Memory usage is optimized, so maximal number of parallel processes can be launched.
  --progress            Show a progress bar (tqdm if available; otherwise a simple counter).
  --pstep PSTEP         Batch updates every N lines in multiprocessing mode (default: 50)

Analysis and Code Implementation: Eli Paul, Sung-Hun Bae
Eisai Center for Genetics Guided Dementia Discovery (G2D2)
Original Synt-On Code implementation:                Yuliana Zabolotna, Alexandre Varnek
                                    Laboratoire de Chémoinformatique, Université de Strasbourg.

Knowledge base (SMARTS library):    Dmitriy M.Volochnyuk, Sergey V.Ryabukhin, Kostiantyn Gavrylenko, Olexandre Oksiuta
                                    Institute of Organic Chemistry, National Academy of Sciences of Ukraine
                                    Kyiv National Taras Shevchenko University
2021 Strasbourg, Kiev

```
An minimal example call may look like

```bash
python bulksynthonization.py -i <path_to_your_BBs sdf/smi> -o synth_example
```
Which will create four files: synth_example_BBmode.smi, synth_example_Synthmode.smi, synth_example_NotClassified, and synth_example_NotProcessed. For more information about each files structure and purpose, please refer to the [Readme](SyntOn/README.md) in the SyntOn directory. For the following analyses, we will focus on synth_example_Synthmode.smi.

### Fragment Enumeration
An example end to end run of enumeration can be found in [examples](examples/fragment_synthoization.ipynb). In the example, we simply use a synthon as a starting seed, but you may use any starting fragment that may or may not be present in your BB database.

Multiple seeds can be passed at once; however, currently, only single step enumeration is supported. i.e. if a seed has multiple reactive sites, only one will be used during enumeration.

To run enumeration, we can use:
```bash
python enumeration/enumerate.py -h 
```

```text
usage: enumeration.py [-h] --seeds SEEDS --synthons SYNTHONS [--rxn_config RXN_CONFIG]
                      [--mode {stream,parquet,both}] [-o OUTPUT_DIR] [-b BATCH_SIZE] [--run_name RUN_NAME]
                      [--rng_seed RNG_SEED]

options:
  -h, --help            show this help message and exit
  --seeds SEEDS         Path to seeds/scaffolds (sdf or smi file)
  --synthons SYNTHONS   Path to synthons (smi file)
  --site_id             (Optional) Choose a specific reaction center to enumerate from. Chosen randomly if not provided.
  --rxn_config RXN_CONFIG
                        Path to reaction setup configuration file
  --mode {stream,parquet,both}
                        Choose an output format: streaming generator (stream), parquet files (parquet), or both
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Where to save parquet outputs (if applicable)
  -b BATCH_SIZE, --batch_size BATCH_SIZE
                        Batch size for enumeration
  --run_name RUN_NAME   Run id/name for persistence and separation between runs
  --rng_seed RNG_SEED   Random seed for when using random site selection during enumeration
```
A minimal example may look like:
```bash
python enumeration/enumerate.py  --seeds seed_fragments.sdf --synthons synth_example_Synthmode.smi --output_dir example_dir --mode parquet
```
This will created the output_dir which will be home to directories containing the results parquet files.
#### Site Identification & User Selection

To inspect sites (and their IDs) for a seed in case you want to specify during enumeration, you can run the following:

```python
>>> from standardization import canonicalize_seed_smiles
>>>from sites import list_sites_pretty
>>>std, mol = canonicalize_seed_smiles("CC([C:10])N")
>>>print(list_sites_pretty(mol))
```
```text
[{'site_id': 0, 'mark_type': 'C:10', 'site_label': 'C:10@0', 'canonical_atom_rank': 3, 'atom_idx': 3, 'mark_occurrence_index': 0}]
```

If a seed has multiple reaction sites, you can restrict enumeration to specific sites via the argument. Otherwise, a site will be chosen at random.
#### Parquet Outputs
The results from enumeration can be generated in two ways. Firstly, a generator, where each item is a batch of <batch_size> containing enumeration results. This can be useful if you want to preform small analysis on the results or simply check the outputs. Additionally, results can be saved to parquet files, which will be housed in <output_dir> and can be used for larger scale downstream analysis and enhanced persistence. Each parquet file will correspond to a single batch of results. 

Each enumerated result is a route-level record (dict-like) containing:

- `route_id` (deterministic hash)
- `seed_id`, `seed_canonical_smiles`
- `seed_site_id`, `seed_site_mark_type`, `seed_site_atom_idx`
- `synthon_id`, `synthon_smiles`, `synthon_mark_type`
- `reaction_id`, `reaction_name`, `reactant_order`
- `product_smiles`, `product_valid`, `failure_reason`
- run metadata: `run_id`, `rng_seed`

> Even if two routes lead to the same final product SMILES, both records are retained (route provenance is preserved).


#### Reaction Configuration and Definition
rxn_config defulats to `Setup.xml` (reaction definitions)
This file defines available reactions and reconstruction SMARTS. The pipeline uses:
- `Labels` to map reaction “handles” to mark types (e.g., `C:10`, `N:20`)
- `ReconstructionReaction` for the actual SMARTS applied during enumeration

  Additionally,  you may edit to add additional reactions as needed, or create a new configuration if desired that follows the same structure.


---

## Reproducibility

Reproducibility and tracability is ensured via:
- canonical seed representation (`seed_canonical_smiles`)
- deterministic site IDs on the canonical seed
- deterministic `route_id` derived from route components
- user-configurable RNG seed for random site selection

The results of every run contains all of the information to understand and trace how it was generated.

---

## Performance Notes and Recommendations (Scaling Guidance)

- Index once, enumerate many: build `SynthonIndex` and `ReactionIndex` once and reuse. Its quick to retrieve by mark type but slower to build and sort many times
- Batch size matters: larger batches (to an extent) reduce overhead (especially for Parquet writing).
- Sharded outputs: for HPC/multi-process workflows, write per-worker output shards to avoid file contention.
- Avoid materializing huge lists: prefer `stream` or `stream+parquet` for large jobs.

---

## Contributing

Contributions are welcome, please fork if you are interested. Suggested areas:
- additional reaction schemas (for synthonization or reconstruction)
- performance profiling and optimization
- improved reaction/template parsing and validation
- support for additional input formats and HPC job orchestration patterns
- expanded test coverage (especially for tricky chemistry edge cases)

---

## License

- This project is primarily licensed under the MIT License (see LICENSE.txt).
- Portions of the code under `SyntOn/` are licensed under the BSD 3-Clause License.
  See `SyntOn/LICENSE` for details.
