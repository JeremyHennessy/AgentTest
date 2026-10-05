from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

REGISTRY_VERSION = "native-shadow-source-registry-v1"
ATTESTATION_VERSION = "git-object-source-attestation-v1"
MANIFEST_VERSION = "native-shadow-source-manifest-v1"

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")

PINNED_OPEN_OBJECT_WORLD_SOURCE = {
    "registry_version": REGISTRY_VERSION,
    "source_id": "research.open-object-world-v0",
    "source_kind": "public_observation_stream",
    "observation_schema": "open-object-world-v0",
    "repository_full_name": "JeremyHennessy/AgentTest",
    "commit_sha": "dcb03f13ad37bcc84543bfa9f42c5be04095feb3",
    "components": [
        {
            "path": "experiments/open_object_world.py",
            "blob_sha": "f25a43b148a8009fa85a375184a484e6d54434b8",
        },
        {
            "path": "experiments/open_object_world_explorer.py",
            "blob_sha": "afafba3ff6ea59de239b071d81c36a37b5cfe0e8",
        },
    ],
    "trust_mode": "git_object_pinned_shadow",
    "activation_scope": "shadow_only",
    "signed_source": False,
    "allow_live_activation": False,
    "allow_environment_actions": False,
    "allow_action_lab": False,
    "allow_planning_lab": False,
    "allow_phase42_credit": False,
}


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounded_identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} must be a bounded identifier")
    return value


def _sha40(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HEX40.fullmatch(value):
        raise ValueError(f"{name} must be a git object SHA")
    return value


def _components(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("source registry requires pinned components")
    normalized = []
    paths = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "blob_sha"}:
            raise ValueError("source component fields do not match contract")
        path = item["path"]
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or ".." in path.split("/")
            or path in paths
        ):
            raise ValueError("source component path is invalid or duplicated")
        paths.add(path)
        normalized.append(
            {
                "path": path,
                "blob_sha": _sha40(item["blob_sha"], "component blob_sha"),
            }
        )
    return sorted(normalized, key=lambda item: item["path"])


def validate_registry_entry(entry: dict[str, Any]) -> dict[str, Any]:
    required = set(PINNED_OPEN_OBJECT_WORLD_SOURCE)
    if not isinstance(entry, dict) or set(entry) != required:
        raise ValueError("source registry entry fields do not match contract")
    if entry["registry_version"] != REGISTRY_VERSION:
        raise ValueError("unsupported source registry version")

    normalized = deepcopy(entry)
    normalized["source_id"] = _bounded_identifier(entry["source_id"], "source_id")
    if entry["source_kind"] != "public_observation_stream":
        raise ValueError("registry source must be a public observation stream")
    normalized["observation_schema"] = _bounded_identifier(
        entry["observation_schema"],
        "observation_schema",
    )
    repository = entry["repository_full_name"]
    if (
        not isinstance(repository, str)
        or repository.count("/") != 1
        or any(not part for part in repository.split("/"))
    ):
        raise ValueError("repository_full_name must be owner/repository")
    normalized["commit_sha"] = _sha40(entry["commit_sha"], "commit_sha")
    normalized["components"] = _components(entry["components"])

    if entry["trust_mode"] != "git_object_pinned_shadow":
        raise ValueError("unsupported shadow source trust mode")
    if entry["activation_scope"] != "shadow_only":
        raise ValueError("registry entry is not shadow-only")
    for field in (
        "signed_source",
        "allow_live_activation",
        "allow_environment_actions",
        "allow_action_lab",
        "allow_planning_lab",
        "allow_phase42_credit",
    ):
        if type(entry[field]) is not bool:
            raise ValueError(f"{field} must be boolean")
        if entry[field]:
            raise ValueError(f"shadow registry cannot enable {field}")

    return normalized


def registry_entry_hash(entry: dict[str, Any]) -> str:
    return canonical_sha256(validate_registry_entry(entry))


def expected_attestation(entry: dict[str, Any]) -> dict[str, Any]:
    checked = validate_registry_entry(entry)
    return {
        "version": ATTESTATION_VERSION,
        "verification_mode": "git_object_pinned_shadow",
        "registry_entry_hash": canonical_sha256(checked),
        "repository_full_name": checked["repository_full_name"],
        "commit_sha": checked["commit_sha"],
        "components": deepcopy(checked["components"]),
        "observation_schema": checked["observation_schema"],
        "signed_source": False,
        "live_activation_authorized": False,
    }


def validate_attestation(
    entry: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    expected = expected_attestation(entry)
    if not isinstance(attestation, dict) or set(attestation) != set(expected):
        raise ValueError("source attestation fields do not match contract")
    normalized = deepcopy(attestation)
    normalized["components"] = _components(attestation["components"])
    if normalized != expected:
        raise ValueError("source attestation does not match reviewed registry entry")
    return normalized


def shadow_source_manifest(
    entry: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    checked = validate_registry_entry(entry)
    verified = validate_attestation(checked, attestation)
    return {
        "version": MANIFEST_VERSION,
        "source_id": checked["source_id"],
        "source_kind": checked["source_kind"],
        "observation_schema": checked["observation_schema"],
        "registry_entry_hash": verified["registry_entry_hash"],
        "repository_full_name": checked["repository_full_name"],
        "commit_sha": checked["commit_sha"],
        "component_blobs": deepcopy(checked["components"]),
        "trust_mode": checked["trust_mode"],
        "activation_scope": "shadow_only",
        "signed_source": False,
        "allow_live_activation": False,
        "allow_environment_actions": False,
        "allow_action_lab": False,
        "allow_planning_lab": False,
        "allow_phase42_credit": False,
    }
