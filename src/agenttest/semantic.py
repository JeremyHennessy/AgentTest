from __future__ import annotations

import re
from itertools import combinations
from typing import Any


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)
    }


def _memory(state: dict[str, Any]) -> dict[str, Any]:
    memory = state.setdefault(
        "semantic_memory",
        {
            "last_episode_index": 0,
            "concepts": {},
            "associations": {},
        },
    )
    memory.setdefault("last_episode_index", 0)
    memory.setdefault("concepts", {})
    memory.setdefault("associations", {})
    return memory


def consolidate_semantic_memory(state: dict[str, Any]) -> dict[str, int]:
    memory = _memory(state)
    episodes = state.get("episodes", [])
    start = min(int(memory.get("last_episode_index", 0)), len(episodes))
    new_episodes = episodes[start:]
    concept_updates = 0
    association_updates = 0

    for episode in new_episodes:
        episode_id = episode.get("id")
        cycle = int(episode.get("cycle", 0))
        concepts = sorted(
            {
                str(concept).strip().lower()
                for concept in episode.get("concepts", [])
                if str(concept).strip()
            }
        )

        for concept in concepts:
            node = memory["concepts"].setdefault(
                concept,
                {
                    "concept": concept,
                    "count": 0,
                    "first_cycle": cycle,
                    "last_cycle": cycle,
                    "episode_refs": [],
                },
            )
            node["count"] += 1
            node["first_cycle"] = min(int(node.get("first_cycle", cycle)), cycle)
            node["last_cycle"] = max(int(node.get("last_cycle", cycle)), cycle)
            if episode_id and episode_id not in node["episode_refs"]:
                node["episode_refs"].append(episode_id)
                node["episode_refs"] = node["episode_refs"][-32:]
            concept_updates += 1

        for left, right in combinations(concepts, 2):
            key = f"{left}|{right}"
            edge = memory["associations"].setdefault(
                key,
                {
                    "concepts": [left, right],
                    "count": 0,
                    "first_cycle": cycle,
                    "last_cycle": cycle,
                    "episode_refs": [],
                },
            )
            edge["count"] += 1
            edge["first_cycle"] = min(int(edge.get("first_cycle", cycle)), cycle)
            edge["last_cycle"] = max(int(edge.get("last_cycle", cycle)), cycle)
            if episode_id and episode_id not in edge["episode_refs"]:
                edge["episode_refs"].append(episode_id)
                edge["episode_refs"] = edge["episode_refs"][-32:]
            association_updates += 1

    memory["last_episode_index"] = len(episodes)
    return {
        "episodes_consolidated": len(new_episodes),
        "concept_updates": concept_updates,
        "association_updates": association_updates,
    }


