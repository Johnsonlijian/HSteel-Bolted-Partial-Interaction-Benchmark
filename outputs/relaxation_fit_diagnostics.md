# Relaxation Fit Diagnostics

Calibration date: 2026-05-22

The W2 data report preload vs. thermal cycle count, not measured frictional work.
Following the brief, `dissipation_proxy` maps each reported cycle to `dW_f=1`.
Sensitivity below rescales that proxy; eta changes with the scale, while residual preload is more stable.
When the trajectory reaches the fitted residual plateau, eta is only lower-bound identifiable; the fitter uses a tiny eta tie-breaker to choose the smallest eta with the same SSE.

## ds1_eraliev2021_m12_120c

- DOI: `10.1177/16878140211039428`
- Points: 5
- Source: Figure 8(c), Results text
- eta_dis: 0.30875 (95% residual-bootstrap CI 0.1773 to 0.334062)
- q_b_residual: 0.48875 (95% residual-bootstrap CI 0.459375 to 0.537914)
- RMS residual: 0.0603635
- Dissipation-proxy sensitivity:
- scale=0.5: eta_dis=0.81998, q_b_residual=0.455, RMS=0.0301662
- scale=1: eta_dis=0.30875, q_b_residual=0.48875, RMS=0.0603635
- scale=2: eta_dis=0.154375, q_b_residual=0.48875, RMS=0.0603635

Extraction notes:
- Initial preload normalized to 1.0; M12 x 1.75 Grade 8.8 stainless-steel bolted joint, 5 kN initial preload, 20-120 C thermal cycles.
- Text reports 41% loss after first cycle; normalized preload = 1 - 0.410.
- Text reports following-cycle loosening of 8.5%; cumulative normalized preload = 1 - 0.410 - 0.085.
- Text reports following-cycle loosening of 5.5%; cumulative normalized preload = 1 - 0.410 - 0.085 - 0.055.
- Text reports following-cycle loosening of 4%; cumulative normalized preload = 1 - 0.410 - 0.085 - 0.055 - 0.040.

## ds2_eraliev2022_abs2_40c

- DOI: `10.3390/app12063001`
- Points: 5
- Source: Figure 4, Results text
- eta_dis: 0.1095 (95% residual-bootstrap CI 0.084 to 0.1105)
- q_b_residual: 0.8635 (95% residual-bootstrap CI 0.8595 to 0.8685)
- RMS residual: 0.00716938
- Dissipation-proxy sensitivity:
- scale=0.5: eta_dis=0.219, q_b_residual=0.8635, RMS=0.00716938
- scale=1: eta_dis=0.1095, q_b_residual=0.8635, RMS=0.00716938
- scale=2: eta_dis=0.05475, q_b_residual=0.8635, RMS=0.00716938

Extraction notes:
- Initial preload normalized to 1.0; ABS-2 3D-printed bolt, 10-40 C thermal cycles, initial preload 1000 N.
- Text reports ABS-2 preload 877 N after first cycle; normalized by 1000 N.
- Text reports ABS-2 preload 861 N after second cycle; normalized by 1000 N.
- Text reports remaining cycles loosen by 1 N and 4 N; first residual decrement applied after cycle 3.
- Text reports remaining cycles loosen by 1 N and 4 N; cumulative endpoint after cycle 4 = 856 N.
