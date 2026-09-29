from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from .semantic import retrieve_semantic_memory
from .state import utc_now
from .world import current_world_claims

PROMPT_VERSION = "cognition-v2"
DEFAULT_MODEL = "gpt-6-luna"
RESPONSES_URL = "https://api.openai.com/v1/responses"

CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "minLength": 1, "maxLength": 500},
        "hypothesis": {"type": "string", "minLength": 1, "maxLength": 1000},
        "experiment": {"type": "string", "minLength": 1, "maxLength": 1500},
        "falsification": {"type": "string", "minLength": 1, "maxLength": 1000},
        "predicted_observation": {"type": "string", "minLength": 1, "maxLength": 1000},
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 32},
            "minItems": 1,
            "maxItems": 12,
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "novelty_note": {"type": "string", "minLength": 1, "maxLength": 800},
    },
    "required": [
        "question",
        "hypothesis",
        "experiment",
        "falsification",
        "predicted_observation",
        "evidence_refs",
        "confidence",
        "novelty_note",
    ],
    "additionalProperties": False,
}

_INSTRUCTIONS = """You are the optional cognition component of AgentTest, an experiment in
persistent evidence-driven machine growth. Produce exactly one testable candidate thought.

Rules:
- Use only evidence explicitly supplied in the context.
- Reference evidence by its supplied IDs.
- World claims are derived summaries; prefer raw evidence when practical.
- Do not claim an observation happened unless it appears in evidence.
- Do not claim consciousness, subjective experience, sentience, or improvement.
- Prefer a hypothesis that could be wrong.
- Give a concrete falsifier and predicted observation.
- Align the question with the current intention and strongest drive.
- Do not provide hidden reasoning or a chain of thought; return only the requested fields.
- You have no authority to change state, tools, code, metrics, or evidence.
"""


class CognitionProvider(Protocol):
    name: str

    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        ...


class StaticCognitionProvider:
    name = "static-test"

    def __init__(self, candidate: dict[str, Any]) -> None:
        self.candidate = candidate

    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "candidate": dict(self.candidate),
            "provider": self.name,
            "model": "static",
            "response_id": None,
            "usage": None,
        }


class OpenAIResponsesProvider:
    name = "openai-responses"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        endpoint: str = RESPONSES_URL,
        timeout: float = 45.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "OpenAIResponsesProvider | None":
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            return None
        model = os.environ.get("AGENTTEST_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        return cls(api_key=key, model=model)

    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "store": False,
            "instructions": _INSTRUCTIONS,
            "input": json.dumps(context, sort_keys=True),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agenttest_cognition",
                    "strict": True,
                    "schema": CANDIDATE_SCHEMA,
                }
            },
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"Responses API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Responses API request failed: {exc}") from exc

        text = _extract_output_text(body)
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Responses API returned non-JSON cognition output") from exc

        return {
            "candidate": candidate,
            "provider": self.name,
            "model": self.model,
            "response_id": body.get("id"),
            "usage": body.get("usage"),
        }


