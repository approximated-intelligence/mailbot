# -*- coding: utf-8 -*-
"""
Tests for email_utils.py - email parsing, construction, language detection.
"""

import email.message
import unittest

from ..email_utils import (
    build_message,
    detect_language,
    should_process_message,
)


class TestShouldProcessMessage(unittest.TestCase):
    """Tests for message deduplication"""

    def test_new_message_should_process(self):
        seen = set()
        should, new_seen = should_process_message("msg1@domain", seen)
        self.assertTrue(should)
        self.assertIn("msg1@domain", new_seen)

    def test_seen_message_should_not_process(self):
        seen = {"msg1@domain"}
        should, new_seen = should_process_message("msg1@domain", seen)
        self.assertFalse(should)

    def test_original_set_unchanged(self):
        seen = set()
        _, new_seen = should_process_message("msg1@domain", seen)
        self.assertEqual(len(seen), 0)
        self.assertEqual(len(new_seen), 1)


class TestDetectLanguage(unittest.TestCase):
    """Tests for language detection from headers only"""

    def test_detect_from_content_language_header(self):
        msg = email.message.EmailMessage()
        msg["Content-Language"] = "de"

        result = detect_language(msg, ["en", "de"], default="en")
        self.assertEqual(result, "de")

    def test_detect_from_content_language_header_with_region(self):
        msg = email.message.EmailMessage()
        msg["Content-Language"] = "de-DE"

        result = detect_language(msg, ["en", "de"], default="en")
        self.assertEqual(result, "de")

    def test_default_when_no_header(self):
        msg = email.message.EmailMessage()

        result = detect_language(msg, ["en", "de"], default="en")
        self.assertEqual(result, "en")

    def test_default_when_unknown_language(self):
        msg = email.message.EmailMessage()
        msg["Content-Language"] = "fr"

        result = detect_language(msg, ["en", "de"], default="en")
        self.assertEqual(result, "en")


class TestBuildMessage(unittest.TestCase):
    """Tests for email message creation - verifies required headers are set"""

    def test_required_headers_present(self):
        msg = build_message(
            subject="Test Subject",
            from_addr="sender@example.com",
            to_addr="recipient@example.com",
            body="Test body",
        )
        self.assertEqual(msg["Subject"], "Test Subject")
        self.assertEqual(msg["From"], "sender@example.com")
        self.assertEqual(msg["To"], "recipient@example.com")
        self.assertIsNotNone(msg["Message-ID"])
        self.assertIsNotNone(msg["Date"])

    def test_subject_prefix_applied(self):
        msg = build_message(
            subject="Original",
            from_addr="from@x",
            to_addr="to@x",
            body="Body",
            subject_prefix="Re:",
        )
        self.assertEqual(msg["Subject"], "Re: Original")

    def test_reply_to_set_when_provided(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="Body",
            reply_to="reply@x",
        )
        self.assertEqual(msg["Reply-To"], "reply@x")

    def test_threading_headers_set_for_reply(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="Body",
            in_reply_to="<original@example.com>",
        )
        self.assertEqual(msg["In-Reply-To"], "<original@example.com>")
        self.assertEqual(msg["References"], "<original@example.com>")

    def test_explicit_message_id(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="Body",
            message_id="<explicit123@example.com>",
        )
        self.assertEqual(msg["Message-ID"], "<explicit123@example.com>")

    def test_message_id_domain(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="Body",
            message_id_domain="testdomain",
        )
        self.assertIn("testdomain", msg["Message-ID"])

    def test_explicit_message_id_overrides_domain(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="Body",
            message_id="<explicit@test>",
            message_id_domain="ignored",
        )
        self.assertEqual(msg["Message-ID"], "<explicit@test>")


class TestCreateReplyMessage(unittest.TestCase):
    """Tests for reply message creation"""

    def test_reply_has_re_prefix(self):
        msg = build_message(
            subject="Original",
            from_addr="from@x",
            to_addr="to@x",
            body="Reply body",
            subject_prefix="Re:",
            in_reply_to="<orig@x>",
        )
        self.assertEqual(msg["Subject"], "Re: Original")

    def test_reply_body_included(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="This is the reply body",
            subject_prefix="Re:",
            in_reply_to="<orig@x>",
        )
        body = msg.get_content()
        self.assertIn("This is the reply body", body)

    def test_reply_can_be_serialized(self):
        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="This is the reply body",
            subject_prefix="Re:",
            in_reply_to="<orig@x>",
        )
        serialized = msg.as_string()
        self.assertIsInstance(serialized, str)
        self.assertGreater(len(serialized), 0)


class TestCreateForwardMessage(unittest.TestCase):
    """Tests for forward message creation"""

    def test_forward_has_fwd_prefix(self):
        original = email.message.EmailMessage()
        original["Subject"] = "Original"
        original.set_content("Original content")

        msg = build_message(
            subject="Original",
            from_addr="from@x",
            to_addr="to@x",
            body="Forwarding this",
            subject_prefix="Fwd:",
            in_reply_to="<orig@x>",
            attach_bytes=original.as_bytes(),
            attach_maintype="message",
            attach_subtype="rfc822",
        )
        self.assertEqual(msg["Subject"], "Fwd: Original")

    def test_forward_can_be_serialized(self):
        original = email.message.EmailMessage()
        original.set_content("Original content")

        msg = build_message(
            subject="Test",
            from_addr="from@x",
            to_addr="to@x",
            body="See below",
            subject_prefix="Fwd:",
            in_reply_to="<orig@x>",
            attach_bytes=original.as_bytes(),
            attach_maintype="message",
            attach_subtype="rfc822",
        )
        serialized = msg.as_string()
        self.assertIsInstance(serialized, str)
        self.assertGreater(len(serialized), 0)


class TestGetDecodedEmailBody(unittest.TestCase):
    """Tests for email body extraction"""

    def test_extracts_plain_text_body(self):
        from ..email_utils import get_decoded_email_body

        msg = email.message.EmailMessage()
        msg.set_content("Plain text content")

        body = get_decoded_email_body(msg)

        self.assertEqual(body, "Plain text content")

    def test_extracts_html_body(self):
        from ..email_utils import get_decoded_email_body

        msg = email.message.EmailMessage()
        msg.set_content("<p>HTML content</p>", subtype="html")

        body = get_decoded_email_body(msg)

        self.assertIn("HTML content", body)

    def test_returns_empty_string_on_failure(self):
        from ..email_utils import get_decoded_email_body

        msg = email.message.EmailMessage()
        # Empty message with no content

        body = get_decoded_email_body(msg)

        self.assertEqual(body, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
