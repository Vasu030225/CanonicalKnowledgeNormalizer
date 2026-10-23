---
name: Build Python Normalization POC
description: "Build a Python proof of concept for an LLM-powered normalization pipeline using separate ServiceNow, Confluence, and Jira dummy-data files."
argument-hint: "Optional: add constraints such as Python version, fields, or LLM provider"
agent: agent
---

Build a working Python proof of concept in the current workspace for the architecture below. First inspect the existing files and conventions, then implement the POC, run the relevant checks, and summarize how to run it.

## Goal

Demonstrate an LLM-powered normalization layer that converts records from multiple enterprise sources into the canonical chunk schema specified below, enriches them, embeds them, and persists the vector store locally. This is a POC: use synthetic data and do not connect to real enterprise systems or external services.

## Pipeline to implement

`Source systems -> Ingest & land (retain raw records) -> Normalize -> Canonical chunk records -> Embedding -> Vector DB`

The normalization stage must include both:

1. **Deterministic adapters** that map each source's fields to the shared canonical chunk schema.
2. **LLM enrichment** that produces a concise summary and entities for each record.

Only new or changed record content should require LLM enrichment. Cache enrichment by a stable content hash so rerunning the pipeline on unchanged input reuses the prior result. A changed record should be enriched again.

## Required canonical chunk schema

Follow the canonical schema in the provided architecture image. It is the target output format; do not substitute a different or generic canonical-record schema. Each vectorized chunk must have this shape:

```json
{
  "id": "jira:PROJ-123#chunk-2",
  "parent_id": "jira:PROJ-123",
  "chunk_index": 2,
  "source": "jira",
  "object_type": "issue",
  "title": "Login fails after SSO",
  "content": "Text for this chunk...",
  "context_header": "Jira - PROJ-123 - Login fails after SSO - resolved",
  "canonical_fields": {
    "status": "resolved",
    "priority": "high",
    "owner": "jane.doe",
    "created_at": "2026-01-10T00:00:00Z",
    "updated_at": "2026-01-21T00:00:00Z"
  },
  "summary": "Concise summary...",
  "entities": ["SSO", "token cache"],
  "source_fields": {"source_specific_field": "original value"},
  "url": "https://example.invalid/issues/PROJ-123",
  "content_hash": "sha256:...",
  "acl": ["group:eng-platform"],
  "schema_version": "1.0"
}
```

- Keep these field names and their meanings consistent for every source. `id` must be stable and unique per chunk; derive `parent_id` stably from source plus source record ID, and use a zero-based `chunk_index` so chunks can be reassembled and deduplicated.
- `source` identifies ServiceNow, Confluence, or Jira; `object_type` identifies the source object kind (for example, incident, page, or issue). `title` is the record title and `content` is that chunk's text.
- `context_header` must be prepended to the text passed to the embedding provider so a chunk retains its source, record key, title, and available status context even when retrieved alone.
- `canonical_fields` holds the shared normalized `status`, `priority`, `owner`, `created_at`, and `updated_at` fields. Map source-specific values to consistent shared enums where appropriate, and serialize available dates as ISO-8601 UTC strings. Represent unavailable values consistently as `null`; do not invent values.
- `summary` and `entities` are enrichment outputs. Generate them from source record text, and cache them by the stable `content_hash`. Keep `source_fields` as the original source-specific fields needed for traceability or re-mapping; do not overwrite them with normalized values.
- Preserve the source `url` when present; otherwise use `null`. Preserve source access-control information in `acl` when present; otherwise use an empty list. The POC must carry ACL metadata through to every chunk, even though it does not implement real authentication or access enforcement.
- Compute `content_hash` deterministically from the record's relevant source content and fields used for enrichment, independent of JSON key order. Use the same record hash for its chunks so an unchanged record can be detected and a changed record can replace all prior chunks.
- Include `schema_version` with value `"1.0"` on every chunk. Store the numeric embedding alongside each chunk in the vector-store file (for example, as an `embedding` field on the stored chunk entry); embedding is vector-store data, not a replacement for or alteration of the canonical chunk schema.
- Use typed models and validate required fields and types. Keep any internal parent-record representation as an implementation detail; serialize vectorized chunks using the schema above.

## Required project structure

Use this structure as the target layout when the repository does not already have an established Python structure. Preserve existing project conventions where they exist, but do not leave the layout implicit:

```text
.
├── .github/
│   └── prompts/
│       └── python-normalization-poc.prompt.md
├── data/
│   └── sources/
│       ├── servicenow.json
│       ├── confluence.json
│       └── jira.json
├── normalization_poc/
│   ├── __init__.py
│   ├── __main__.py
│   ├── adapters.py
│   ├── chunking.py
│   ├── cli.py
│   ├── embeddings.py
│   ├── enrichment.py
│   ├── models.py
│   ├── pipeline.py
│   ├── report.py
│   └── vector_store.py
├── output/
│   ├── vector_store.json   # generated by the pipeline; all vectors and cache in this one file
│   └── vector_store_report.html  # generated detailed HTML run report
├── tests/
│   ├── test_adapters.py
│   ├── test_hashing.py
│   ├── test_pipeline.py
│   └── test_vector_store.py
└── readme.md
```

