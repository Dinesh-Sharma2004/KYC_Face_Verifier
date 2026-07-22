"""Client-side gateway utilities for the Streamlit KYC console.

The frontend is intentionally a thin central control plane. It can route work
to one or more backend nodes while keeping a local customer/job ledger for
operators who need to manage many customers from a single screen.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

import requests


DEFAULT_NODES = [
    {
        "name": "Unified Extractor",
        "url": "http://127.0.0.1:8000",
        "kind": "unified",
        "api_key": "secret123",
    },
    {
        "name": "PAN Aadhaar OCR",
        "url": "http://127.0.0.1:8000",
        "kind": "legacy_kyc",
        "api_key": "secret123",
    },
]

KNOWN_NODE_KINDS = {"unified", "legacy_kyc", "face"}


@dataclass(frozen=True)
class BackendNode:
    name: str
    url: str
    kind: str = "unified"
    api_key: str = ""

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def stable_customer_id(name: str, external_id: str = "") -> str:
    seed = f"{name.strip().lower()}::{external_id.strip().lower()}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    label = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "customer"
    return f"{label}-{digest}"


def document_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def mask_identifier(value: Any, visible: int = 4) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return f"{'*' * (len(text) - visible)}{text[-visible:]}"


def parse_nodes(raw_config: str | None = None) -> list[BackendNode]:
    """Parse backend nodes from JSON or newline CSV config.

    JSON form:
    [{"name": "Node A", "url": "http://localhost:8000", "kind": "unified", "api_key": "secret123"}]

    CSV form:
    Node A,http://localhost:8000,unified,secret123
    """

    raw = (raw_config or "").strip()
    if not raw:
        return [BackendNode(**node) for node in DEFAULT_NODES]

    items: list[Mapping[str, Any]]
    if raw.startswith("["):
        decoded = json.loads(raw)
        if not isinstance(decoded, list):
            raise ValueError("Node JSON config must be a list.")
        items = decoded
    else:
        items = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 2:
                raise ValueError(f"Invalid node config line: {line}")
            items.append(
                {
                    "name": parts[0],
                    "url": parts[1],
                    "kind": parts[2] if len(parts) > 2 and parts[2] else "unified",
                    "api_key": parts[3] if len(parts) > 3 else "",
                }
            )

    nodes = []
    for item in items:
        kind = str(item.get("kind") or "unified")
        if kind not in KNOWN_NODE_KINDS:
            raise ValueError(f"Unsupported backend node kind: {kind}")
        nodes.append(
            BackendNode(
                name=str(item.get("name") or item.get("url") or "Backend Node"),
                url=str(item["url"]),
                kind=kind,
                api_key=str(item.get("api_key") or ""),
            )
        )
    return nodes


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"customers": {}, "jobs": []}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("customers", {})
    data.setdefault("jobs", [])
    return data


def save_ledger(path: Path, ledger: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(ledger, handle, indent=2, default=str)
    tmp_path.replace(path)


def record_customer(ledger: dict[str, Any], customer: Mapping[str, Any]) -> None:
    customer_id = str(customer["customer_id"])
    existing = ledger.setdefault("customers", {}).get(customer_id, {})
    merged = {**existing, **dict(customer), "updated_at": utc_now_iso()}
    merged.setdefault("created_at", utc_now_iso())
    ledger["customers"][customer_id] = merged


def append_job(ledger: dict[str, Any], job: Mapping[str, Any]) -> None:
    ledger.setdefault("jobs", []).insert(0, dict(job))


def flatten_profiles(payload: Any) -> list[dict[str, Any]]:
    """Normalize legacy and unified backend responses into customer profiles."""

    if payload is None:
        return []
    if isinstance(payload, list):
        return [profile for profile in payload if isinstance(profile, dict)]
    if isinstance(payload, dict):
        profiles = payload.get("extracted_user_profiles")
        if isinstance(profiles, dict):
            return [profile for profile in profiles.values() if isinstance(profile, dict)]
        if isinstance(profiles, list):
            return [profile for profile in profiles if isinstance(profile, dict)]
        if "documents" in payload:
            return [payload]
    return []


def iter_document_records(payload: Any) -> Iterable[dict[str, Any]]:
    for profile in flatten_profiles(payload):
        documents = profile.get("documents") or {}
        if isinstance(documents, dict):
            for doc_type, document in documents.items():
                if isinstance(document, dict):
                    merged = dict(document)
                    merged.setdefault("document_type", doc_type)
                    yield merged
        for key in ("aadhaar_card", "pan_card"):
            document = profile.get(key)
            if isinstance(document, dict):
                merged = dict(document)
                merged.setdefault("document_type", key)
                yield merged

    if isinstance(payload, dict):
        raw_results = payload.get("raw_document_results") or []
        if isinstance(raw_results, list):
            for result in raw_results:
                if isinstance(result, dict):
                    yield result


def _extract_field(document: Mapping[str, Any], *field_names: str) -> Any:
    candidates: list[Mapping[str, Any]] = [document]
    extracted = document.get("extracted_data")
    if isinstance(extracted, Mapping):
        candidates.append(extracted)
    for nested_name in ("front_data", "back_data"):
        nested = document.get(nested_name)
        if isinstance(nested, Mapping):
            candidates.append(nested)

    for candidate in candidates:
        for field_name in field_names:
            value = candidate.get(field_name)
            if value not in (None, ""):
                return value
    return None


def build_verification_summary(
    client_payload: Any,
    kyc_payload: Any,
    expected_name: str = "",
) -> dict[str, Any]:
    client_docs = list(iter_document_records(client_payload))
    kyc_docs = list(iter_document_records(kyc_payload))

    aadhaar = next((_extract_field(doc, "aadhaar_number") for doc in kyc_docs if _extract_field(doc, "aadhaar_number")), None)
    pan = next((_extract_field(doc, "pan_number") for doc in kyc_docs if _extract_field(doc, "pan_number")), None)
    names = [
        str(value).strip()
        for doc in [*client_docs, *kyc_docs]
        for value in [_extract_field(doc, "full_name_en", "full_name", "name", "customer_name")]
        if value
    ]

    normalized_expected = expected_name.strip().casefold()
    normalized_names = {name.casefold() for name in names}
    name_matched = bool(normalized_expected and normalized_expected in normalized_names)
    if not name_matched and len(normalized_names) == 1 and normalized_names:
        name_matched = True

    kyc_complete = bool(aadhaar or pan)
    checks = {
        "client_documents_processed": len(client_docs),
        "kyc_documents_processed": len(kyc_docs),
        "aadhaar_found": bool(aadhaar),
        "pan_found": bool(pan),
        "name_matched": name_matched,
    }
    score = sum(1 for value in checks.values() if bool(value))
    status = "verified" if kyc_complete and (name_matched or not expected_name) else "review_required"

    return {
        "status": status,
        "score": score,
        "checks": checks,
        "identity": {
            "names": sorted(set(names)),
            "aadhaar_number": mask_identifier(aadhaar),
            "pan_number": mask_identifier(pan),
        },
    }


class KycGateway:
    def __init__(self, node: BackendNode, timeout: int = 120):
        self.node = node
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        response = requests.get(f"{self.node.base_url}/health", timeout=10)
        response.raise_for_status()
        return response.json()

    def submit(self, files: list[tuple[str, bytes, str]], metadata: list[dict[str, Any]] | None = None) -> dict[str, Any] | list[Any]:
        headers = {"X-API-KEY": self.node.api_key} if self.node.api_key else {}
        multipart = [("files", (filename, content, mime_type)) for filename, content, mime_type in files]

        if self.node.kind == "legacy_kyc":
            response = requests.post(
                f"{self.node.base_url}/process",
                files=multipart,
                headers=headers,
                timeout=self.timeout,
            )
        else:
            data = {"metadata": json.dumps(metadata or [])}
            response = requests.post(
                f"{self.node.base_url}/user_profile",
                files=multipart,
                data=data,
                headers=headers,
                timeout=self.timeout,
            )

        response.raise_for_status()
        return response.json()


def new_job_id() -> str:
    return str(uuid4())
