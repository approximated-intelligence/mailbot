# -*- coding: utf-8 -*-
"""
Tests for proxy_utils.py - URL fetching, option parsing, message building.
"""

import unittest

from ..proxy_utils import (
    proxy_decode_text_content,
    proxy_fix_filename_extension,
    proxy_parse_options,
)


class TestProxyParseOptions(unittest.TestCase):
    """Tests for proxy option parsing"""

    def test_txt_option_converts_to_text(self, test_config=None):
        if test_config is None:
            test_config = self._make_config()
        to_addr = f"txt+{test_config.proxy_to}"

        opts = proxy_parse_options(to_addr, test_config, "sender@x")

        self.assertTrue(opts["as_txt"])

    def test_bleach_option_sanitizes_html(self):
        config = self._make_config()
        to_addr = f"bleach+{config.proxy_to}"

        opts = proxy_parse_options(to_addr, config, "sender@x")

        self.assertTrue(opts["bleach_html"])

    def test_images_option_inlines_images(self):
        config = self._make_config()
        to_addr = f"images+{config.proxy_to}"

        opts = proxy_parse_options(to_addr, config, "sender@x")

        self.assertTrue(opts["include_images"])

    def test_kindle_routes_to_kindle(self):
        config = self._make_config()
        to_addr = f"kindle+txt+{config.proxy_to}"

        opts = proxy_parse_options(to_addr, config, "sender@x")

        self.assertTrue(opts["send_using_smtp"])
        self.assertEqual(opts["send_to"], config.kindle_send_to)
        self.assertEqual(opts["send_from"], config.kindle_send_from)

    def test_default_routes_back_to_sender(self):
        config = self._make_config()
        to_addr = f"txt+{config.proxy_to}"

        opts = proxy_parse_options(to_addr, config, "original_sender@x")

        self.assertFalse(opts["send_using_smtp"])
        self.assertEqual(opts["send_to"], "original_sender@x")

    def test_combined_options(self):
        config = self._make_config()
        to_addr = f"txt+bleach+images+{config.proxy_to}"

        opts = proxy_parse_options(to_addr, config, "sender@x")

        self.assertTrue(opts["as_txt"])
        self.assertTrue(opts["bleach_html"])
        self.assertTrue(opts["include_images"])

    def test_options_are_case_insensitive(self):
        config = self._make_config()
        to_addr = f"TXT+BLEACH+{config.proxy_to}"

        opts = proxy_parse_options(to_addr, config, "sender@x")

        self.assertTrue(opts["as_txt"])
        self.assertTrue(opts["bleach_html"])

    def _make_config(self):
        """Create minimal config for tests that don't use fixture"""

        class Config:
            mydomain = "@example.com"
            proxy_to = "proxy@example.com"
            proxy_send_from = "Proxy <proxy@example.com>"
            kindle_send_from = "Kindle <kindle@example.com>"
            kindle_send_to = "user@kindle.com"

        return Config()


class TestProxyDecodeTextContent(unittest.TestCase):
    """Tests for text content decoding"""

    def test_decodes_valid_utf8(self):
        result = proxy_decode_text_content("Héllo wörld".encode("utf-8"), "utf-8")

        self.assertEqual(result, "Héllo wörld")

    def test_decodes_with_declared_charset(self):
        result = proxy_decode_text_content("Héllo".encode("iso-8859-1"), "iso-8859-1")

        self.assertEqual(result, "Héllo")

    def test_handles_invalid_encoding_without_crashing(self):
        content = bytes([0x80, 0x81, 0x82])

        result = proxy_decode_text_content(content, "ascii")

        self.assertIsInstance(result, str)


class TestProxyFixFilenameExtension(unittest.TestCase):
    """Tests for filename extension handling"""

    def test_adds_txt_for_plain_text(self):
        result = proxy_fix_filename_extension("document", "plain")

        self.assertEqual(result, "document.txt")

    def test_adds_html_for_html(self):
        result = proxy_fix_filename_extension("page", "html")

        self.assertEqual(result, "page.html")

    def test_preserves_existing_correct_extension(self):
        result = proxy_fix_filename_extension("doc.txt", "plain")

        self.assertEqual(result, "doc.txt")

    def test_other_types_unchanged(self):
        result = proxy_fix_filename_extension("file.pdf", "pdf")

        self.assertEqual(result, "file.pdf")


class TestProxyExtractUrls(unittest.TestCase):
    """Tests for URL extraction from proxy emails"""

    def test_extracts_urls_from_plain_text_body(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Check http://example.com/article")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com/article", urls)

    def test_extracts_urls_from_html_body(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content(
            '<p>Visit <a href="http://example.com">our site</a></p>',
            subtype="html",
        )

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com", urls)

    def test_extracts_urls_from_subject(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Body without URL")

        urls = proxy_extract_urls(msg, "Read this: https://news.com/story")

        self.assertIn("https://news.com/story", urls)

    def test_extracts_urls_from_both_body_and_subject(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Body link: http://one.com")

        urls = proxy_extract_urls(msg, "Subject link: http://two.com")

        self.assertIn("http://one.com", urls)
        self.assertIn("http://two.com", urls)

    def test_deduplicates_urls(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("http://same.com")

        urls = proxy_extract_urls(msg, "http://same.com")

        self.assertIn("http://same.com", urls)
        self.assertEqual(len([u for u in urls if "same.com" in u]), 1)

    def test_handles_none_subject(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("http://example.com")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com", urls)

    def test_strips_trailing_period(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("See http://example.com.")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com", urls)

    def test_strips_trailing_punctuation_from_parens(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Info (http://example.com) here")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com", urls)

    def test_strips_trailing_question_mark(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Did you see http://example.com?")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com", urls)

    def test_strips_trailing_colon(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Check this site: http://example.com:")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com", urls)

    def test_preserves_query_strings(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Search: http://example.com/search?q=test&page=1")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com/search?q=test&page=1", urls)

    def test_preserves_fragments(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("See http://example.com/page#section")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://example.com/page#section", urls)

    def test_preserves_port_numbers(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("Dev server: http://localhost:8080/app")

        urls = proxy_extract_urls(msg, None)

        self.assertIn("http://localhost:8080/app", urls)

    def test_returns_empty_set_when_no_urls(self):
        import email.message

        from ..proxy_utils import proxy_extract_urls

        msg = email.message.EmailMessage()
        msg.set_content("No links here")

        urls = proxy_extract_urls(msg, "Also no links")

        self.assertEqual(len(urls), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
