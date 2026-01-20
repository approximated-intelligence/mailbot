# -*- coding: utf-8 -*-
"""
Tests for html_utils.py - HTML transformation and sanitization.
"""

import unittest


class TestMakeHtml2TextConverter(unittest.TestCase):
    """Tests for HTML to text converter configuration"""

    def test_returns_converter_instance(self):
        from ..html_utils import make_html2text_converter

        converter = make_html2text_converter()

        self.assertIsNotNone(converter)
        self.assertTrue(hasattr(converter, "handle"))

    def test_converts_html_to_text(self):
        from ..html_utils import make_html2text_converter

        converter = make_html2text_converter()
        html = "<p>Hello <strong>world</strong></p>"

        result = converter.handle(html)

        self.assertIn("Hello", result)
        self.assertIn("world", result)

    def test_preserves_links_by_default(self):
        from ..html_utils import make_html2text_converter

        converter = make_html2text_converter()
        html = '<p>Visit <a href="http://example.com">example</a></p>'

        result = converter.handle(html)

        self.assertIn("http://example.com", result)

    def test_handles_lists(self):
        from ..html_utils import make_html2text_converter

        converter = make_html2text_converter()
        html = "<ul><li>One</li><li>Two</li></ul>"

        result = converter.handle(html)

        self.assertIn("One", result)
        self.assertIn("Two", result)


class TestBleachContent(unittest.TestCase):
    """Tests for HTML sanitization"""

    def test_output_contains_no_script_tags(self):
        import lxml.html

        from ..html_utils import bleach_content

        html = "<html><body><script>alert('xss')</script><p>Safe</p></body></html>"
        tree = lxml.html.fromstring(html)

        result = bleach_content(tree, "http://example.com")
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertNotIn("<script", result_str.lower())
        self.assertIn("Safe", result_str)

    def test_output_contains_no_javascript_urls(self):
        import lxml.html

        from ..html_utils import bleach_content

        html = '<html><body><a href="javascript:alert(1)">Click</a></body></html>'
        tree = lxml.html.fromstring(html)

        result = bleach_content(tree, "http://example.com")
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertNotIn("javascript:", result_str.lower())

    def test_output_contains_no_form_tags(self):
        import lxml.html

        from ..html_utils import bleach_content

        html = '<html><body><form action="/steal"><input name="cc"></form></body></html>'
        tree = lxml.html.fromstring(html)

        result = bleach_content(tree, "http://example.com")
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertNotIn("<form", result_str.lower())

    def test_preserves_safe_content(self):
        import lxml.html

        from ..html_utils import bleach_content

        html = "<html><body><p>Hello</p><a href='http://safe.com'>Link</a></body></html>"
        tree = lxml.html.fromstring(html)

        result = bleach_content(tree, "http://example.com")
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertIn("Hello", result_str)
        self.assertIn("http://safe.com", result_str)

    def test_removes_inline_styles(self):
        import lxml.html

        from ..html_utils import bleach_content

        html = '<html><body><p style="color:red">Styled</p></body></html>'
        tree = lxml.html.fromstring(html)

        result = bleach_content(tree, "http://example.com")
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertNotIn("style=", result_str.lower())
        self.assertIn("Styled", result_str)


class TestTransformHtmlContent(unittest.TestCase):
    """Tests for HTML transformation pipeline"""

    def test_returns_html_when_as_txt_false(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = "<html><body><p>Content</p></body></html>"
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=False,
            include_images=False,
            as_txt=False,
            txt_without_links=False,
        )

        self.assertEqual(subtype, "html")
        self.assertIn("<", content)

    def test_returns_plain_text_when_as_txt_true(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = "<html><body><p>Content</p></body></html>"
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=False,
            include_images=False,
            as_txt=True,
            txt_without_links=False,
        )

        self.assertEqual(subtype, "plain")
        self.assertIn("Content", content)

    def test_extracts_title(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = "<html><head><title>My Title</title></head><body><p>Content</p></body></html>"
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=False,
            include_images=False,
            as_txt=False,
            txt_without_links=False,
        )

        self.assertEqual(title, "My Title")

    def test_prefix_indicates_bleach(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = "<html><body><p>Content</p></body></html>"
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=True,
            include_images=False,
            as_txt=False,
            txt_without_links=False,
        )

        self.assertIn("B", prefix)

    def test_prefix_indicates_text_with_links(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = "<html><body><p>Content</p></body></html>"
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=False,
            include_images=False,
            as_txt=True,
            txt_without_links=False,
        )

        self.assertIn("TL", prefix)

    def test_prefix_indicates_text_without_links(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = "<html><body><p>Content</p></body></html>"
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=False,
            include_images=False,
            as_txt=True,
            txt_without_links=True,
        )

        self.assertIn("TP", prefix)

    def test_links_removed_when_txt_without_links(self):
        import lxml.html

        from ..html_utils import transform_html_content

        html = '<html><body><a href="http://example.com">Link</a></body></html>'
        tree = lxml.html.fromstring(html)
        config = self._make_config()

        content, title, subtype, prefix = transform_html_content(
            tree,
            "http://example.com",
            config,
            bleach_html=False,
            include_images=False,
            as_txt=True,
            txt_without_links=True,
        )

        self.assertNotIn("http://example.com", content)

    def _make_config(self):
        class Config:
            deobfuscators = {}
            default_image_timeout = 10
            default_max_images = 100

        return Config()


class TestDeobfuscateSpiegel(unittest.TestCase):
    """Tests for Spiegel.de deobfuscation"""

    def test_shifts_obfuscated_text_back(self):
        import lxml.html

        from ..html_utils import deobfuscate_spiegel

        # Spiegel shifts characters forward by 1, so 'b' becomes 'a'
        html = '<html><body><div class="obfuscated"><p>ifmmp</p></div></body></html>'
        tree = lxml.html.fromstring(html)

        result = deobfuscate_spiegel(tree)
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertIn("hello", result_str)

    def test_leaves_non_obfuscated_content_unchanged(self):
        import lxml.html

        from ..html_utils import deobfuscate_spiegel

        html = "<html><body><p>normal text</p></body></html>"
        tree = lxml.html.fromstring(html)

        result = deobfuscate_spiegel(tree)
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertIn("normal text", result_str)


class TestApplyDeobfuscation(unittest.TestCase):
    """Tests for deobfuscation dispatch"""

    def test_applies_matching_deobfuscator(self):
        import lxml.html

        from ..html_utils import apply_deobfuscation

        html = '<html><body><div class="obfuscated"><p>uftu</p></div></body></html>'
        tree = lxml.html.fromstring(html)
        deobfuscators = {"spiegel.de": "deobfuscate_spiegel"}

        result = apply_deobfuscation(tree, "http://spiegel.de/article", deobfuscators)
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertIn("test", result_str)

    def test_no_change_when_no_matching_deobfuscator(self):
        import lxml.html

        from ..html_utils import apply_deobfuscation

        html = "<html><body><p>original</p></body></html>"
        tree = lxml.html.fromstring(html)
        deobfuscators = {"spiegel.de": "deobfuscate_spiegel"}

        result = apply_deobfuscation(tree, "http://other.com/article", deobfuscators)
        result_str = lxml.html.tostring(result, encoding="unicode")

        self.assertIn("original", result_str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
