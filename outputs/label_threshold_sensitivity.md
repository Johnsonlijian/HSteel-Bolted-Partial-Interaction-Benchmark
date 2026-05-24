# Weak-label threshold sensitivity

| Scenario | Agreement | Labels retained | Label counts |
| --- | ---: | ---: | --- |
| baseline | 1.000 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| all_thresholds_minus10 | 0.867 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 27, "mixed_slip_stability": 6, "slip_dominated": 17, "stiff_composite_like": 4}` |
| all_thresholds_plus10 | 0.956 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 8, "slip_dominated": 20, "stiff_composite_like": 8}` |
| global_threshold_minus10 | 1.000 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| global_threshold_plus10 | 1.000 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| local_threshold_minus10 | 0.900 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 27, "mixed_slip_stability": 5, "slip_dominated": 16, "stiff_composite_like": 6}` |
| local_threshold_plus10 | 1.000 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 6, "slip_dominated": 23, "stiff_composite_like": 7}` |
| slip_thresholds_minus10 | 0.956 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 8, "slip_dominated": 24, "stiff_composite_like": 4}` |
| slip_thresholds_plus10 | 0.956 | 5 | `{"global_instability_sensitive": 36, "local_buckling_softening": 18, "mixed_slip_stability": 8, "slip_dominated": 20, "stiff_composite_like": 8}` |

Interpretation: all tested threshold perturbations retain all five labels, with minimum non-baseline agreement 0.867. The weak labels are therefore auditable screening classes rather than single-threshold artefacts.
