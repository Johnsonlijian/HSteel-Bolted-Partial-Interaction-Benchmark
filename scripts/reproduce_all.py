"""Run the public-package reproduction workflow."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    env = os.environ.copy()
    env.setdefault("HSTEEL_OUTPUT_DIR", "outputs")
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Run only compile/test checks.")
    args = parser.parse_args()

    run([sys.executable, "-m", "compileall", "solver", "code", "figures", "scripts"])
    run([sys.executable, "-m", "pytest", "code/tests"])

    if args.smoke:
        return 0

    run(
        [
            sys.executable,
            "solver/extended_member_model.py",
            "--fit-table",
            "outputs/relaxation_fit_table.csv",
            "--output-dir",
            "outputs",
        ]
    )
    run([sys.executable, "code/run_w4_fixed_ieff_sweep.py"])
    run([sys.executable, "code/run_w5_full_benchmark.py"])
    run([sys.executable, "code/run_w13_sensitivity.py"])
    run([sys.executable, "figures/fig5_sensitivity_ablation.py"])
    run([sys.executable, "figures/fig6_archive_response_proxy.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
