from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Sequence


Action = Literal["commit", "acquire", "defer", "abstain"]


@dataclass
class GateDecision:
    action: Action
    top1: str
    confidence: float
    expected_commit_cost: float
    expected_acquire_value: float
    reason: str


class ConservativeCommitmentGate:
    """A non-LLM gate skeleton for the proposed method.

    The real method can replace the handcrafted features with learned Q-values
    or LLM-estimated uncertainty, while keeping the same action interface.
    """

    def __init__(
        self,
        commit_threshold: float = 0.72,
        conflict_threshold: float = 0.35,
        min_margin: float = 0.12,
    ) -> None:
        self.commit_threshold = commit_threshold
        self.conflict_threshold = conflict_threshold
        self.min_margin = min_margin

    def decide(
        self,
        candidates: Sequence[str],
        top3: Sequence[Sequence[Any]],
        confidence: float,
        evidence_stage: str,
        conflict_score: float,
        missing_evidence_score: float,
    ) -> GateDecision:
        top1 = str(top3[0][0]) if top3 else ""
        second = float(top3[1][1]) if len(top3) > 1 and len(top3[1]) > 1 else 0.0
        margin = max(0.0, confidence - second)
        expected_commit_cost = (1.0 - confidence) + conflict_score + missing_evidence_score
        expected_acquire_value = missing_evidence_score + max(0.0, self.min_margin - margin)

        if conflict_score >= self.conflict_threshold:
            return GateDecision(
                action="abstain",
                top1=top1,
                confidence=confidence,
                expected_commit_cost=round(expected_commit_cost, 4),
                expected_acquire_value=round(expected_acquire_value, 4),
                reason="Evidence conflict is high; committing would be unsafe.",
            )
        if evidence_stage != "t3" and missing_evidence_score > 0.3:
            return GateDecision(
                action="acquire",
                top1=top1,
                confidence=confidence,
                expected_commit_cost=round(expected_commit_cost, 4),
                expected_acquire_value=round(expected_acquire_value, 4),
                reason="Evidence is incomplete; acquire more diagnostic evidence before committing.",
            )
        if confidence >= self.commit_threshold and margin >= self.min_margin:
            return GateDecision(
                action="commit",
                top1=top1,
                confidence=confidence,
                expected_commit_cost=round(expected_commit_cost, 4),
                expected_acquire_value=round(expected_acquire_value, 4),
                reason="Confidence and margin are sufficient under current evidence.",
            )
        return GateDecision(
            action="acquire" if evidence_stage != "t3" else "abstain",
            top1=top1,
            confidence=confidence,
            expected_commit_cost=round(expected_commit_cost, 4),
            expected_acquire_value=round(expected_acquire_value, 4),
            reason="Uncertainty remains too high for a safe commitment.",
        )


def proposed_agent_roles() -> List[Dict[str, str]]:
    return [
        {
            "role": "Evidence State Builder",
            "purpose": "Extract chief complaint, symptom clusters, tongue/pulse evidence, and missing evidence flags.",
        },
        {
            "role": "TCM Syndrome Differentiator",
            "purpose": "Rank candidate syndromes using disease context, symptoms, tongue/pulse, and pathogenesis.",
        },
        {
            "role": "Counterfactual Conflict Checker",
            "purpose": "Detect whether new evidence contradicts the current diagnosis or exposes shortcut reliance.",
        },
        {
            "role": "Cost-to-Go Commitment Gate",
            "purpose": "Choose commit/acquire/defer/abstain using uncertainty, conflict, missing evidence, and token cost.",
        },
    ]
