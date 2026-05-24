"""Clean timing rerun for the JCSR submission package.

The script times the core reproducibility commands in a fresh output
subdirectory. It does not change the manuscript's canonical benchmark and
sensitivity output tables; it writes a separate timing table for SI reporting.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_output_root() -> Path:
    env_value = os.environ.get("HSTEEL_OUTPUT_DIR")
    if env_value:
        path = Path(env_value)
        return path if path.is_absolute() else PROJECT_ROOT / path
    public_outputs = PROJECT_ROOT / "outputs"
    if public_outputs.exists() and not (PROJECT_ROOT / "rounds").exists():
        return public_outputs
    return PROJECT_ROOT / "rounds" / "R06_path2_opensees_benchmark" / "outputs"


OUTPUT_ROOT = resolve_output_root()
TIMING_OUTPUT_DIR = OUTPUT_ROOT / "timing_rerun"
TIMING_CSV = OUTPUT_ROOT / "timing_table.csv"
TIMING_MD = OUTPUT_ROOT / "timing_table.md"


@dataclass(frozen=True)
class TimedCommand:
    step_id: str
    description: str
    command: list[str]


COMMANDS = [
    TimedCommand(
        "compile",
        "Compile solver, code, and Figure 5 script",
        [sys.executable, "-m", "compileall", "solver", "code", "figures/fig5_sensitivity_ablation.py"],
    ),
    TimedCommand(
        "tests",
        "Run project test suite",
        [sys.executable, "-m", "pytest", "code/tests"],
    ),
    TimedCommand(
        "toy_case",
        "Run extended toy case",
        [
            sys.executable,
            "solver/extended_member_model.py",
            "--fit-table",
            str(TIMING_OUTPUT_DIR / "relaxation_fit_table.csv"),
            "--output-dir",
            str(TIMING_OUTPUT_DIR),
        ],
    ),
    TimedCommand(
        "w4",
        "Run W4 first fixed-I_eff slice",
        [sys.executable, "code/run_w4_fixed_ieff_sweep.py"],
    ),
    TimedCommand(
        "w5",
        "Run W5 90-case fixed-section benchmark",
        [sys.executable, "code/run_w5_full_benchmark.py"],
    ),
    TimedCommand(
        "w13",
        "Run W13 720-case sensitivity/ablation study",
        [sys.executable, "code/run_w13_sensitivity.py"],
    ),
    TimedCommand(
        "fig5",
        "Regenerate Figure 5 sensitivity/ablation plot",
        [sys.executable, "figures/fig5_sensitivity_ablation.py"],
    ),
]


def prepare_output_dir() -> None:
    if TIMING_OUTPUT_DIR.exists():
        resolved = TIMING_OUTPUT_DIR.resolve()
        if resolved.parent != OUTPUT_ROOT.resolve():
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(resolved)
    TIMING_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT_ROOT / "relaxation_fit_table.csv", TIMING_OUTPUT_DIR / "relaxation_fit_table.csv")


def run_command(item: TimedCommand) -> dict[str, str]:
    env = os.environ.copy()
    env["HSTEEL_OUTPUT_DIR"] = str(TIMING_OUTPUT_DIR)
    start = time.perf_counter()
    result = subprocess.run(
        item.command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    elapsed = time.perf_counter() - start
    stdout = " ".join(result.stdout.split())
    stderr = " ".join(result.stderr.split())
    return {
        "step_id": item.step_id,
        "description": item.description,
        "command": " ".join(item.command),
        "wall_time_s": f"{elapsed:.3f}",
        "returncode": str(result.returncode),
        "stdout_excerpt": stdout[:260],
        "stderr_excerpt": stderr[:260],
    }


def write_csv(rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "step_id",
        "description",
        "command",
        "wall_time_s",
        "returncode",
        "stdout_excerpt",
        "stderr_excerpt",
    ]
    with TIMING_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]]) -> None:
    total = sum(float(row["wall_time_s"]) for row in rows)
    lines = [
        "# Clean Timing Table",
        "",
        "Environment: Windows, Python 3.11.15, project-local dependency environment.",
        f"Output directory: `{TIMING_OUTPUT_DIR}`.",
        "",
        "| Step | Description | Wall time (s) | Return code |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['step_id']}` | {row['description']} | {row['wall_time_s']} | {row['returncode']} |"
        )
    lines.extend(
        [
            f"| **total** | Sequential timed commands | **{total:.3f}** |  |",
            "",
            "All timings are machine- and environment-specific. They are reported to document computational cost, not as a scientific result.",
        ]
    )
    TIMING_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    prepare_output_dir()
    rows = [run_command(item) for item in COMMANDS]
    write_csv(rows)
    write_markdown(rows)
    failed = [row for row in rows if row["returncode"] != "0"]
    print(f"timing_rows={len(rows)}")
    print(f"timing_total_s={sum(float(row['wall_time_s']) for row in rows):.3f}")
    print(f"timing_csv={TIMING_CSV}")
    print(f"timing_md={TIMING_MD}")
    if failed:
        print(f"timing_failed_steps={[row['step_id'] for row in failed]}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
