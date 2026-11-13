"""
Unit tests for search_templates.py
Validates integrity of the 100+ popular website search templates.
"""

import unittest
from urllib.parse import urlparse
import search_templates


class TestSearchTemplates(unittest.TestCase):

    def test_minimum_count(self):
        """Ensure we have at least 100 popular website templates."""
        self.assertGreaterEqual(len(search_templates.SEARCH_TEMPLATES), 100)

    def test_schema_integrity(self):
        """Verify that every entry contains valid fields, domains, and placeholders."""
        seen_names = set()
        for idx, entry in enumerate(search_templates.SEARCH_TEMPLATES):
            name = entry.get("name")
            self.assertIsNotNone(name, f"Entry #{idx} missing name")
            self.assertNotIn(name, seen_names, f"Duplicate entry name: {name}")
            seen_names.add(name)

            self.assertIn("aliases", entry)
            self.assertIsInstance(entry["aliases"], list)
            self.assertGreater(len(entry["aliases"]), 0, f"{name} must have at least one alias")

            self.assertIn("domain", entry)
            self.assertIn("category", entry)

            url = entry.get("search_url")
            self.assertTrue(url.startswith("https://"), f"{name} URL must start with https://: {url}")
            self.assertIn("{query}", url, f"{name} URL must contain '{{query}}' placeholder: {url}")

            parsed = urlparse(url)
            self.assertTrue(bool(parsed.netloc), f"{name} has invalid netloc: {url}")

            param = entry.get("query_param")
            self.assertTrue(bool(param), f"{name} must specify query_param")

    def test_prompt_resolution(self):
        """Verify accurate natural language resolution on sample prompts."""
        test_cases = [
            (
                "find the last paper of Nikola Danevski on google scholar and summarize it for me in one sentence",
                "https://scholar.google.com/scholar?q=the+last+paper+of+Nikola+Danevski",
                "Google Scholar"
            ),
            (
                "check github for localpilot repository",
                "https://github.com/search?q=localpilot+repository",
                "GitHub"
            ),
            (
                "look up machine learning on wikipedia",
                "https://en.wikipedia.org/w/index.php?search=machine+learning",
                "Wikipedia"
            ),
            (
                "search for mechanical keyboard on amazon",
                "https://www.amazon.com/s?k=mechanical+keyboard",
                "Amazon"
            ),
            (
                "find python tutorial on youtube and tell me the views",
                "https://www.youtube.com/results?search_query=python+tutorial",
                "YouTube"
            ),
            (
                "search pubmed for crispr gene editing",
                "https://pubmed.ncbi.nlm.nih.gov/?term=crispr+gene+editing",
                "PubMed"
            ),
            (
                "find transformers models on hugging face",
                "https://huggingface.co/models?search=transformers+models",
                "Hugging Face"
            )
        ]

        for prompt, expected_url, expected_name in test_cases:
            res = search_templates.resolve_search_template(prompt)
            self.assertIsNotNone(res, f"Failed to match prompt: {prompt}")
            formatted_url, site_name, query = res
            self.assertEqual(site_name, expected_name)
            self.assertEqual(formatted_url, expected_url)


if __name__ == "__main__":
    unittest.main()
