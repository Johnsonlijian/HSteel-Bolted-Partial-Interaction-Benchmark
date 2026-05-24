# W13 Sensitivity Summary

This table supports the JCSR-positioned claim that the framework is a bounded reduced-order screening benchmark, not a design-ready prediction model.

## Scenario Summary

| Scenario | Group | Converged | Labels | Agreement vs baseline | Median min q_b/q_b0 | Median slip index | Label counts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| eta_0_no_relaxation | eta_envelope | 90/90 | 5 | 1.000 | 1.000 | 1.633 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| eta_ds1_ci_lo | eta_envelope | 90/90 | 5 | 1.000 | 0.807 | 1.633 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| eta_ds1_fit | eta_envelope | 90/90 | 5 | 1.000 | 0.698 | 1.633 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| eta_ds1_ci_hi | eta_envelope | 90/90 | 5 | 1.000 | 0.698 | 1.633 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| shape_outer_amplified | row_shape | 90/90 | 5 | 1.000 | 0.698 | 1.633 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| shape_uniform | row_shape | 90/90 | 4 | 0.856 | 0.592 | 2.499 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 30}` |
| shape_outer_mild | row_shape | 90/90 | 5 | 0.956 | 0.698 | 1.883 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 4, "slip_dominated": 26, "stiff_composite_like": 6}` |
| shape_center_amplified | row_shape | 90/90 | 4 | 0.856 | 0.592 | 2.499 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 30}` |

## Interpretation

- `eta_dis = 0` is the no-relaxation ablation; contrasts with ds1 CI scenarios isolate the contribution of dissipation-driven preload decay.
- Row-shape scenarios test whether the weak response classes are an artifact of the baseline outer-row-amplified slip map.
- The analysis should be cited as sensitivity evidence only. It does not convert the model into a design-ready predictor.