def retrieve_semantic_memory(
    state: dict[str, Any],
    query: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    memory = _memory(state)
    terms = _tokens(query)
    ranked: list[tuple[float, str, dict[str, Any]]] = []

    for concept, node in memory["concepts"].items():
        count = float(node.get("count", 0))
        last_cycle = float(node.get("last_cycle", 0))
        lexical = 4.0 if concept in terms else 0.0
        score = lexical + min(3.0, count) + min(1.0, last_cycle / max(1.0, state.get("cycles", 1)))
        ranked.append((score, concept, node))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    result = []
    for score, concept, node in ranked[: max(0, limit)]:
        related = []
        for edge in memory["associations"].values():
            pair = edge.get("concepts", [])
            if concept in pair:
                other = pair[1] if pair and pair[0] == concept else (pair[0] if pair else None)
                if other:
                    related.append(
                        {
                            "concept": other,
                            "count": edge.get("count", 0),
                        }
                    )
        related.sort(key=lambda item: (-int(item["count"]), item["concept"]))
        result.append(
            {
                "concept": concept,
                "count": node.get("count", 0),
                "last_cycle": node.get("last_cycle", 0),
                "episode_refs": list(node.get("episode_refs", []))[-8:],
                "related": related[:5],
                "score": round(score, 4),
            }
        )
    return result


_EXPERIMENT_FOLLOWUP_PATTERNS = (
    re.compile(
        r"^What observable, evidence source, and resolution rule would make "
        r"experiment (X\d{6}) evidence-ready\?$"
    ),
    re.compile(
        r"^What obtainable evidence would resolve pending experiment "
        r"(X\d{6}) with the least additional assumption\?$"
    ),
)


def question_target_experiment_id(question: dict[str, Any]) -> str | None:
    explicit = question.get("target_experiment_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    text = str(question.get("text", ""))
    for pattern in _EXPERIMENT_FOLLOWUP_PATTERNS:
        match = pattern.match(text)
        if match:
            return match.group(1)
    return None


def question_has_active_experiment_path(
    state: dict[str, Any],
    question: dict[str, Any],
) -> bool:
    """Whether an open question currently leads to executable/active experiment work."""

    if question.get("status") != "open" or not question.get("id"):
        return False

    question_id = str(question["id"])
    linked = [
        experiment
        for experiment in state.get("experiments", [])
        if str(experiment.get("question_id") or "") == question_id
    ]
    if linked:
        return any(
            experiment.get("status") == "proposed"
            for experiment in linked
        )

    target_experiment_id = question_target_experiment_id(question)
    if target_experiment_id:
        return any(
            str(experiment.get("id") or "") == target_experiment_id
            and experiment.get("status") == "proposed"
            for experiment in state.get("experiments", [])
        )

    return False


def actionable_open_questions(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Derived live inquiry surface; preserves historical question records unchanged."""

    return [
        question
        for question in state.get("questions", [])
        if question_has_active_experiment_path(state, question)
    ]


INQUIRY_FAMILY_VERSION = "inquiry-family-state-v1"
INQUIRY_SIMILARITY_THRESHOLD = 0.72

_INQUIRY_STOPWORDS = {
    "a", "an", "and", "are", "be", "could", "did", "do", "does", "from",
    "has", "have", "how", "in", "into", "is", "it", "its", "my", "of",
    "on", "or", "rather", "than", "that", "the", "this", "to", "was",
    "were", "what", "when", "whether", "which", "with", "would",
}


def _inquiry_tokens(text: str) -> set[str]:
    normalized = text.lower()
    normalized = re.sub(r"\b[a-z]\d{4,}\b", " <id> ", normalized)
    normalized = re.sub(r"\b\d+(?:\.\d+)?\b", " <num> ", normalized)
    tokens = re.findall(r"<id>|<num>|[a-z][a-z0-9_]*", normalized)
    return {
        token
        for token in tokens
        if token not in _INQUIRY_STOPWORDS
    }


def _inquiry_similarity(left: str, right: str) -> float:
    a = _inquiry_tokens(left)
    b = _inquiry_tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def consolidate_inquiry_families(state: dict[str, Any]) -> dict[str, Any]:
    memory = _memory(state)
    questions = [
        question
        for question in state.get("questions", [])
        if isinstance(question, dict)
        and question.get("id")
        and str(question.get("text", "")).strip()
    ]
    count = len(questions)
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
            if (
                _inquiry_similarity(
                    str(questions[left].get("text", "")),
                    str(questions[right].get("text", "")),
                )
                >= INQUIRY_SIMILARITY_THRESHOLD
            ):
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

    family_records = []
    question_to_family: dict[str, str] = {}
    for index, family in enumerate(families, start=1):
        family_id = f"F{index:03d}"
        refs = [str(item["id"]) for item in family]
        for ref in refs:
            question_to_family[ref] = family_id
        family_records.append(
            {
                "family_id": family_id,
                "size": len(family),
                "question_refs": refs,
                "representative": str(family[0].get("text", "")),
            }
        )

    cycle_count = int(state.get("cycles", 0))
    family_count = len(family_records)
    open_endedness = (
        min(1.0, family_count / cycle_count)
        if cycle_count > 0
        else 0.0
    )
    summary = {
        "version": INQUIRY_FAMILY_VERSION,
        "similarity_threshold": INQUIRY_SIMILARITY_THRESHOLD,
        "question_count": count,
        "family_count": family_count,
        "open_endedness": open_endedness,
        "families": family_records,
        "question_to_family": question_to_family,
        "updated_cycle": cycle_count,
    }
    memory["inquiry_families"] = summary
    return summary
