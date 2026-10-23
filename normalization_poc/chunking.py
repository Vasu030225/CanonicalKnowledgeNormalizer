from __future__ import annotations

import re

from .models import CanonicalChunk, NormalizedRecord


CHUNK_WORD_LIMITS = {
    "incident": 48,
    "issue": 64,
    "bug": 64,
    "task": 64,
    "page": 80,
}


def _split_text(text: str, word_limit: int) -> list[str]:
    words = re.findall(r"\S+", text)
    if not words:
        return [""]
    return [
        " ".join(words[index : index + word_limit])
        for index in range(0, len(words), word_limit)
    ]


def chunk_record(record: NormalizedRecord) -> list[CanonicalChunk]:
    body = record.body.strip() or record.summary
    word_limit = CHUNK_WORD_LIMITS.get(record.object_type, 64)
    pieces = _split_text(body, word_limit)
    chunks: list[CanonicalChunk] = []
    status = record.canonical_fields.status
    header_parts = [record.source.title(), record.parent_id, record.title]
    if status:
        header_parts.append(status)
    context_header = " - ".join(header_parts)
    for index, content in enumerate(pieces):
        chunks.append(
            CanonicalChunk(
                id=f"{record.parent_id}#chunk-{index}",
                parent_id=record.parent_id,
                chunk_index=index,
                source=record.source,
                object_type=record.object_type,
                title=record.title,
                content=content,
                context_header=context_header,
                canonical_fields=record.canonical_fields,
                summary=record.summary,
                entities=list(record.entities),
                source_fields=record.source_fields,
                url=record.url,
                content_hash=record.content_hash,
                acl=record.acl,
            )
        )
    return chunks
