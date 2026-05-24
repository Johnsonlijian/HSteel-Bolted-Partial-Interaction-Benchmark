"""Link R04 calibration anchors to local evidence tables and direct-variable scripts."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


DIRECT_TOKENS = [
    "CDISP",
    "CFORCE",
    "CSTRESS",
    "CSTATUS",
    "CPRESS",
    "COPEN",
    "BoltLoad",
    "ConnectorSection",
    "ConnectorElasticity",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [{key.lstrip("\ufeff"): value for key, value in row.items()} for row in rows]


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_study_key(study_key: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in study_key.split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key] = value
    return result


def number_equal(a: str, b: str, tol: float = 1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return str(a) == str(b)


def match_study_key(row: dict[str, str], params: dict[str, str], keys: list[str]) -> bool:
    for key in keys:
        if key not in params:
            continue
        if not number_equal(row.get(key, ""), params[key]):
            return False
    return True


def compact(values: list[str], limit: int = 4) -> str:
    cleaned = [value for value in values if value]
    unique = []
    for value in cleaned:
        if value not in unique:
            unique.append(value)
    if len(unique) <= limit:
        return "; ".join(unique)
    return "; ".join(unique[:limit]) + f"; ... (+{len(unique) - limit})"


def scan_direct_variable_scripts(mirror_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in mirror_root.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = [token for token in DIRECT_TOKENS if token in text]
        if not hits:
            continue
        rel = path.relative_to(mirror_root).as_posix()
        if "实体单元模型" in rel:
            family = "entity_bolt_or_solid_contact"
        elif "3分离螺栓" in rel or "boltH" in path.name:
            family = "connector_bolt_shell"
        elif "2分离单独" in rel:
            family = "separated_shell"
        else:
            family = "other"
        rows.append(
            {
                "relative_path": rel,
                "script_family_guess": family,
                "has_direct_connector_output": str(any(token in hits for token in ["CDISP", "CFORCE", "CSTRESS", "CSTATUS"])),
                "has_contact_pressure_output": str(any(token in hits for token in ["CPRESS", "COPEN"])),
                "has_boltload": str("BoltLoad" in hits),
                "has_connector_definition": str(any(token in hits for token in ["ConnectorSection", "ConnectorElasticity"])),
                "tokens": ";".join(hits),
            }
        )
    rows.sort(key=lambda row: (row["script_family_guess"], row["relative_path"]))
    return rows


def summarize_script_inventory(script_rows: list[dict[str, str]]) -> dict[str, str]:
    families = Counter(row["script_family_guess"] for row in script_rows)
    direct = sum(row["has_direct_connector_output"] == "True" for row in script_rows)
    boltload = sum(row["has_boltload"] == "True" for row in script_rows)
    pressure = sum(row["has_contact_pressure_output"] == "True" for row in script_rows)
    connector = sum(row["has_connector_definition"] == "True" for row in script_rows)
    return {
        "direct_variable_script_count": str(len(script_rows)),
        "direct_connector_output_script_count": str(direct),
        "boltload_script_count": str(boltload),
        "contact_pressure_output_script_count": str(pressure),
        "connector_definition_script_count": str(connector),
        "direct_script_family_counts": "; ".join(f"{key}:{value}" for key, value in sorted(families.items())),
    }


def build_anchor_links(
    candidates: list[dict[str, str]],
    selected_evidence: list[dict[str, str]],
    field_extrema: list[dict[str, str]],
    selected_metrics: list[dict[str, str]],
    riks_coverage: list[dict[str, str]],
    case_atlas: list[dict[str, str]],
) -> list[dict[str, str]]:
    selected_by_key = defaultdict(list)
    for row in selected_evidence:
        selected_by_key[row.get("study_key", "")].append(row)

    field_by_key = defaultdict(list)
    for row in field_extrema:
        field_by_key[row.get("study_key", "")].append(row)

    metrics_by_key = {row.get("study_key", ""): row for row in selected_metrics}

    riks_by_key = defaultdict(list)
    for row in riks_coverage:
        riks_by_key[row.get("study_key", "")].append(row)

    case_keys = [
        "H",
        "B",
        "T1",
        "T2",
        "L",
        "n_or_E",
        "F",
        "BoltD",
        "BoltB",
        "cf1f",
        "cf2f",
        "cf3f",
        "yfss",
        "yuss",
        "yusn",
    ]

    links: list[dict[str, str]] = []
    for candidate in candidates:
        key = candidate["study_key"]
        params = parse_study_key(key)
        evidence_rows = selected_by_key.get(key, [])
        field_rows = field_by_key.get(key, [])
        metric = metrics_by_key.get(key, {})
        riks_rows = riks_by_key.get(key, [])
        atlas_matches = [row for row in case_atlas if match_study_key(row, params, case_keys)]

        roles = Counter(row.get("result_role", "") for row in evidence_rows)
        families = Counter(row.get("top_family_bucket", "") for row in evidence_rows)
        field_columns = Counter(row.get("column", "") for row in field_rows)
        atlas_families = Counter(row.get("model_family", "") for row in atlas_matches)
        atlas_interfaces = Counter(row.get("interface_mode", "") for row in atlas_matches)
        atlas_sources = [row.get("source_relpath", "") for row in atlas_matches]

        has_plastic_curve = any("plastic" in row.get("result_role", "").lower() or "Plastic" in row.get("file_basename", "") for row in evidence_rows)
        has_elastic_field = any("elastic" in row.get("result_role", "").lower() or "Elastic" in row.get("file_basename", "") for row in evidence_rows)
        has_field_extrema = bool(field_rows)
        has_riks_candidate = bool(riks_rows)
        def is_bolt_specific_case(atlas_row: dict[str, str]) -> bool:
            family_text = f"{atlas_row.get('model_family', '')} {atlas_row.get('interface_mode', '')}"
            return "螺栓" in family_text and "无螺栓" not in family_text

        has_exact_bolt_atlas = any(is_bolt_specific_case(row) for row in atlas_matches)

        if has_plastic_curve and has_field_extrema and has_riks_candidate:
            response_evidence_status = "strong_response_proxy"
        elif has_plastic_curve and (has_field_extrema or has_riks_candidate):
            response_evidence_status = "usable_response_proxy"
        elif has_plastic_curve:
            response_evidence_status = "curve_only_proxy"
        else:
            response_evidence_status = "weak_or_missing_response_proxy"

        if has_exact_bolt_atlas:
            direct_link_status = "exact_bolt_case_candidate_in_case_atlas"
        else:
            direct_link_status = "no_exact_bolt_case_in_case_atlas_for_this_signature"

        physical_upgrade_status = "weak_label_only"
        if has_exact_bolt_atlas:
            physical_upgrade_status = "candidate_for_direct_variable_extraction"
        elif has_field_extrema and has_riks_candidate:
            physical_upgrade_status = "response_proxy_ready_needs_direct_contact_or_slip"

        links.append(
            {
                "candidate_role": candidate.get("candidate_role", ""),
                "rank_score": candidate.get("rank_score", ""),
                "study_key": key,
                "archive_peak_abs_rf2_ratio": candidate.get("archive_peak_abs_rf2_ratio", ""),
                "archive_response_direction": candidate.get("archive_response_direction", ""),
                "selected_evidence_count": str(len(evidence_rows)),
                "selected_evidence_roles": "; ".join(f"{k}:{v}" for k, v in sorted(roles.items()) if k),
                "selected_family_buckets": "; ".join(f"{k}:{v}" for k, v in sorted(families.items()) if k),
                "sample_result_files": compact([row.get("relative_path", "") for row in evidence_rows], 5),
                "has_plastic_curve_or_report": str(has_plastic_curve),
                "has_elastic_field_or_mode_figure": str(has_elastic_field),
                "field_extrema_count": str(len(field_rows)),
                "field_extrema_columns": "; ".join(f"{k}:{v}" for k, v in sorted(field_columns.items()) if k),
                "metric_eigenvalue_ratio": metric.get("eigenvalue_ratio_separated_overall", ""),
                "metric_u2_ratio": metric.get("u2_absmax_ratio_separated_overall", ""),
                "metric_ur_ratio": metric.get("ur_magnitude_ratio_separated_overall", ""),
                "riks_family_slots": compact([row.get("family_slot", "") for row in riks_rows], 4),
                "riks_best_files": compact([row.get("best_file_basename", "") for row in riks_rows], 4),
                "case_atlas_match_count": str(len(atlas_matches)),
                "case_atlas_model_families": "; ".join(f"{k}:{v}" for k, v in sorted(atlas_families.items()) if k),
                "case_atlas_interface_modes": "; ".join(f"{k}:{v}" for k, v in sorted(atlas_interfaces.items()) if k),
                "case_atlas_sample_sources": compact(atlas_sources, 4),
                "direct_link_status": direct_link_status,
                "response_evidence_status": response_evidence_status,
                "physical_upgrade_status": physical_upgrade_status,
                "next_action": "link connector/entity-bolt outputs if available; otherwise keep weak labels and use response proxies",
            }
        )
    return links


def write_summary(
    links: list[dict[str, str]],
    scripts: list[dict[str, str]],
    path: Path,
) -> None:
    roles = Counter(row["candidate_role"] for row in links)
    response_status = Counter(row["response_evidence_status"] for row in links)
    physical_status = Counter(row["physical_upgrade_status"] for row in links)
    direct_link = Counter(row["direct_link_status"] for row in links)
    script_summary = summarize_script_inventory(scripts)

    lines = [
        "# R05 Anchor Evidence Linking Summary",
        "",
        f"Anchors linked: {len(links)}",
        "",
        "## Anchor Roles",
        "",
        "| Role | Count |",
        "| --- | ---: |",
    ]
    for key, value in sorted(roles.items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Response Evidence Status", "", "| Status | Count |", "| --- | ---: |"])
    for key, value in sorted(response_status.items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Physical Upgrade Status", "", "| Status | Count |", "| --- | ---: |"])
    for key, value in sorted(physical_status.items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Direct Link Status", "", "| Status | Count |", "| --- | ---: |"])
    for key, value in sorted(direct_link.items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Direct-Variable Script Inventory",
            "",
            f"- Scripts with any direct target token: {script_summary['direct_variable_script_count']}",
            f"- Scripts with connector/contact output tokens (`CDISP/CFORCE/CSTRESS/CSTATUS`): {script_summary['direct_connector_output_script_count']}",
            f"- Scripts with `BoltLoad`: {script_summary['boltload_script_count']}",
            f"- Scripts with `CPRESS/COPEN`: {script_summary['contact_pressure_output_script_count']}",
            f"- Scripts with connector definitions: {script_summary['connector_definition_script_count']}",
            f"- Family counts: {script_summary['direct_script_family_counts']}",
            "",
            "## Interpretation",
            "",
            "The 11 R04 anchors have usable response-proxy evidence through selected result files, field extrema and Riks-style curve/figure candidates. However, none of the exact P1 anchor signatures currently match a bolt-specific case family in the Case Atlas. Direct connector/contact output scripts and BoltLoad scripts exist elsewhere in the archive, but they are adjacent high-fidelity or connector-bolt families, not yet case-matched validation evidence.",
            "",
            "## Manuscript Consequence",
            "",
            "P1 can claim a reproducible theory and screening framework with archive response-proxy anchors. It cannot yet claim physically calibrated slip/contact/preload prediction. The next high-quality step is either to locate matching connector/entity-bolt result files for the same signatures or to create a small new open benchmark using the current Python solver/OpenSeesPy route.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--selected-evidence", required=True)
    parser.add_argument("--field-extrema", required=True)
    parser.add_argument("--selected-metrics", required=True)
    parser.add_argument("--riks-coverage", required=True)
    parser.add_argument("--case-atlas", required=True)
    parser.add_argument("--mirror-root", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    candidates = load_csv(Path(args.candidates))
    selected_evidence = load_csv(Path(args.selected_evidence))
    field_extrema = load_csv(Path(args.field_extrema))
    selected_metrics = load_csv(Path(args.selected_metrics))
    riks_coverage = load_csv(Path(args.riks_coverage))
    case_atlas = load_csv(Path(args.case_atlas))
    script_rows = scan_direct_variable_scripts(Path(args.mirror_root))
    links = build_anchor_links(candidates, selected_evidence, field_extrema, selected_metrics, riks_coverage, case_atlas)

    write_csv(links, outdir / "r05_anchor_evidence_links.csv")
    write_csv(script_rows, outdir / "r05_direct_variable_script_inventory.csv")
    write_summary(links, script_rows, outdir / "r05_anchor_evidence_summary.md")


if __name__ == "__main__":
    main()
