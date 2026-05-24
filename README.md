# HSteel Bolted Partial-Interaction Benchmark

Status: public reproducibility package authorized by the author for GitHub publication.

This package supports the manuscript:

**Dissipation-driven bolt-preload relaxation in a reduced-order partial-interaction benchmark for bolted built-up H-section steel members**

The package is intentionally narrower than the private working project. It contains code, tests, generated figures, derived computational outputs, source metadata, and a reproducible runbook. It excludes manuscript drafts, cover letters, internal orchestration rounds, private logs, raw thesis/Abaqus archives, credentials, and any file with unclear redistribution rights.

## What This Package Reproduces

1. Synthetic recovery and DOI-anchored calibration workflow for the preload-relaxation law.
2. Extended reduced-order member solver with row-level stick-slip and preload-state history.
3. Analytical-limit sanity checks for zero-friction and infinite-friction composite-action limits.
4. First fixed-`I_eff` slice.
5. Ninety-case fixed-section benchmark.
6. `eta_dis` envelope and row-slip-shape sensitivity checks.
7. Step-refinement and label-threshold defensive checks.
8. Programmatic Figure 1, Figure 4, Figure 5, and Figure 6 generation.
9. Clean timing table for the core reproduction commands.
10. Corrected archive-derived section-normalization table approved for public release.

## Repository Layout

```text
.
|-- README.md
|-- LICENSE
|-- CITATION.cff
|-- DATASETS_AND_LINKS.csv
|-- REPRODUCIBLE_RUNBOOK.md
|-- SOURCE_REGISTRY_PUBLIC.md
|-- requirements.txt
|-- code/
|   |-- tests/
|   |-- calibrate_relaxation.py
|   |-- run_w4_fixed_ieff_sweep.py
|   |-- run_w5_full_benchmark.py
|   |-- run_w13_sensitivity.py
|   |-- run_defensive_sensitivity.py
|   `-- run_timing.py
|-- solver/
|-- figures/
|-- outputs/
`-- scripts/
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\reproduce_all.py --smoke
```

Expected smoke result: compile succeeds and the test suite passes.

## Output Directory

The scripts support a public-package output layout through the `HSTEEL_OUTPUT_DIR` environment variable. In this package, the default is `outputs/` when no private `rounds/` directory exists.

Example:

```powershell
$env:HSTEEL_OUTPUT_DIR="outputs"
python code\run_w5_full_benchmark.py
python code\run_w13_sensitivity.py
python figures\fig5_sensitivity_ablation.py
Remove-Item Env:HSTEEL_OUTPUT_DIR
```

## Release Boundary

Included:

- Python source code and tests.
- Generated benchmark outputs and figures.
- DOI/source metadata.
- Derived fit tables and benchmark tables.
- Corrected archive-derived section-normalization table.

Excluded:

- Active manuscript files under `sections/`.
- Cover letters and submission drafts.
- Internal `rounds/` and `logs/`.
- Raw private thesis/Abaqus archive files.
- Credentials, session files, or unpublished author/funding details.

## Scientific Boundary

This package reproduces a reduced-order screening benchmark. It does not provide a validated design model, design resistance factors, direct H-section mechanical-cycling validation, or raw bolt-force/contact-pressure measurements.
