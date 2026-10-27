import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from tcm_diagcommit.io_utils import read_jsonl, write_json
from tcm_diagcommit.metrics import (
    compute_commitment_metrics,
    compute_progressive_metrics,
    compute_static_metrics,
    write_csv,
)


def load_predictions(paths: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in paths:
        rows.extend(read_jsonl(Path(path)))
    return rows


def write_static(rows: List[Dict[str, Any]], out_dir: Path) -> None:
    overall = compute_static_metrics(rows)
    write_csv(out_dir / "static_metrics.csv", overall)
    write_json(out_dir / "static_metrics.json", overall)
    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row.get("variant", "unknown")].append(row)
    variant_rows: List[Dict[str, Any]] = []
    for variant, items in sorted(by_variant.items()):
        for metric in compute_static_metrics(items):
            metric = dict(metric)
            metric["variant"] = variant
            variant_rows.append(metric)
    write_csv(out_dir / "static_metrics_by_variant.csv", variant_rows)


def write_progressive(rows: List[Dict[str, Any]], out_dir: Path) -> None:
    stage_rows, transition_rows = compute_progressive_metrics(rows)
    write_csv(out_dir / "progressive_stage_metrics.csv", stage_rows)
    write_csv(out_dir / "progressive_transition_metrics.csv", transition_rows)
    write_json(
        out_dir / "progressive_metrics.json",
        {"stage_metrics": stage_rows, "transition_metrics": transition_rows},
    )
    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row.get("variant", "unknown")].append(row)
    variant_stage: List[Dict[str, Any]] = []
    variant_transition: List[Dict[str, Any]] = []
    for variant, items in sorted(by_variant.items()):
        stage, transition = compute_progressive_metrics(items)
        for metric in stage:
            metric = dict(metric)
            metric["variant"] = variant
            variant_stage.append(metric)
        for metric in transition:
            metric = dict(metric)
            metric["variant"] = variant
            variant_transition.append(metric)
    write_csv(out_dir / "progressive_stage_metrics_by_variant.csv", variant_stage)
    write_csv(out_dir / "progressive_transition_metrics_by_variant.csv", variant_transition)


def write_commitment(rows: List[Dict[str, Any]], out_dir: Path, args: argparse.Namespace) -> None:
    metrics = compute_commitment_metrics(
        rows,
        wrong_commit_cost=args.wrong_commit_cost,
        evidence_cost=args.evidence_cost,
        defer_cost=args.defer_cost,
        abstain_cost=args.abstain_cost,
    )
    write_csv(out_dir / "commitment_metrics.csv", metrics)
    write_json(out_dir / "commitment_metrics.json", metrics)
    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row.get("variant", "unknown")].append(row)
    variant_rows: List[Dict[str, Any]] = []
    for variant, items in sorted(by_variant.items()):
        for metric in compute_commitment_metrics(
            items,
            wrong_commit_cost=args.wrong_commit_cost,
            evidence_cost=args.evidence_cost,
            defer_cost=args.defer_cost,
            abstain_cost=args.abstain_cost,
        ):
            metric = dict(metric)
            metric["variant"] = variant
            variant_rows.append(metric)
    write_csv(out_dir / "commitment_metrics_by_variant.csv", variant_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["static", "progressive", "commitment"], required=True)
    parser.add_argument("--predictions", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--wrong-commit-cost", type=float, default=5.0)
    parser.add_argument("--evidence-cost", type=float, default=0.25)
    parser.add_argument("--defer-cost", type=float, default=1.0)
    parser.add_argument("--abstain-cost", type=float, default=1.5)
    args = parser.parse_args()

    rows = load_predictions(args.predictions)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.task == "static":
        write_static(rows, out_dir)
    elif args.task == "progressive":
        write_progressive(rows, out_dir)
    else:
        write_commitment(rows, out_dir, args)
    print(f"Scored {len(rows)} {args.task} rows into {out_dir}")


if __name__ == "__main__":
    main()
