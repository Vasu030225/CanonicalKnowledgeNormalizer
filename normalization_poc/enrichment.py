from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .models import NormalizedRecord


@dataclass(frozen=True)
class Enrichment:
    summary: str
    entities: list[str]


class EnrichmentProvider(Protocol):
    name: str

    def enrich(self, record: NormalizedRecord) -> Enrichment:
        """Return summary and entities for a normalized source record."""


class DeterministicMockEnrichment:
    """Offline placeholder; this provider does not call or represent a real LLM."""

    name = "deterministic-mock"

    def enrich(self, record: NormalizedRecord) -> Enrichment:
        text = " ".join((record.title, record.body)).strip()
        summary = re.sub(r"\s+", " ", text)
        if len(summary) > 240:
            summary = summary[:237].rsplit(" ", 1)[0] + "..."
        candidates = re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b|\b[A-Z]{2,}\b", text)
        entities: list[str] = []
        for candidate in candidates:
            if candidate not in entities:
                entities.append(candidate)
            if len(entities) == 8:
                break
        return Enrichment(summary=summary, entities=entities)
