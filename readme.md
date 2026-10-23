# Multi-source Data Normalizer POC

This repository contains a small, offline proof of concept for normalizing synthetic ServiceNow, Confluence, and Jira records for a RAG ingestion pipeline. It demonstrates the data flow and local vector persistence; it does not connect to real enterprise systems or a hosted vector database.

## Pipeline

```text
ServiceNow / Confluence / Jira JSON fixtures
    -> ingest and preserve raw source fields
    -> deterministic source adapters
    -> canonical parent records and cached enrichment
    -> type-aware canonical chunks
    -> deterministic offline embeddings
    -> output/vector_store.json
```

The canonical chunk includes `id`, `parent_id`, `chunk_index`, `source`, `object_type`, `title`, `content`, `context_header`, `canonical_fields`, `summary`, `entities`, `source_fields`, `url`, `content_hash`, `acl`, and `schema_version`. Each persisted chunk also has an `embedding` vector.

## Project layout

- `data/sources/`: separate, fictional JSON fixtures for each source.
- `normalization_poc/`: adapters, typed models, enrichment, chunking, embeddings, pipeline, CLI, HTML reporting, and local store.
- `tests/`: dependency-free unit tests.
- `output/vector_store.json`: generated vector-store and enrichment-cache file, created on the first run.
- `output/vector_store_report.html`: generated detailed run report, automatically opened after a successful run.

## Prerequisites

- Python 3.10 or newer.
- No third-party packages, API keys, database, or network connection are required.

Check the installed Python version:

```powershell
python --version
```

## Setup

After cloning the repository with your usual Git client, open a terminal at the repository root. Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe --version
```

There are no dependencies to install. The project uses only the Python standard library.

## Run the POC

From the repository root:

```powershell
python -m normalization_poc
```

The command reads the three JSON fixtures from `data/sources/`, creates `output/` as needed, and writes all chunks, embeddings, and enrichment-cache entries into `output/vector_store.json`. To choose alternate locations:

```powershell
python -m normalization_poc --data-dir .\data\sources --output .\output\vector_store.json
```

The CLI reports the selected enrichment provider, records read, cache hits, enrichment calls, chunks created/updated/removed, total chunks, and the output path. After a successful run it generates `output/vector_store_report.html` and opens the detailed report in your default browser. Use `--no-open-report` to generate the report without launching a browser (for example, on a headless machine).

The HTML report includes run metrics, per-source record and chunk counts, normalized record fields, enrichment summaries and entities, chunk text and metadata, embedding dimensions, and the vector-store path. Source text is HTML-escaped before display. The report is a local generated file alongside the vector store.

### First and subsequent runs

On the first run, each record is enriched by the deterministic offline mock and its chunks are embedded and written to the vector store. On an unchanged subsequent run, enrichment results are reused by `content_hash`; existing chunks are not duplicated or needlessly updated. If a record's title or body changes, only that record needs a new enrichment result and its existing chunks are replaced. Records removed from the source fixtures have their old chunks removed from the store.

The default provider is named `deterministic-mock`. It is a transparent, repeatable placeholder and **is not a real LLM**. The provider interface can be replaced later, but this POC does not implement a real LLM provider or require LLM environment variables.

Embeddings are deterministic feature-hash vectors generated locally. They make the output shape reproducible for the POC, but are not semantic model embeddings and should not be treated as production search quality.

## Vector-store format and reset

`output/vector_store.json` is one JSON object containing:

- `schema_version`: vector-store format version.
- `chunks`: canonical chunk objects, each with an additional numeric `embedding` array.
- `enrichment_cache`: cached `summary` and `entities` indexed by stable record content hash.

Each chunk carries source metadata, normalized shared fields, original source fields, its content hash, URL and ACL metadata where provided, and a `context_header` used together with chunk text when generating its embedding. ACL values are preserved as metadata only; this POC does not enforce access control.

To avoid opening the report automatically, use:

```powershell
python -m normalization_poc --no-open-report
```

To reset generated state and force enrichment to run again, remove the generated store and report files:

```powershell
Remove-Item .\output\vector_store.json, .\output\vector_store_report.html
```

The next run recreates it. Keep the files under `data/sources/`; they are input fixtures, not generated output.

## Run tests

From the repository root:

```powershell
python -m unittest discover -s tests -v
```

Tests cover source field mapping, content hashing, enrichment cache reuse/invalidation, canonical chunk metadata, and single-file persistence. They run offline and do not use credentials.

## Limitations

- The source records are synthetic and there are no ServiceNow, Confluence, or Jira API integrations.
- Enrichment uses a deterministic mock, not a language model. No real LLM provider is included.
- The feature-hash embedding is for demonstrating the pipeline and is not a semantic embedding model.
- The JSON file is a lightweight local POC store, not a production vector database; it does not provide vector indexing, concurrent-writer coordination, authentication, or ACL enforcement.
