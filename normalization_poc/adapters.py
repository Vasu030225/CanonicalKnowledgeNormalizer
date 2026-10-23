from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .models import CanonicalFields, NormalizedRecord


class SourceDataError(ValueError):
    """Raised when a source fixture is missing or malformed."""


def stable_content_hash(source: str, object_type: str, title: str, body: str) -> str:
    payload = {
        "source": source,
        "object_type": object_type,
        "title": title,
        "body": body,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _normalize_date(value: Any, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SourceDataError(f"{field_name} must be an ISO-8601 string or null.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceDataError(f"{field_name} has invalid ISO-8601 value {value!r}.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_status(value: Any, mapping: dict[str, str]) -> str | None:
    if value is None or value == "":
        return None
    return mapping.get(str(value).strip().lower(), "unknown")


def _normalize_priority(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if " - " in text:
        text = text.split(" - ", 1)[1].strip()
    for key, normalized in (
        ("critical", "critical"),
        ("highest", "critical"),
        ("blocker", "critical"),
        ("high", "high"),
        ("major", "high"),
        ("moderate", "medium"),
        ("medium", "medium"),
        ("normal", "medium"),
        ("low", "low"),
        ("minor", "low"),
        ("lowest", "low"),
    ):
        if key in text:
            return normalized
    return "unknown"


def _string_field(record: dict[str, Any], field: str, *, required: bool = False) -> str:
    value = record.get(field)
    if not isinstance(value, str) or (required and not value.strip()):
        if required:
            raise SourceDataError(f"Required field {field!r} must be a non-empty string.")
        if value is None:
            return ""
        raise SourceDataError(f"Field {field!r} must be a string.")
    return value.strip()


def _acl(record: dict[str, Any]) -> list[str]:
    value = record.get("acl", [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SourceDataError("Field 'acl' must be a list of strings.")
    return list(value)


def _map_record(
    source: str,
    object_type: str,
    source_id: str,
    title: str,
    body: str,
    raw: dict[str, Any],
    *,
    status: str | None,
    priority: Any,
    owner: Any,
    created_at: Any,
    updated_at: Any,
) -> NormalizedRecord:
    if not source_id.strip():
        raise SourceDataError("Source record ID must not be empty.")
    if owner is not None and not isinstance(owner, str):
        raise SourceDataError(f"Owner for {source}:{source_id} must be a string or null.")
    url = raw.get("url")
    if url is not None and not isinstance(url, str):
        raise SourceDataError(f"URL for {source}:{source_id} must be a string or null.")
    return NormalizedRecord(
        parent_id=f"{source}:{source_id}",
        source=source,
        object_type=object_type,
        title=title,
        body=body,
        canonical_fields=CanonicalFields(
            status=status,
            priority=_normalize_priority(priority),
            owner=owner,
            created_at=_normalize_date(created_at, f"{source}:{source_id}.created_at"),
            updated_at=_normalize_date(updated_at, f"{source}:{source_id}.updated_at"),
        ),
        source_fields=dict(raw),
        url=url,
        acl=_acl(raw),
        content_hash=stable_content_hash(source, object_type, title, body),
    )


def adapt_servicenow(raw: dict[str, Any]) -> NormalizedRecord:
    if not isinstance(raw, dict):
        raise SourceDataError("Each ServiceNow record must be a JSON object.")
    statuses = {
        "new": "open",
        "open": "open",
        "in progress": "in_progress",
        "work in progress": "in_progress",
        "resolved": "resolved",
        "closed": "closed",
        "cancelled": "closed",
    }
    return _map_record(
        "servicenow",
        "incident",
        _string_field(raw, "number", required=True),
        _string_field(raw, "short_description", required=True),
        _string_field(raw, "description"),
        raw,
        status=_normalize_status(raw.get("state"), statuses),
        priority=raw.get("priority"),
        owner=raw.get("assigned_to"),
        created_at=raw.get("opened_at"),
        updated_at=raw.get("sys_updated_on"),
    )


def adapt_confluence(raw: dict[str, Any]) -> NormalizedRecord:
    if not isinstance(raw, dict):
        raise SourceDataError("Each Confluence record must be a JSON object.")
    statuses = {
        "current": "resolved",
        "published": "resolved",
        "draft": "open",
        "archived": "closed",
    }
    return _map_record(
        "confluence",
        "page",
        _string_field(raw, "id", required=True),
        _string_field(raw, "title", required=True),
        _string_field(raw, "body"),
        raw,
        status=_normalize_status(raw.get("status"), statuses),
        priority=raw.get("priority"),
        owner=raw.get("owner"),
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
    )


def adapt_jira(raw: dict[str, Any]) -> NormalizedRecord:
    if not isinstance(raw, dict):
        raise SourceDataError("Each Jira record must be a JSON object.")
    statuses = {
        "to do": "open",
        "open": "open",
        "backlog": "open",
        "in progress": "in_progress",
        "in review": "in_progress",
        "done": "resolved",
        "resolved": "resolved",
        "closed": "closed",
    }
    return _map_record(
        "jira",
        _string_field(raw, "issue_type", required=True).lower(),
        _string_field(raw, "key", required=True),
        _string_field(raw, "summary", required=True),
        _string_field(raw, "description"),
        raw,
        status=_normalize_status(raw.get("status"), statuses),
        priority=raw.get("priority"),
        owner=raw.get("assignee"),
        created_at=raw.get("created"),
        updated_at=raw.get("updated"),
    )


ADAPTERS: dict[str, Callable[[dict[str, Any]], NormalizedRecord]] = {
    "servicenow": adapt_servicenow,
    "confluence": adapt_confluence,
    "jira": adapt_jira,
}


def load_source_file(source: str, path: Path) -> list[NormalizedRecord]:
    try:
        with path.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except OSError as exc:
        raise SourceDataError(f"Cannot read {source} fixture at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SourceDataError(f"Invalid JSON in {source} fixture at {path}: {exc}") from exc
    if not isinstance(records, list):
        raise SourceDataError(f"{source} fixture at {path} must contain a JSON array.")
    adapter = ADAPTERS[source]
    return [adapter(record) for record in records]
