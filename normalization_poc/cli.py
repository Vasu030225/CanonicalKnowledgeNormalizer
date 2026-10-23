from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .adapters import ADAPTERS
from .pipeline import run_pipeline
from .report import write_report


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the offline multi-source normalization POC."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "sources",
        help="Directory containing servicenow.json, confluence.json, and jira.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "vector_store.json",
        help="Path for the single-file vector store.",
    )
    parser.add_argument(
        "--no-open-report",
        action="store_true",
        help="Generate the HTML report without opening it in a browser.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_files = {
        source: args.data_dir / f"{source}.json"
        for source in ADAPTERS
    }
    try:
        stats = run_pipeline(source_files, args.output)
        report_path = write_report(stats, args.output)
    except (OSError, ValueError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(f"Enrichment provider: {stats.provider} (offline; not a real LLM)")
    print(f"Records read: {stats.records_read}")
    print(f"Cache hits (unchanged records): {stats.cache_hits}")
    print(f"Records enriched: {stats.enrichment_calls}")
    print(f"Chunks created: {stats.chunks_created}")
    print(f"Chunks updated: {stats.chunks_updated}")
    print(f"Chunks removed: {stats.chunks_removed}")
    print(f"Total chunks: {stats.total_chunks}")
    print(f"Vector store: {stats.output_path}")
    print(f"HTML report: {report_path}")
    if not args.no_open_report:
        try:
            opened = webbrowser.open(report_path.resolve().as_uri())
        except (OSError, webbrowser.Error) as exc:
            print(
                f"Could not open the HTML report automatically: {exc}. "
                f"Open it manually at {report_path.resolve()}",
                file=sys.stderr,
            )
        else:
            if opened:
                print("Opened the detailed HTML report in your default browser.")
            else:
                print(
                    f"Could not open a browser automatically. Open the report manually at "
                    f"{report_path.resolve()}",
                    file=sys.stderr,
                )
    return 0
