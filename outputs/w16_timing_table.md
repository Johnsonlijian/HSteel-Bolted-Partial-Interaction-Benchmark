# W16 Clean Timing Table

Environment: Windows, Python 3.11.15, project-local dependency environment.
Output directory: `R:\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\2026-HSteel-Bolted-Theory-TopJournal\rounds\R06_path2_opensees_benchmark\outputs\w16_timing_rerun`.

| Step | Description | Wall time (s) | Return code |
| --- | --- | ---: | ---: |
| `compile` | Compile solver, code, and Figure 5 script | 0.259 | 0 |
| `tests` | Run project test suite | 4.549 | 0 |
| `toy_case` | Run extended toy case | 1.224 | 0 |
| `w4` | Run W4 first fixed-I_eff slice | 4.817 | 0 |
| `w5` | Run W5 90-case fixed-section benchmark | 11.721 | 0 |
| `w13` | Run W13 720-case sensitivity/ablation study | 79.756 | 0 |
| `fig5` | Regenerate Figure 5 sensitivity/ablation plot | 1.412 | 0 |
| **total** | Sequential timed commands | **103.738** |  |

All timings are machine- and environment-specific. They are reported to document computational cost, not as a scientific result.
