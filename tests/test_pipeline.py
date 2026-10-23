import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from normalization_poc import cli
from normalization_poc.enrichment import DeterministicMockEnrichment
from normalization_poc.pipeline import PipelineStats, run_pipeline
from normalization_poc.report import write_report


class CountingProvider(DeterministicMockEnrichment):
    def __init__(self):
        self.calls = 0

    def enrich(self, record):
        self.calls += 1
        return super().enrich(record)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.sources = {}
        for source, record in (
            (
                "servicenow",
                {
                    "number": "INC1",
                    "short_description": "VPN fails",
                    "description": "VPN certificate error",
                    "state": "New",
                },
            ),
            (
                "confluence",
                {
                    "id": "KB1",
                    "title": "VPN guide",
                    "body": "Rotate the VPN certificate",
                    "status": "current",
                },
            ),
            (
                "jira",
                {
                    "key": "APP-1",
                    "issue_type": "Task",
                    "summary": "Add VPN metric",
                    "description": "Track VPN reconnects",
                    "status": "To Do",
                },
            ),
        ):
            path = self.root / f"{source}.json"
            path.write_text(json.dumps([record]), encoding="utf-8")
            self.sources[source] = path
        self.output = self.root / "output" / "vector_store.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_cache_reuse_then_only_changed_record_is_enriched(self):
        provider = CountingProvider()
        first = run_pipeline(self.sources, self.output, provider)
        self.assertEqual(first.records_read, 3)
        self.assertEqual(first.enrichment_calls, 3)
        self.assertEqual(provider.calls, 3)

        second = run_pipeline(self.sources, self.output, provider)
        self.assertEqual(second.cache_hits, 3)
        self.assertEqual(second.enrichment_calls, 0)
        self.assertEqual(provider.calls, 3)
        self.assertEqual(second.chunks_created, 0)
        self.assertEqual(second.chunks_updated, 0)

        record = json.loads(self.sources["jira"].read_text(encoding="utf-8"))[0]
        record["description"] += " with a new alert."
        self.sources["jira"].write_text(json.dumps([record]), encoding="utf-8")
        third = run_pipeline(self.sources, self.output, provider)
        self.assertEqual(third.cache_hits, 2)
        self.assertEqual(third.enrichment_calls, 1)
        self.assertEqual(provider.calls, 4)

    def test_chunks_match_schema_and_have_contextual_embeddings(self):
        run_pipeline(self.sources, self.output)
        store = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(len(store["chunks"]), 3)
        chunk = next(item for item in store["chunks"] if item["source"] == "jira")
        self.assertEqual(chunk["id"], "jira:APP-1#chunk-0")
        self.assertEqual(chunk["parent_id"], "jira:APP-1")
        self.assertEqual(chunk["canonical_fields"]["status"], "open")
        self.assertIn("APP-1", chunk["context_header"])
        self.assertEqual(chunk["schema_version"], "1.0")
        self.assertEqual(len(chunk["embedding"]), 64)
        self.assertAlmostEqual(sum(value * value for value in chunk["embedding"]), 1.0)
        self.assertIn("key", chunk["source_fields"])

    def test_removed_source_record_removes_stale_chunks(self):
        run_pipeline(self.sources, self.output)
        self.sources["jira"].write_text("[]", encoding="utf-8")
        stats = run_pipeline(self.sources, self.output)
        store = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(stats.chunks_removed, 1)
        self.assertFalse(any(chunk["source"] == "jira" for chunk in store["chunks"]))

    def test_report_contains_run_metrics_and_escapes_source_text(self):
        record = json.loads(self.sources["jira"].read_text(encoding="utf-8"))[0]
        record["description"] = "<script>alert('x')</script>"
        self.sources["jira"].write_text(json.dumps([record]), encoding="utf-8")
        stats = run_pipeline(self.sources, self.output)
        report = write_report(stats, self.output)
        content = report.read_text(encoding="utf-8")
        self.assertIn("Run summary", content)
        self.assertIn("Enrichment cache hits", content)
        self.assertIn("servicenow", content)
        self.assertIn("Show embedding values", content)
        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>alert", content)
        self.assertEqual(report.name, "vector_store_report.html")

    def test_cli_opens_report_by_default_and_can_skip_browser(self):
        stats = PipelineStats(
            records_read=0,
            records_by_source={"jira": 0},
            cache_hits=0,
            enrichment_calls=0,
            chunks_created=0,
            chunks_updated=0,
            chunks_removed=0,
            total_chunks=0,
            output_path=str(self.output),
            provider="deterministic-mock",
        )
        report_path = self.root / "report.html"
        with (
            patch.object(cli, "run_pipeline", return_value=stats),
            patch.object(cli, "write_report", return_value=report_path),
            patch.object(cli.webbrowser, "open", return_value=True) as open_browser,
        ):
            self.assertEqual(cli.main([]), 0)
            open_browser.assert_called_once_with(report_path.resolve().as_uri())
            open_browser.reset_mock()
            self.assertEqual(cli.main(["--no-open-report"]), 0)
            open_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
