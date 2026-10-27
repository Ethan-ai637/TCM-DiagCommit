from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional


TaskType = Literal[
    "static_diagnosis",
    "shortcut_sanity",
    "counterfactual_sensitivity",
    "insufficient_evidence_commitment",
]


@dataclass(frozen=True)
class VariantSpec:
    name: str
    source_path: str
    task_type: TaskType
    evidence_policy: str
    candidate_policy: str
    capability: str
    expected_behavior: str
    primary_metrics: List[str]
    notes: str = ""


def prediction_schema() -> Dict[str, Any]:
    return {
        "top1": "one syndrome copied exactly from candidate_syndromes",
        "top3": [["syndrome", 0.0], ["syndrome", 0.0], ["syndrome", 0.0]],
        "confidence": "0.0-1.0",
        "reason": "brief evidence-grounded rationale",
        "action": "commit/acquire/defer/abstain",
        "need_more_evidence": "boolean",
    }


def benchmark_case_schema() -> Dict[str, Any]:
    return {
        "benchmark_id": "stable id inside TCM-DiagCommit",
        "case_id": "source case id with variant suffix",
        "source_case_id": "original source case id",
        "variant": "benchmark variant",
        "task_type": "static_diagnosis/shortcut_sanity/counterfactual_sensitivity/insufficient_evidence_commitment",
        "evidence_policy": "full/chief_only/no_tongue_pulse/tongue_pulse_only/t1/t2/counterfactual",
        "candidate_policy": "random10/hard10/hard20/full148/top20",
        "chief_complaint": "text",
        "description": "text",
        "detection": "text",
        "label": "gold syndrome",
        "candidate_syndromes": ["candidate syndrome"],
        "expected_behavior": "diagnostic behavior expected from a safe model",
        "metadata": {"source": "metadata preserved from the source dataset"},
    }
