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
