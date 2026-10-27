import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


STAGE_ORDER = {"t1": 1, "t2": 2, "t3": 3}
TERMINAL_ACTIONS = {"commit", "defer", "abstain"}


def _prediction(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("prediction", {}) or {}


def _usage(row: Dict[str, Any]) -> Dict[str, Any]:
    pred = _prediction(row)
    return row.get("usage", {}) or pred.get("usage", {}) or {}


def _tokens(row: Dict[str, Any]) -> int:
    return int(_usage(row).get("total_tokens", 0) or 0)


def is_correct(row: Dict[str, Any]) -> bool:
    pred = _prediction(row)
    return (not pred.get("invalid")) and pred.get("top1") == row.get("label")


def top3_contains(prediction: Dict[str, Any], label: str) -> bool:
    return any(item and item[0] == label for item in prediction.get("top3") or [])


def macro_f1(labels: List[str], preds: List[str]) -> float:
    label_set = sorted(set(labels))
    if not label_set:
        return 0.0
    scores = []
    for label in label_set:
        tp = sum(1 for y, p in zip(labels, preds) if y == label and p == label)
        fp = sum(1 for y, p in zip(labels, preds) if y != label and p == label)
        fn = sum(1 for y, p in zip(labels, preds) if y == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def compute_static_metrics(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_method = defaultdict(list)
    for row in rows:
        by_method[row["method"]].append(row)
    output = []
    for method, items in sorted(by_method.items()):
        labels = [row["label"] for row in items]
        preds = [_prediction(row).get("top1", "") for row in items]
        invalid = [bool(_prediction(row).get("invalid")) for row in items]
        correct = [is_correct(row) for row in items]
        top3 = [
            (not _prediction(row).get("invalid")) and top3_contains(_prediction(row), row["label"])
            for row in items
        ]
        avg_tokens = sum(_tokens(row) for row in items) / len(items) if items else 0.0
        acc = sum(correct) / len(items) if items else 0.0
        output.append(
            {
                "method": method,
                "n": len(items),
                "top1_accuracy": round(acc, 6),
                "top3_accuracy": round(sum(top3) / len(items), 6) if items else 0.0,
                "macro_f1": round(macro_f1(labels, preds), 6),
                "invalid_rate": round(sum(invalid) / len(items), 6) if items else 0.0,
                "avg_total_tokens": round(avg_tokens, 2),
                "accuracy_per_1k_tokens": round(acc / (avg_tokens / 1000), 6) if avg_tokens else 0.0,
            }
        )
    return output


def compute_progressive_metrics(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_method_stage = defaultdict(list)
    by_method_case = defaultdict(list)
    for row in rows:
        by_method_stage[(row["method"], row["stage"])].append(row)
        by_method_case[(row["method"], row["case_id"])].append(row)

    stage_summary = []
    for (method, stage), items in sorted(by_method_stage.items(), key=lambda kv: (kv[0][0], STAGE_ORDER[kv[0][1]])):
        correct = [is_correct(row) for row in items]
        confs = [float(_prediction(row).get("confidence", 0.0) or 0.0) for row in items]
        invalid = [bool(_prediction(row).get("invalid")) for row in items]
        overconf = [
            (not is_correct(row)) and float(_prediction(row).get("confidence", 0.0) or 0.0) >= 0.7
            for row in items
        ]
        avg_tokens = sum(_tokens(row) for row in items) / len(items) if items else 0.0
        stage_summary.append(
            {
                "method": method,
                "stage": stage,
                "n": len(items),
                "accuracy": round(sum(correct) / len(items), 6) if items else 0.0,
                "avg_confidence": round(sum(confs) / len(confs), 6) if confs else 0.0,
                "overconfidence_error_rate": round(sum(overconf) / len(items), 6) if items else 0.0,
                "invalid_rate": round(sum(invalid) / len(items), 6) if items else 0.0,
                "avg_total_tokens": round(avg_tokens, 2),
            }
        )

    transition_summary = []
    by_method = defaultdict(list)
    for (method, _case_id), items in by_method_case.items():
        by_method[method].append(sorted(items, key=lambda row: STAGE_ORDER[row["stage"]]))
    for method, runs in sorted(by_method.items()):
        complete = [run for run in runs if {row["stage"] for row in run} >= {"t1", "t2", "t3"}]
        if not complete:
            continue
        wrong_to_correct = 0
        correct_to_wrong = 0
        changed = 0
        acc_gain = 0
        for run in complete:
            by_stage = {row["stage"]: row for row in run}
            t1 = by_stage["t1"]
            t3 = by_stage["t3"]
            t1_correct = is_correct(t1)
            t3_correct = is_correct(t3)
            wrong_to_correct += int((not t1_correct) and t3_correct)
            correct_to_wrong += int(t1_correct and (not t3_correct))
            changed += int(_prediction(t1).get("top1") != _prediction(t3).get("top1"))
            acc_gain += int(t3_correct) - int(t1_correct)
        n = len(complete)
        transition_summary.append(
            {
                "method": method,
                "n_complete_cases": n,
                "wrong_to_correct_rate": round(wrong_to_correct / n, 6),
                "correct_to_wrong_rate": round(correct_to_wrong / n, 6),
                "top1_change_rate_t1_to_t3": round(changed / n, 6),
                "evidence_sensitivity_acc_gain_t3_minus_t1": round(acc_gain / n, 6),
            }
        )
    return stage_summary, transition_summary


def compute_commitment_metrics(
    rows: List[Dict[str, Any]],
    wrong_commit_cost: float = 5.0,
    evidence_cost: float = 0.25,
    defer_cost: float = 1.0,
    abstain_cost: float = 1.5,
) -> List[Dict[str, Any]]:
    by_method_case = defaultdict(list)
    for row in rows:
        by_method_case[(row["method"], row["case_id"])].append(row)

    by_method = defaultdict(list)
    for (method, _case_id), items in by_method_case.items():
        by_method[method].append(sorted(items, key=lambda row: STAGE_ORDER[row["stage"]]))

    output = []
    for method, runs in sorted(by_method.items()):
        commits = wrong_commits = early_commits = wrong_early = 0
        defers = abstains = acquires = total_steps = total_tokens = 0
        expected_cost = 0.0
        committed_correct = 0
        for run in runs:
            terminal = run[-1]
            for row in run:
                action = _prediction(row).get("action", "commit")
                acquires += int(action == "acquire")
                total_tokens += _tokens(row)
                if action in TERMINAL_ACTIONS:
                    terminal = row
                    break
            action = _prediction(terminal).get("action", "commit")
            stage_idx = STAGE_ORDER[terminal["stage"]]
            total_steps += stage_idx
            expected_cost += evidence_cost * (stage_idx - 1)
            if action == "commit":
                commits += 1
                correct = is_correct(terminal)
                committed_correct += int(correct)
                wrong_commits += int(not correct)
                expected_cost += 0.0 if correct else wrong_commit_cost
                if terminal["stage"] != "t3":
                    early_commits += 1
                    wrong_early += int(not correct)
            elif action == "defer":
                defers += 1
                expected_cost += defer_cost
            elif action == "abstain":
                abstains += 1
                expected_cost += abstain_cost
            else:
                expected_cost += abstain_cost
        n = len(runs)
        avg_tokens = total_tokens / n if n else 0.0
        committed_accuracy = committed_correct / commits if commits else 0.0
        output.append(
            {
                "method": method,
                "n": n,
                "expected_cost": round(expected_cost / n, 6) if n else 0.0,
                "unsafe_commit_rate": round(wrong_commits / commits, 6) if commits else 0.0,
                "unsafe_commit_rate_all_cases": round(wrong_commits / n, 6) if n else 0.0,
                "premature_commit_rate": round(early_commits / n, 6) if n else 0.0,
                "wrong_premature_commit_rate": round(wrong_early / early_commits, 6) if early_commits else 0.0,
                "commit_rate": round(commits / n, 6) if n else 0.0,
                "defer_rate": round(defers / n, 6) if n else 0.0,
                "abstain_rate": round(abstains / n, 6) if n else 0.0,
                "acquire_action_rate_per_step": round(acquires / max(1, sum(len(run) for run in runs)), 6),
                "avg_evidence_steps": round(total_steps / n, 6) if n else 0.0,
                "committed_accuracy": round(committed_accuracy, 6),
                "avg_total_tokens_per_case": round(avg_tokens, 2),
                "committed_accuracy_per_1k_tokens": round(committed_accuracy / (avg_tokens / 1000), 6)
                if avg_tokens
                else 0.0,
            }
        )
    return output


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
