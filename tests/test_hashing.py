import unittest

from normalization_poc.adapters import stable_content_hash


class StableHashTests(unittest.TestCase):
    def test_hash_is_repeatable_and_sensitive_to_content(self):
        first = stable_content_hash("jira", "issue", "Login", "Callback fails")
        self.assertEqual(first, stable_content_hash("jira", "issue", "Login", "Callback fails"))
        self.assertNotEqual(first, stable_content_hash("jira", "issue", "Login", "Callback works"))

    def test_hash_is_stable_for_equivalent_input_values(self):
        first = stable_content_hash("jira", "issue", "Title", "Body")
        second = stable_content_hash("jira", "issue", "Title", "Body")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
