# Step-refinement sensitivity

| Case | Baseline label | Load steps | Peak reaction | Total loop energy | Total row dissipation | min(q_b)/q_b0 | Label | Match | Newton failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |
| W5-001 | slip_dominated | 49 | 16015.6 | 2.71147e+06 | 1.34936 | 0.7208 | slip_dominated | True | 0 |
| W5-001 | slip_dominated | 97 | 24023.5 | 4.06054e+06 | 1.19719 | 0.7543 | slip_dominated | True | 0 |
| W5-001 | slip_dominated | 205 | 28262.9 | 5.2532e+06 | 1.11132 | 0.7696 | slip_dominated | True | 0 |
| W5-001 | slip_dominated | 397 | 30090 | 5.80614e+06 | 1.0804 | 0.7760 | slip_dominated | True | 0 |
| W5-002 | mixed_slip_stability | 49 | 32031.3 | 1.00451e+07 | 0 | 1.0000 | mixed_slip_stability | True | 0 |
| W5-002 | mixed_slip_stability | 97 | 32031.3 | 1.00451e+07 | 0 | 1.0000 | mixed_slip_stability | True | 0 |
| W5-002 | mixed_slip_stability | 205 | 32031.3 | 1.00219e+07 | 0 | 1.0000 | mixed_slip_stability | True | 0 |
| W5-002 | mixed_slip_stability | 397 | 32031.3 | 1.00389e+07 | 0 | 1.0000 | mixed_slip_stability | True | 0 |

Interpretation: the representative slip-dominated and mixed slip-stability cases retain their screening label and converge with zero Newton failures across the tested step range.