def _extract_output_text(body: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if not texts:
        raise RuntimeError("Responses API returned no output_text")
    return "".join(texts)


def _evidence_catalog(state: dict[str, Any]) -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []

    def add(items: list[dict[str, Any]], kind: str, summary_key: str | None = None) -> None:
        for item in items[-6:]:
            identifier = item.get("id")
            if not identifier:
                continue
            if summary_key and isinstance(item.get(summary_key), str):
                summary = item[summary_key]
            else:
                summary = json.dumps(item, sort_keys=True)
            catalog.append(
                {
                    "id": str(identifier),
                    "kind": kind,
                    "summary": summary[:500],
                }
            )

    add(state.get("episodes", []), "episode", "content")
    add(state.get("surprises", []), "surprise")
    add(state.get("predictions", []), "prediction", "statement")
    add(state.get("intentions", []), "intention", "rationale")
    add(state.get("questions", []), "question", "text")
    add(state.get("experiments", []), "experiment", "hypothesis")
    add(state.get("reflections", []), "reflection", "lesson")
    for claim in current_world_claims(state, limit=8):
        catalog.append(
            {
                "id": claim["id"],
                "kind": "world_claim",
                "summary": (
                    f"{claim['subject']} {claim['predicate']} = "
                    f"{json.dumps(claim.get('value'), sort_keys=True)}; "
                    f"evidence={claim.get('evidence_refs', [])}"
                )[:500],
            }
        )
    return catalog[-28:]


def build_context(
    state: dict[str, Any],
    intention: dict[str, Any],
) -> dict[str, Any]:
    query = " ".join(
        [
            str(intention.get("kind", "")),
            str(intention.get("rationale", "")),
            " ".join(str(key) for key, value in state.get("drives", {}).items() if value),
        ]
    )
    return {
        "cycle": state.get("cycles", 0),
        "identity": state.get("identity", {}),
        "current_drives": state.get("drives", {}),
        "current_intention": intention,
        "self_model": state.get("self_model", {}),
        "semantic_memory": retrieve_semantic_memory(state, query, limit=8),
        "evidence": _evidence_catalog(state),
        "constraints": {
            "candidate_is_untrusted": True,
            "must_be_falsifiable": True,
            "may_not_modify_evidence": True,
            "may_not_claim_consciousness": True,
        },
    }


def known_evidence_ids(state: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in (
        "episodes",
        "surprises",
        "predictions",
        "intentions",
        "questions",
        "experiments",
        "reflections",
    ):
        for item in state.get(key, []):
            identifier = item.get("id")
            if identifier:
                ids.add(str(identifier))
    for claim in state.get("world_model", {}).get("claims", []):
        identifier = claim.get("id")
        if identifier:
            ids.add(str(identifier))
    return ids


def validate_candidate(
    candidate: dict[str, Any],
    allowed_evidence: set[str],
) -> tuple[bool, str | None]:
    if not isinstance(candidate, dict):
        return False, "candidate is not an object"

    required_strings = (
        "question",
        "hypothesis",
        "experiment",
        "falsification",
        "predicted_observation",
        "novelty_note",
    )
    for field in required_strings:
        value = candidate.get(field)
        if not isinstance(value, str) or not value.strip():
            return False, f"{field} must be a non-empty string"

    confidence = candidate.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        return False, "confidence must be numeric"
    if not 0.0 <= float(confidence) <= 1.0:
        return False, "confidence must be between 0 and 1"

    refs = candidate.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False, "evidence_refs must contain at least one evidence ID"
    if any(not isinstance(ref, str) or not ref for ref in refs):
        return False, "all evidence_refs must be non-empty strings"

    unknown = sorted(set(refs) - allowed_evidence)
    if unknown:
        return False, f"unknown evidence refs: {', '.join(unknown)}"

    return True, None


def run_cognition(
    state: dict[str, Any],
    intention: dict[str, Any],
    provider: CognitionProvider | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    provider = provider if provider is not None else OpenAIResponsesProvider.from_env()
    context = build_context(state, intention)
    context_hash = hashlib.sha256(
        json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    event = {
        "id": f"G{len(state.get('cognition_events', [])) + 1:06d}",
        "cycle": state.get("cycles", 0),
        "created_at": utc_now(),
        "prompt_version": PROMPT_VERSION,
        "context_hash": context_hash,
        "status": "unavailable",
        "provider": None,
        "model": None,
        "response_id": None,
        "usage": None,
        "rejection_reason": None,
    }

    if provider is None:
        event["rejection_reason"] = "no cognition provider configured"
        state.setdefault("cognition_events", []).append(event)
        return event, None

    try:
        result = provider.generate(context)
    except Exception as exc:
        event.update(
            {
                "status": "error",
                "provider": getattr(provider, "name", type(provider).__name__),
                "rejection_reason": str(exc)[:1000],
            }
        )
        state.setdefault("cognition_events", []).append(event)
        return event, None

    event.update(
        {
            "provider": result.get("provider", getattr(provider, "name", None)),
            "model": result.get("model"),
            "response_id": result.get("response_id"),
            "usage": result.get("usage"),
        }
    )
    candidate = result.get("candidate")
    valid, reason = validate_candidate(candidate, known_evidence_ids(state))
    if not valid:
        event["status"] = "rejected"
        event["rejection_reason"] = reason
        state.setdefault("cognition_events", []).append(event)
        return event, None

    accepted = dict(candidate)
    accepted.update(
        {
            "id": f"C{len(state.get('cognition_candidates', [])) + 1:06d}",
            "cycle": state.get("cycles", 0),
            "created_at": utc_now(),
            "source_event_id": event["id"],
            "status": "proposed",
            "provider": event["provider"],
            "model": event["model"],
        }
    )
    state.setdefault("cognition_candidates", []).append(accepted)
    event["status"] = "accepted"
    event["candidate_id"] = accepted["id"]
    state.setdefault("cognition_events", []).append(event)
    return event, accepted
