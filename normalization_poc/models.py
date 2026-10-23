from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalFields:
    status: str | None
    priority: str | None
    owner: str | None
    created_at: str | None
    updated_at: str | None

    def __post_init__(self) -> None:
        for name in ("status", "priority", "owner", "created_at", "updated_at"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"canonical_fields.{name} must be a string or null.")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "priority": self.priority,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class NormalizedRecord:
    parent_id: str
    source: str
    object_type: str
    title: str
    body: str
    canonical_fields: CanonicalFields
    source_fields: dict[str, Any]
    url: str | None
    acl: list[str]
    content_hash: str
    summary: str = ""
    entities: tuple[str, ...] = ()

    def with_enrichment(self, summary: str, entities: list[str]) -> NormalizedRecord:
        return NormalizedRecord(
            parent_id=self.parent_id,
            source=self.source,
            object_type=self.object_type,
            title=self.title,
            body=self.body,
            canonical_fields=self.canonical_fields,
            source_fields=self.source_fields,
            url=self.url,
            acl=self.acl,
            content_hash=self.content_hash,
            summary=summary,
            entities=tuple(entities),
        )


@dataclass(frozen=True)
class CanonicalChunk:
    id: str
    parent_id: str
    chunk_index: int
    source: str
    object_type: str
    title: str
    content: str
    context_header: str
    canonical_fields: CanonicalFields
    summary: str
    entities: list[str]
    source_fields: dict[str, Any]
    url: str | None
    content_hash: str
    acl: list[str]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "id",
            "parent_id",
            "source",
            "object_type",
            "title",
            "content",
            "context_header",
            "summary",
            "content_hash",
            "schema_version",
        ):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"Chunk field {name!r} must be a string.")
        if type(self.chunk_index) is not int or self.chunk_index < 0:
            raise ValueError("chunk_index must be a non-negative integer.")
        if not isinstance(self.canonical_fields, CanonicalFields):
            raise ValueError("canonical_fields must be a CanonicalFields value.")
        if not isinstance(self.entities, list) or any(
            not isinstance(value, str) for value in self.entities
        ):
            raise ValueError("entities must be a list of strings.")
        if not isinstance(self.source_fields, dict):
            raise ValueError("source_fields must be an object.")
        if self.url is not None and not isinstance(self.url, str):
            raise ValueError("url must be a string or null.")
        if not isinstance(self.acl, list) or any(
            not isinstance(value, str) for value in self.acl
        ):
            raise ValueError("acl must be a list of strings.")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be '1.0'.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "chunk_index": self.chunk_index,
            "source": self.source,
            "object_type": self.object_type,
            "title": self.title,
            "content": self.content,
            "context_header": self.context_header,
            "canonical_fields": self.canonical_fields.to_dict(),
            "summary": self.summary,
            "entities": self.entities,
            "source_fields": self.source_fields,
            "url": self.url,
            "content_hash": self.content_hash,
            "acl": self.acl,
            "schema_version": self.schema_version,
        }
