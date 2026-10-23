from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import CanonicalChunk, CanonicalFields


CHUNK_FIELDS = (
    "id",
    "parent_id",
    "chunk_index",
    "source",
    "object_type",
    "title",
    "content",
    "context_header",
    "canonical_fields",
    "summary",
    "entities",
    "source_fields",
    "url",
    "content_hash",
    "acl",
    "schema_version",
)


class VectorStoreError(ValueError):
    """Raised when the persisted vector store is invalid or cannot be saved."""


def empty_store() -> dict[str, Any]:
    return {"schema_version": "1.0", "chunks": [], "enrichment_cache": {}}


def load_vector_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_store()
    try:
        with path.open("r", encoding="utf-8") as file:
            store = json.load(file)
    except OSError as exc:
        raise VectorStoreError(f"Cannot read vector store at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VectorStoreError(f"Vector store at {path} is not valid JSON: {exc}") from exc
    if not isinstance(store, dict):
        raise VectorStoreError(f"Vector store at {path} must contain a JSON object.")
    if store.get("schema_version") != "1.0":
        raise VectorStoreError(f"Vector store at {path} has an unsupported schema_version.")
    chunks = store.get("chunks")
    cache = store.get("enrichment_cache")
    if not isinstance(chunks, list) or not isinstance(cache, dict):
        raise VectorStoreError(
            f"Vector store at {path} must contain 'chunks' (array) and 'enrichment_cache' (object)."
        )
    for index, entry in enumerate(chunks):
        if not isinstance(entry, dict) or not isinstance(entry.get("embedding"), list):
            raise VectorStoreError(f"Vector store chunk at index {index} is missing its embedding.")
        if not all(field in entry for field in CHUNK_FIELDS):
            raise VectorStoreError(f"Vector store chunk at index {index} is missing canonical fields.")
        try:
            chunk_data = {field: entry[field] for field in CHUNK_FIELDS}
            chunk_data["canonical_fields"] = CanonicalFields(**chunk_data["canonical_fields"])
            CanonicalChunk(**chunk_data)
        except (TypeError, ValueError) as exc:
            raise VectorStoreError(
                f"Vector store chunk at index {index} does not match the canonical schema: {exc}"
            ) from exc
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in entry["embedding"]
        ):
            raise VectorStoreError(f"Vector store chunk at index {index} has a non-numeric embedding.")
    return store


def save_vector_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = file.name
            json.dump(store, file, indent=2, ensure_ascii=False, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise VectorStoreError(f"Cannot safely write vector store at {path}: {exc}") from exc