- Keep each source's raw synthetic fixture in its own file under `data/sources/`; adapters must load these files without modifying them.
- Keep the implementation in the `normalization_poc/` package. Separate the canonical data types, per-source adapters, enrichment provider, chunking, embeddings, persistence, orchestration, and CLI into the corresponding modules shown above. Add a module only when needed; do not collapse distinct pipeline responsibilities into one large script.
- Create `output/` at runtime if it does not exist. The vector store and enrichment cache must be persisted together in `output/vector_store.json`; do not create per-source vector-store files. The JSON file is generated state, not an input fixture.
- After each successful run, generate a detailed standalone HTML report at `output/vector_store_report.html` containing run statistics, per-source breakdowns, normalized record details, enrichment results, chunk metadata, and embedding dimensions. Automatically open the report in the default browser; provide a `--no-open-report` CLI flag for headless use, while still generating the report.
- Treat the existing root `readme.md` as the primary user guide and expand it into the complete setup and run guide for the finished POC; preserve its project description and do not create a duplicate README.
- The README must be self-contained and include: project purpose and pipeline overview; prerequisites (supported Python version and any required tools); setup from a fresh clone, including whether a virtual environment or dependency installation is needed; exact commands to run the POC from the repository root and run the tests; what the first and repeated runs do; the expected CLI statistics and generated output path; an explanation of the single-file vector-store JSON and canonical chunk entries; how to use the offline mock enrichment and any optional real-LLM configuration, including required environment variables and clear failure behavior if supported; how content-hash caching works; how to reset generated state safely; and POC limitations.
- Ensure every documented command matches the implemented package, CLI flags, test runner, and repository layout. Verify the setup, run, and test commands before documenting them; do not describe optional dependencies, providers, or capabilities that were not implemented.
- Provide a package entry point so the documented command from the project root is `python -m normalization_poc`. Use the standard library's `unittest` runner for a dependency-free test command: `python -m unittest discover -s tests -v`.

## Inputs and synthetic source data

- Create a separate, clearly named dummy-data file for each source: ServiceNow, Confluence, and Jira. Prefer small, readable JSON fixtures unless the existing project already establishes another suitable format.
- Include several realistic but entirely fictional records per source, with source-specific fields and enough variation to exercise field mapping, record types, missing optional fields, and changed-content handling.
- Keep original input records available to the pipeline; do not overwrite or silently discard source fields.
- Do not include credentials, personal data, or data copied from real systems.

## Canonical records and normalization

- Define and document typed models for the canonical chunk schema above. Source adapters must map each raw source record into shared normalized parent fields, then chunking must emit canonical chunk records with the exact required field names. Do not use the earlier generic record schema as a second persisted canonical format.
- Keep source-specific mapping in clear, testable deterministic adapters rather than scattering conditionals throughout the pipeline.
- Make LLM enrichment replaceable behind a small provider/interface boundary.
- The default run must work offline, without API keys, network access, or paid services. Provide a clearly identified deterministic mock enrichment provider for that mode. If a real provider is supported, make it opt-in through configuration/environment variables and report missing configuration clearly; never silently claim the mock is a real LLM.
- Ensure that the hash covers the content relevant to enrichment, is stable across runs, and does not change because of irrelevant serialization details such as dictionary key order.

## Chunking, embeddings, and local vector store

- Chunk normalized parent content with a type-aware strategy that can use `object_type`, title, body, and summary; emit the required canonical chunk schema for every chunk and preserve its parent/source metadata.
- Generate repeatable embeddings suitable for demonstrating vector search. If no local embedding provider is already available, use a documented deterministic offline embedding implementation and keep it behind a replaceable interface. Do not require credentials or network calls for the default run.
- Treat a single local file as the POC's Vector DB: write **all vectorized chunks, embeddings, associated metadata, and the content-hash enrichment cache to one file under `output/`** (for example, `output/vector_store.json`). Do not spread vector data across per-source output files.
- Make repeated runs idempotent: unchanged records reuse enrichment and do not create duplicate chunks; changed records replace/update their prior vectorized representation. Persist the store safely so an interrupted write does not leave a partially written JSON document.
- Keep raw source fixtures separate from generated output. Ensure the output directory is created as needed and explain how to reset generated state.

## Usability and quality

- Provide a simple command-line entry point to run the pipeline from the project root.
- Generate and automatically open a detailed HTML report after a successful CLI run; document the report path and the option to suppress browser opening.
- Report useful run statistics, including records read, unchanged records/cache hits, records sent for enrichment, chunks created or updated, and the vector-store output path.
- Add focused tests for source adapters, stable hashing, cache reuse and invalidation, chunk metadata, and single-file persistence. Tests must not require network access or secrets.
- Add or update concise project documentation with setup, run, test, output-file format, and the mock-versus-real LLM behavior.
- Follow existing project conventions and keep the implementation small and understandable. If the repository is empty, choose a simple standard-library-first Python layout and avoid adding dependencies unless they materially improve the POC.
- Handle malformed input and persistence/provider errors explicitly with actionable messages; do not silently fall back or emit success-shaped output after a failure.

## Acceptance criteria

1. The complete pipeline runs locally from the documented command with only synthetic fixtures and no external credentials.
2. ServiceNow, Confluence, and Jira inputs are stored in separate files and map into the exact canonical chunk schema described above.
3. A second run with unchanged inputs reports cache reuse and makes no additional enrichment calls.
4. Editing a record's relevant content invalidates only that record's enrichment and updates its vectors without duplicating its chunks.
5. All canonical chunk records, their embeddings, and the enrichment cache are persisted in one file under `output/`.
6. Focused tests pass, the CLI creates the detailed HTML report and opens it by default (with a tested headless option), and the root `readme.md` contains verified, step-by-step setup, run, test, output, reset, and provider instructions that accurately describe the POC and its limitations.

Do not replace this architecture with a production integration, hosted vector database, or mandatory external LLM. Implement the smallest end-to-end POC that demonstrates the full flow above.
