# Package Manifest

Local public-release candidate for the JCSR submission.

## Included Directories

| Path | Contents | Release status |
| --- | --- | --- |
| `code/` | Benchmark, calibration, normalization, and sensitivity scripts plus tests | Public candidate |
| `solver/` | Reduced-order interface and member solver modules | Public candidate |
| `figures/` | Programmatic Figure 1, Figure 4, Figure 5, and Figure 6 scripts plus PNG outputs | Public candidate |
| `outputs/` | Derived calibration, toy-case, benchmark, sensitivity, defensive-check, timing, and corrected archive-normalization outputs | Public candidate |
| `scripts/` | Smoke-test/reproduction runner | Public candidate |

## Excluded From Package

| Excluded path/type | Reason |
| --- | --- |
| `sections/` | Active manuscript drafts are not part of public reproducibility code. |
| `submission/` | Cover letters, SI drafts, and upload checklists are submission material. |
| `rounds/` | Internal orchestration history; selected derived outputs are copied to `outputs/`. |
| `logs/` | Internal decision history. |
| raw thesis/Abaqus archive files | Private source material with unclear redistribution boundary. |
| raw archive files | Private source material; only the corrected derived normalization table is released. |
| credentials/session files | Not present and must never be released. |

## Smoke-Test Command

```powershell
python scripts\reproduce_all.py --smoke
```

## Full Reproduction Core

```powershell
$env:HSTEEL_OUTPUT_DIR="outputs"
python solver\extended_member_model.py --fit-table outputs\relaxation_fit_table.csv --output-dir outputs
python code\run_w4_fixed_ieff_sweep.py
python code\run_w5_full_benchmark.py
python code\run_w13_sensitivity.py
python code\run_defensive_sensitivity.py
python figures\fig4_response_state_map.py
python figures\fig5_sensitivity_ablation.py
python code\run_timing.py
Remove-Item Env:HSTEEL_OUTPUT_DIR
```
