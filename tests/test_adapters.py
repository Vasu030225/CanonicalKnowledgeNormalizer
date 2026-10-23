import unittest

from normalization_poc.adapters import (
    adapt_confluence,
    adapt_jira,
    adapt_servicenow,
)


class AdapterTests(unittest.TestCase):
    def test_servicenow_maps_status_priority_owner_and_dates(self):
        record = adapt_servicenow(
            {
                "number": "INC1",
                "short_description": "VPN issue",
                "description": "Cannot connect",
                "state": "In Progress",
                "priority": "2 - High",
                "assigned_to": "test.owner",
                "opened_at": "2026-02-12T09:15:00-05:00",
                "sys_updated_on": "2026-02-12T15:30:00Z",
                "url": "https://example.invalid/INC1",
                "acl": ["group:test"],
            }
        )
        self.assertEqual(record.parent_id, "servicenow:INC1")
        self.assertEqual(record.object_type, "incident")
        self.assertEqual(record.canonical_fields.status, "in_progress")
        self.assertEqual(record.canonical_fields.priority, "high")
        self.assertEqual(record.canonical_fields.created_at, "2026-02-12T14:15:00Z")
        self.assertEqual(record.acl, ["group:test"])
        self.assertIn("number", record.source_fields)

    def test_confluence_handles_missing_optional_fields(self):
        record = adapt_confluence(
            {"id": "KB-1", "title": "Runbook", "body": "Steps", "status": "draft"}
        )
        self.assertEqual(record.canonical_fields.status, "open")
        self.assertIsNone(record.canonical_fields.priority)
        self.assertIsNone(record.url)
        self.assertEqual(record.acl, [])

    def test_jira_maps_issue_type_and_shared_fields(self):
        record = adapt_jira(
            {
                "key": "APP-2",
                "issue_type": "Bug",
                "summary": "Login issue",
                "description": "Callback fails",
                "status": "Done",
                "priority": "Highest",
                "assignee": "test.user",
            }
        )
        self.assertEqual(record.object_type, "bug")
        self.assertEqual(record.canonical_fields.status, "resolved")
        self.assertEqual(record.canonical_fields.priority, "critical")
        self.assertEqual(record.canonical_fields.owner, "test.user")


if __name__ == "__main__":
    unittest.main()
