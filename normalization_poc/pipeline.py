from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import load_source_file
from .embeddings import deterministic_embedding
from .enrichment import DeterministicMockEnrichment, EnrichmentProvider
from .models import NormalizedRecord
from .chunking import chunk_record
from .vector_store import load_vector_store, save_vector_store


@dataclass(frozen=True)
class PipelineStats:
    records_read: int
    records_by_source: dict[str, int]
    cache_hits: int
    enrichment_calls: int
    chunks_created: int
    chunks_updated: int
    chunks_removed: int
    total_chunks: int
    output_path: str
    provider: str


def _record_with_cached_enrichment(
    record: NormalizedRecord,
    cache: dict[str, Any],
    provider: EnrichmentProvider,
) -> tuple[NormalizedRecord, bool]:
    cached = cache.get(record.content_hash)
    if cached is not None:
        if (
            not isinstance(cached, dict)
            or not isinstance(cached.get("summary"), str)
            or not isinstance(cached.get("entities"), list)
            or any(not isinstance(entity, str) for entity in cached["entities"])
        ):
            raise ValueError(f"Invalid enrichment cache entry for {record.content_hash}.")
        return record.with_enrichment(cached["summary"], cached["entities"]), False
    result = provider.enrich(record)
    if not isinstance(result.summary, str) or any(
        not isinstance(entity, str) for entity in result.entities
    ):
        raise ValueError(f"Enrichment provider {provider.name!r} returned invalid output.")
    cache[record.content_hash] = {
        "summary": result.summary,
        "entities": result.entities,
    }
    return record.with_enrichment(result.summary, result.entities), True


def run_pipeline(
    source_files: dict[str, Path],
    output_path: Path,
    provider: EnrichmentProvider | None = None,
) -> PipelineStats:
    if not source_files:
        raise ValueError("At least one source fixture must be configured.")
    provider = provider or DeterministicMockEnrichment()
    records_by_source = {
        source: load_source_file(source, path)
        for source, path in source_files.items()
    }
    store = load_vector_store(output_path)
    cache: dict[str, Any] = dict(store["enrichment_cache"])
    existing_chunks = {entry["id"]: entry for entry in store["chunks"]}
    new_entries: list[dict[str, Any]] = []
    cache_hits = 0
    enrichment_calls = 0
    chunks_created = 0
    chunks_updated = 0
    active_sources = set(source_files)

    for source, records in records_by_source.items():
        for record in records:
            enriched_record, called_provider = _record_with_cached_enrichment(
                record, cache, provider
            )
            if called_provider:
                enrichment_calls += 1
            else:
                cache_hits += 1
            for chunk in chunk_record(enriched_record):
                chunk_data = chunk.to_dict()
                chunk_data["embedding"] = deterministic_embedding(
                    f"{chunk.context_header}\n{chunk.content}"
                )
                previous = existing_chunks.get(chunk.id)
                if previous is None:
                    chunks_created += 1
                elif previous != chunk_data:
                    chunks_updated += 1
                new_entries.append(chunk_data)

    retained_entries = [
        entry
        for entry in existing_chunks.values()
        if entry.get("source") not in active_sources
    ]
    previous_active_ids = {
        chunk_id
        for chunk_id, entry in existing_chunks.items()
        if entry.get("source") in active_sources
    }
    current_ids = {entry["id"] for entry in new_entries}
    chunks_removed = len(previous_active_ids - current_ids)
    final_entries = retained_entries + new_entries
    final_entries.sort(key=lambda entry: (entry["source"], entry["parent_id"], entry["chunk_index"]))
    new_store = {
        "schema_version": "1.0",
        "chunks": final_entries,
        "enrichment_cache": cache,
    }
    save_vector_store(output_path, new_store)
    return PipelineStats(
        records_read=sum(len(records) for records in records_by_source.values()),
        records_by_source={
            source: len(records) for source, records in records_by_source.items()
        },
        cache_hits=cache_hits,
        enrichment_calls=enrichment_calls,
        chunks_created=chunks_created,
        chunks_updated=chunks_updated,
        chunks_removed=chunks_removed,
        total_chunks=len(final_entries),
        output_path=str(output_path),
        provider=provider.name,
    )
