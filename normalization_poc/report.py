from __future__ import annotations

import html
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipeline import PipelineStats
from .vector_store import load_vector_store


def report_path_for(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_report.html")


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        value = str(value)
    return html.escape(str(value), quote=True)


def render_report(stats: PipelineStats, store: dict[str, Any]) -> str:
    chunks = store["chunks"]
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        records[chunk["parent_id"]].append(chunk)

    source_rows = []
    for source in sorted(stats.records_by_source):
        source_chunks = [chunk for chunk in chunks if chunk["source"] == source]
        record_count = stats.records_by_source[source]
        object_types = {chunk["object_type"] for chunk in source_chunks}
        source_rows.append(
            f"""
            <tr>
              <th scope="row">{_escape(source.title())}</th>
              <td>{record_count}</td>
              <td>{len(source_chunks)}</td>
              <td>{len(object_types)}</td>
            </tr>"""
        )

    record_sections = []
    for parent_id in sorted(records):
        record_chunks = sorted(records[parent_id], key=lambda item: item["chunk_index"])
        first = record_chunks[0]
        fields = first["canonical_fields"]
        entities = sorted({entity for item in record_chunks for entity in item["entities"]})
        chunk_sections = []
        for chunk in record_chunks:
            vector = chunk["embedding"]
            source_fields_html = _escape(chunk["source_fields"])
            content_html = _escape(chunk["content"]) or "<em>(empty)</em>"
            chunk_sections.append(
                f"""
                <article class="chunk">
                  <div class="chunk-heading">
                    <strong>{_escape(chunk["id"])}</strong>
                    <span>{len(vector)}-dimension embedding</span>
                  </div>
                  <p class="context">{_escape(chunk["context_header"])}</p>
                  <h4>Chunk content</h4>
                  <p>{content_html}</p>
                  <details>
                    <summary>Vectorized canonical metadata</summary>
                    <dl class="metadata">
                      <dt>Chunk index</dt><dd>{chunk["chunk_index"]}</dd>
                      <dt>Content hash</dt><dd><code>{_escape(chunk["content_hash"])}</code></dd>
                      <dt>Source URL</dt><dd>{_escape(chunk["url"])}</dd>
                      <dt>ACL metadata</dt><dd>{_escape(chunk["acl"])}</dd>
                      <dt>Source fields</dt><dd><pre>{source_fields_html}</pre></dd>
                    </dl>
                    <details>
                      <summary>Show embedding values</summary>
                      <pre>{_escape(vector)}</pre>
                    </details>
                  </details>
                </article>"""
            )
        record_sections.append(
            f"""
            <details class="record" open>
              <summary>
                <span class="record-title">{_escape(first["title"])}</span>
                <span class="badge">{_escape(first["source"])}</span>
                <span class="badge muted">{_escape(first["object_type"])}</span>
                <span class="record-key">{_escape(parent_id)}</span>
              </summary>
              <div class="record-body">
                <p>{_escape(first["summary"])}</p>
                <dl class="metadata">
                  <dt>Status</dt><dd>{_escape(fields["status"])}</dd>
                  <dt>Priority</dt><dd>{_escape(fields["priority"])}</dd>
                  <dt>Owner</dt><dd>{_escape(fields["owner"])}</dd>
                  <dt>Created</dt><dd>{_escape(fields["created_at"])}</dd>
                  <dt>Updated</dt><dd>{_escape(fields["updated_at"])}</dd>
                  <dt>Entities</dt><dd>{_escape(entities)}</dd>
                  <dt>Chunks</dt><dd>{len(record_chunks)}</dd>
                </dl>
                {"".join(chunk_sections)}
              </div>
            </details>"""
        )

    metric_cards = [
        ("Records read", stats.records_read),
        ("Enrichment cache hits", stats.cache_hits),
        ("Records enriched", stats.enrichment_calls),
        ("Chunks created", stats.chunks_created),
        ("Chunks updated", stats.chunks_updated),
        ("Chunks removed", stats.chunks_removed),
        ("Chunks in vector store", stats.total_chunks),
    ]
    cards = "".join(
        f'<div class="metric"><span>{_escape(label)}</span><strong>{value}</strong></div>'
        for label, value in metric_cards
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Normalization POC - Run Report</title>
  <style>
    :root {{ color-scheme: light; --ink:#18313b; --muted:#60737b; --line:#d8e3e6; --teal:#078b89; --paper:#f4f8f8; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font:15px/1.55 "Segoe UI",Arial,sans-serif; }}
    header {{ padding:38px max(24px,calc((100vw - 1120px)/2)); background:#12323b; color:white; }}
    header h1 {{ margin:0 0 6px; font-size:30px; }}
    header p {{ margin:0; color:#c5d7db; }}
    main {{ max-width:1120px; margin:28px auto; padding:0 20px 50px; }}
    h2 {{ margin:30px 0 14px; font-size:21px; }}
    .provider {{ display:inline-block; margin-top:16px; padding:5px 10px; border:1px solid #7cc7c2; border-radius:20px; color:#d3fffb; font-size:13px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:12px; }}
    .metric {{ padding:16px; border:1px solid var(--line); border-radius:10px; background:white; }}
    .metric span {{ display:block; color:var(--muted); font-size:13px; }}
    .metric strong {{ display:block; margin-top:5px; font-size:26px; }}
    .panel {{ overflow:hidden; border:1px solid var(--line); border-radius:10px; background:white; }}
    table {{ width:100%; border-collapse:collapse; text-align:left; }}
    th,td {{ padding:12px 16px; border-bottom:1px solid var(--line); }}
    thead {{ background:#eaf2f3; }}
    .record {{ margin:10px 0; border:1px solid var(--line); border-radius:10px; background:white; }}
    .record > summary {{ display:flex; align-items:center; flex-wrap:wrap; gap:9px; padding:14px 16px; cursor:pointer; list-style:none; }}
    .record > summary::-webkit-details-marker {{ display:none; }}
    .record-title {{ font-weight:650; }}
    .record-key {{ margin-left:auto; color:var(--muted); font:13px Consolas,monospace; }}
    .badge {{ padding:2px 8px; border-radius:20px; background:#d9f2ef; color:#075d5b; font-size:12px; }}
    .badge.muted {{ background:#edf1f3; color:#52636a; }}
    .record-body {{ padding:0 16px 16px; }}
    .metadata {{ display:grid; grid-template-columns:150px 1fr; gap:5px 14px; margin:14px 0; }}
    .metadata dt {{ color:var(--muted); }}
    .metadata dd {{ margin:0; overflow-wrap:anywhere; }}
    .chunk {{ margin-top:12px; padding:14px; border:1px solid var(--line); border-left:4px solid var(--teal); border-radius:8px; }}
    .chunk-heading {{ display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }}
    .chunk-heading span,.context {{ color:var(--muted); font-size:13px; }}
    .context {{ padding:8px 10px; background:#f3f8f8; border-radius:5px; }}
    .chunk h4 {{ margin:10px 0 3px; }}
    .chunk p {{ overflow-wrap:anywhere; }}
    .chunk details {{ margin-top:10px; }}
    summary {{ cursor:pointer; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; margin:0; }}
    code {{ overflow-wrap:anywhere; }}
    .note {{ color:var(--muted); font-size:13px; }}
    footer {{ padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; }}
    @media(max-width:600px) {{ .metadata {{ grid-template-columns:1fr; gap:1px; }} .metadata dd {{ margin-bottom:8px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Normalization POC — Run Report</h1>
    <p>Multi-source ingestion, normalization, enrichment, chunking, and local vectorization</p>
    <span class="provider">Provider: {_escape(stats.provider)} · offline mock, not a real LLM</span>
  </header>
  <main>
    <p class="note">Generated {generated_at}. Unchanged records can reuse enrichment cached by content hash.</p>
    <h2>Run summary</h2>
    <section class="metrics" aria-label="Run metrics">{cards}</section>
    <h2>Source breakdown</h2>
    <div class="panel">
      <table>
        <thead><tr><th>Source</th><th>Records read</th><th>Stored chunks</th><th>Object types</th></tr></thead>
        <tbody>{"".join(source_rows)}</tbody>
      </table>
    </div>
    <h2>Normalized records and chunks</h2>
    {"".join(record_sections) or '<p class="panel" style="padding:16px">No chunks were produced in this run.</p>'}
    <h2>Output</h2>
    <div class="panel" style="padding:16px">
      <p><strong>Vector store:</strong> <code>{_escape(stats.output_path)}</code></p>
      <p>All chunk metadata, embeddings, and enrichment-cache entries are stored in this single JSON file.</p>
      <p class="note">Embeddings are deterministic demonstration vectors. ACL values are displayed as metadata and are not enforced by this POC.</p>
    </div>
    <footer>Generated locally by the Multi-source Data Normalizer POC.</footer>
  </main>
</body>
</html>
"""


def write_report(stats: PipelineStats, output_path: Path) -> Path:
    store = load_vector_store(output_path)
    report_path = report_path_for(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=report_path.parent,
            prefix=f".{report_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = file.name
            file.write(render_report(stats, store))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, report_path)
    except OSError as exc:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise OSError(f"Could not safely write HTML run report at {report_path}: {exc}") from exc
    return report_path
