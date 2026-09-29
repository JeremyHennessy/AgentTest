from __future__ import annotations

import re
from typing import Any

DIAGNOSTIC_VERSION = "inquiry-family-v2"
SIMILARITY_THRESHOLD = 0.72
MIN_QUESTIONS = 4
CHURN_MIN_FAMILY = 3
CHURN_MIN_DUPLICATE_PRESSURE = 0.25
METRIC_ALIGNMENT_TOLERANCE = 0.05

_STOPWORDS = {
    "a", "an", "and", "are", "be", "could", "did", "do", "does", "from",
    "has", "have", "how", "in", "into", "is", "it", "its", "my", "of",
    "on", "or", "rather", "than", "that", "the", "this", "to", "was",
    "were", "what", "when", "whether", "which", "with", "would",
}


def _tokens(text: str) -> set[str]:
    normalized = text.lower()
    normalized = re.sub(r"\b[a-z]\d{4,}\b", " <id> ", normalized)
    normalized = re.sub(r"\b\d+(?:\.\d+)?\b", " <num> ", normalized)
    tokens = re.findall(r"<id>|<num>|[a-z][a-z0-9_]*", normalized)
    return {
        token
        for token in tokens
        if token not in _STOPWORDS
    }


def _similarity(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _families(questions: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    count = len(questions)
    if count == 0:
        return []

    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left in range(count):
        for right in range(left + 1, count):
            similarity = _similarity(
                str(questions[left].get("text", "")),
                str(questions[right].get("text", "")),
            )
            if similarity >= SIMILARITY_THRESHOLD:
                union(left, right)

    grouped: dict[int, list[dict[str, Any]]] = {}
    for index, question in enumerate(questions):
        grouped.setdefault(find(index), []).append(question)

    families = list(grouped.values())
    families.sort(
        key=lambda family: (
            -len(family),
            str(family[0].get("id", "")),
        )
    )
    return families


def evaluate_inquiry_families(state: dict[str, Any]) -> dict[str, Any]:
    questions = [
        question
        for question in state.get("questions", [])
        if isinstance(question, dict)
        and question.get("id")
        and str(question.get("text", "")).strip()
    ]
    families = _families(questions)
    question_count = len(questions)
    family_count = len(families)
    repeated_count = sum(max(0, len(family) - 1) for family in families)
    duplicate_pressure = (
        0.0 if question_count == 0 else repeated_count / question_count
    )
    largest_family_size = max((len(family) for family in families), default=0)
    largest_family_ratio = (
        0.0 if question_count == 0 else largest_family_size / question_count
    )

    family_open_endedness = min(
        1.0,
        family_count / max(1, int(state.get("cycles", 0))),
    )
    reported_open_endedness = float(
        state.get("metrics", {}).get("open_endedness", 0.0)
    )
    metric_gap = reported_open_endedness - family_open_endedness
    churn_present = (
        largest_family_size >= CHURN_MIN_FAMILY
        and duplicate_pressure >= CHURN_MIN_DUPLICATE_PRESSURE
    )

    if question_count < MIN_QUESTIONS:
        outcome = "insufficient_data"
    elif churn_present and metric_gap > METRIC_ALIGNMENT_TOLERANCE:
        outcome = "metric_inflation"
    elif churn_present:
        outcome = "paraphrase_churn_metric_aligned"
    else:
        outcome = "diverse"

    family_records = []
    for index, family in enumerate(families, start=1):
        member_ids = [str(item["id"]) for item in family]
        family_records.append(
            {
                "family_id": f"F{index:03d}",
                "size": len(family),
                "question_refs": member_ids,
                "representative": str(family[0].get("text", "")),
                "max_pair_similarity": max(
                    (
                        _similarity(
                            str(family[left].get("text", "")),
                            str(family[right].get("text", "")),
                        )
                        for left in range(len(family))
                        for right in range(left + 1, len(family))
                    ),
                    default=1.0,
                ),
            }
        )

    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "outcome": outcome,
        "question_count": question_count,
        "family_count": family_count,
        "repeated_question_count": repeated_count,
        "duplicate_pressure": duplicate_pressure,
        "largest_family_size": largest_family_size,
        "largest_family_ratio": largest_family_ratio,
        "family_open_endedness": family_open_endedness,
        "reported_open_endedness": reported_open_endedness,
        "metric_gap": metric_gap,
        "metric_alignment_tolerance": METRIC_ALIGNMENT_TOLERANCE,
        "churn_present": churn_present,
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "families": family_records,
        "source_state_mutated": False,
    }
