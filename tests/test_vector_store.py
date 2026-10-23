import json
import tempfile
import unittest
from pathlib import Path

from normalization_poc.vector_store import (
    VectorStoreError,
    empty_store,
    load_vector_store,
    save_vector_store,
)


class VectorStoreTests(unittest.TestCase):
    def test_single_file_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output" / "vector_store.json"
            store = empty_store()
            store["enrichment_cache"]["sha256:test"] = {
                "summary": "A summary",
                "entities": ["Example"],
            }
            store["chunks"].append(
                {
                    "id": "jira:APP-1#chunk-0",
                    "parent_id": "jira:APP-1",
                    "chunk_index": 0,
                    "source": "jira",
                    "object_type": "issue",
                    "title": "Example",
                    "content": "Example chunk",
                    "context_header": "Jira - APP-1 - Example",
                    "canonical_fields": {
                        "status": "open",
                        "priority": None,
                        "owner": None,
                        "created_at": None,
                        "updated_at": None,
                    },
                    "summary": "A summary",
                    "entities": ["Example"],
                    "source_fields": {"key": "APP-1"},
                    "url": None,
                    "content_hash": "sha256:test",
                    "acl": [],
                    "schema_version": "1.0",
                    "embedding": [0.0, 1.0],
                }
            )
            save_vector_store(path, store)
            self.assertEqual(load_vector_store(path), store)
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_invalid_store_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vector_store.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(VectorStoreError, "not valid JSON"):
                load_vector_store(path)

    def test_invalid_canonical_chunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vector_store.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "chunks": [{"id": "jira:APP-1#chunk-0", "embedding": [0.0]}],
                        "enrichment_cache": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(VectorStoreError, "missing canonical fields"):
                load_vector_store(path)


if __name__ == "__main__":
    unittest.main()
