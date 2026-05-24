# Reproducible Runbook

This runbook assumes it is executed from the root of the public package.

## 1. Environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Python 3.11 was used in the W15 local smoke test.

## 2. Smoke Test

```powershell
python scripts\reproduce_all.py --smoke
```

Expected:

```text
compileall: pass
pytest: all tests pass
```

## 3. Output Directory Convention

The private project writes outputs under `rounds/R06_path2_opensees_benchmark/outputs/`. The public package writes to `outputs/`. The copied scripts detect `outputs/` automatically when no private `rounds/` directory exists. To be explicit:

```powershell
$env:HSTEEL_OUTPUT_DIR="outputs"
```

Clear it after the run:

```powershell
Remove-Item Env:HSTEEL_OUTPUT_DIR
```

## 4. Extended Toy Case

```powershell
$env:HSTEEL_OUTPUT_DIR="outputs"
python solver\extended_member_model.py --fit-table outputs\relaxation_fit_table.csv --output-dir outputs
Remove-Item Env:HSTEEL_OUTPUT_DIR
```

Expected values:

```text
n_newton_failures = 0
per_row_final_q_b approximately [0.6943, 1.0, 0.6943]
composite_factor_final approximately 0.3333
```

## 5. W4 and W5 Benchmarks

```powershell
$env:HSTEEL_OUTPUT_DIR="outputs"
python code\run_w4_fixed_ieff_sweep.py
python code\run_w5_full_benchmark.py
Remove-Item Env:HSTEEL_OUTPUT_DIR
```

Expected W5 summary:

```text
n_cases = 90
n_converged = 90
n_failed = 0
global label count = 5 weak response classes
```

## 6. W13 Sensitivity and Ablation

```powershell
$env:HSTEEL_OUTPUT_DIR="outputs"
python code\run_w13_sensitivity.py
python figures\fig5_sensitivity_ablation.py
python code\run_w16_timing.py
Remove-Item Env:HSTEEL_OUTPUT_DIR
```

Expected W13 summary:

```text
8 scenarios x 90 cases = 720 cases
all cases converged
eta envelope label counts unchanged
row-shape alternatives retain four to five labels
```

The figure is written to:

```text
figures/fig5_sensitivity_ablation.png
outputs/w16_timing_table.csv
outputs/w16_timing_table.md
```

## 7. Calibration

The derived calibration table is included as `outputs/relaxation_fit_table.csv`.

Full re-fitting requires the digitized calibration CSVs used in the private project. Those CSVs are not bundled in this W15 public-release candidate until the authors confirm redistribution rights for extracted values from the source papers. The DOI metadata and fit table are included so the benchmark can be rerun without redistributing raw publisher-derived data.

## 8. Archive Cross-Check Boundary

The private manuscript uses a corrected archive normalization table as response-proxy evidence. Raw thesis/Abaqus archive files and archive-derived normalized tables are not included in this W15 package because their redistribution boundary is not yet approved. This omission does not affect W4/W5/W13 benchmark reproduction.

## 9. Expected Core Files After Full Run

```text
outputs/extended_toy_case_summary.json
outputs/w4_fixed_ieff_sweep_summary.csv
outputs/benchmark_full.csv
outputs/benchmark_full_summary.json
outputs/w13_sensitivity_summary.csv
outputs/w13_sensitivity_case_summary.csv
figures/fig5_sensitivity_ablation.png
```
