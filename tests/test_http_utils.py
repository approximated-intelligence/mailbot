# -*- coding: utf-8 -*-
"""
Tests for http_utils.py - HTTP fetching and caching.
"""

import unittest

from ..http_utils import get_filename_from_headers_or_url


class TestGetFilenameFromHeadersOrUrl(unittest.TestCase):
    """Tests for filename extraction"""

    def test_extracts_from_content_disposition(self):
        headers = {"content-disposition": 'attachment; filename="report.pdf"'}
        result = get_filename_from_headers_or_url(headers, "http://example.com/other")
        self.assertEqual(result, "report.pdf")

    def test_extracts_from_content_disposition_single_quotes(self):
        headers = {"content-disposition": "attachment; filename='report.pdf'"}
        result = get_filename_from_headers_or_url(headers, "http://example.com/other")
        self.assertEqual(result, "report.pdf")

    def test_falls_back_to_url(self):
        headers = {}
        result = get_filename_from_headers_or_url(
            headers, "http://example.com/path/file.txt"
        )
        self.assertIn("file", result)

    def test_returns_default_on_empty(self):
        headers = {}
        result = get_filename_from_headers_or_url(headers, "")
        self.assertEqual(result, "download")


if __name__ == "__main__":
    unittest.main(verbosity=2)
