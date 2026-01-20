# -*- coding: utf-8 -*-
"""
Tests for handlers.py - email handler behavior.
"""

import email
import unittest
from unittest.mock import Mock

from ..email_utils import build_message
from ..handlers import (
    Copy,
    Delete,
    Expunge,
    Move,
    Obnoxious,
    SetFlags,
    SetFlagsAndMove,
    WorkEmail,
)


def make_test_config():
    """Create minimal config object for testing."""

    class Config:
        mydomain = "@example.com"
        proxy_to = "proxy@example.com"

        # Work email settings
        work_forward_to = "work@workplace.edu"
        work_reply_from = "Answermachine <answermachine@example.com>"
        work_forward_by = "Forwarder <forwarder@example.com>"
        work_reply = {
            "en": "Work emails should be sent to work@workplace.edu",
            "de": "Arbeits-E-Mails bitte an work@workplace.edu senden.",
        }
        work_forward_note = {
            "en": "Forwarded from {sender}",
            "de": "Weitergeleitet von {sender}",
        }

        # Obnoxious settings
        obnoxious_reply_from = "Devnull <devnull@example.com>"
        obnoxious_reply = {
            "en": "This is an automated response. Your email has been filtered as unsolicited.",
            "de": "Dies ist eine automatische Antwort. Ihre E-Mail wurde als unerwünscht eingestuft.",
        }

        # Proxy settings
        proxy_send_from = "Proxy <proxy@example.com>"
        proxy_store_to = "INBOX.Later"
        kindle_send_from = "Kindle <kindle@example.com>"
        kindle_send_to = "user@kindle.com"

        # Fetch settings
        default_fetch_timeout = 30
        default_max_download_size = 100 * 1024 * 1024
        default_image_timeout = 10
        default_max_images = 100
        deobfuscators = {}

    return Config()


def make_raw_email(
    from_addr="sender@example.com",
    to_addr="recipient@example.com",
    subject="Test Subject",
    message_id="<test123@example.com>",
    body="Test body",
    reply_to=None,
    content_language=None,
):
    """Create raw email bytes for testing."""
    msg = build_message(
        subject=subject,
        from_addr=from_addr,
        to_addr=to_addr,
        body=body,
        reply_to=reply_to,
        content_language=content_language,
        message_id=message_id,
    )
    return msg.as_bytes()


def make_mock_server(fetch_data):
    """Create a mock IMAP server that returns given data on FETCH."""
    server = Mock()
    server.uid.return_value = ("OK", fetch_data)
    server.expunge.return_value = ("OK", [])
    return server


class TestExpungeHandler(unittest.TestCase):
    """Tests for Expunge handler behavior"""

    def test_calls_server_expunge(self):
        """Expunge issues EXPUNGE command to server"""
        handler = Expunge()

        server = Mock()
        server.expunge.return_value = ("OK", [])

        res, data, seen_ids = handler(server, [b"1", b"2"], {}, set())

        server.expunge.assert_called_once()
        self.assertEqual(res, "OK")

    def test_passes_through_seen_ids(self):
        """Expunge returns seen_ids unchanged"""
        handler = Expunge()

        server = Mock()
        server.expunge.return_value = ("OK", [])

        initial_seen = {"<msg1@x>", "<msg2@x>"}
        _, _, returned_seen = handler(server, [b"1"], {}, initial_seen)

        self.assertEqual(returned_seen, initial_seen)


class TestDeleteHandler(unittest.TestCase):
    """Tests for Delete handler behavior"""

    def test_marks_messages_as_deleted(self):
        """Delete sets \\Deleted flag on messages"""
        handler = Delete()

        server = Mock()
        server.uid.return_value = ("OK", [])

        handler(server, [b"1", b"2"], {}, set())

        server.uid.assert_called_once()
        call_args = server.uid.call_args[0]
        self.assertEqual(call_args[0], "STORE")
        self.assertIn(b"1", call_args[1])
        self.assertIn(b"2", call_args[1])
        self.assertIn("Deleted", call_args[3])

    def test_passes_through_seen_ids(self):
        """Delete returns seen_ids unchanged"""
        handler = Delete()

        server = Mock()
        server.uid.return_value = ("OK", [])

        initial_seen = {"<msg@x>"}
        _, _, returned_seen = handler(server, [b"1"], {}, initial_seen)

        self.assertEqual(returned_seen, initial_seen)


class TestCopyHandler(unittest.TestCase):
    """Tests for Copy handler behavior"""

    def test_copies_to_specified_folder(self):
        """Copy issues COPY command with correct folder"""
        handler = Copy("INBOX.Archive")

        server = Mock()
        server.uid.return_value = ("OK", [])

        handler(server, [b"1", b"2"], {}, set())

        server.uid.assert_called_once()
        call_args = server.uid.call_args[0]
        self.assertEqual(call_args[0], "COPY")
        self.assertEqual(call_args[2], "INBOX.Archive")

    def test_copies_all_uids(self):
        """Copy includes all UIDs in command"""
        handler = Copy("INBOX.Archive")

        server = Mock()
        server.uid.return_value = ("OK", [])

        handler(server, [b"1", b"2", b"3"], {}, set())

        call_args = server.uid.call_args[0]
        self.assertIn(b"1", call_args[1])
        self.assertIn(b"2", call_args[1])
        self.assertIn(b"3", call_args[1])

    def test_passes_through_seen_ids(self):
        """Copy returns seen_ids unchanged"""
        handler = Copy("INBOX.Archive")

        server = Mock()
        server.uid.return_value = ("OK", [])

        initial_seen = {"<msg@x>"}
        _, _, returned_seen = handler(server, [b"1"], {}, initial_seen)

        self.assertEqual(returned_seen, initial_seen)


class TestWorkEmailHandler(unittest.TestCase):
    """Tests for WorkEmail handler behavior"""

    def test_sends_forward_before_reply(self):
        """Forward is sent first (internal, more reliable), then reply"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"from": from_addr, "to": to_addr, "subject": msg["Subject"]})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(
            from_addr="boss@workplace.edu",
            subject="Urgent Task",
            message_id="<work123@example.com>",
        )
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["to"], config.work_forward_to)
        self.assertEqual(sent[1]["to"], "boss@workplace.edu")

    def test_forward_goes_to_work_address(self):
        """Forward is sent to configured work_forward_to"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"from": from_addr, "to": to_addr})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(from_addr="boss@workplace.edu")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        forward = sent[0]
        self.assertEqual(forward["to"], config.work_forward_to)
        self.assertEqual(forward["from"], config.work_forward_by)

    def test_reply_goes_to_sender(self):
        """Reply is sent back to original sender"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"from": from_addr, "to": to_addr})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(from_addr="boss@workplace.edu")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        reply = sent[1]
        self.assertEqual(reply["to"], "boss@workplace.edu")
        self.assertEqual(reply["from"], config.work_reply_from)

    def test_uses_reply_to_header_when_present(self):
        """Sender address prefers Reply-To over From"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"to": to_addr})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(
            from_addr="noreply@workplace.edu", reply_to="actual-boss@workplace.edu"
        )
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        reply = sent[1]
        self.assertEqual(reply["to"], "actual-boss@workplace.edu")

    def test_uses_german_template_when_content_language_is_de(self):
        """German template used when Content-Language header indicates German"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"msg": msg})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(
            from_addr="boss@workplace.edu", content_language="de"
        )
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        reply_msg = sent[1]["msg"]
        body = reply_msg.get_content()
        self.assertIn("Arbeits-E-Mails", body)

    def test_uses_english_template_by_default(self):
        """English template used when no Content-Language header"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"msg": msg})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(from_addr="boss@workplace.edu")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        reply_msg = sent[1]["msg"]
        body = reply_msg.get_content()
        self.assertIn("Work emails should be sent", body)

    def test_deduplicates_by_message_id(self):
        """Same Message-ID processed twice results in only one forward/reply pair"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"to": to_addr})

        config = make_test_config()
        handler = WorkEmail(config, send_fn=capture_send)

        raw_email = make_raw_email(
            from_addr="boss@workplace.edu", message_id="<duplicate@example.com>"
        )
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        _, _, seen_ids = handler(server, [b"1"], {}, set())
        handler(server, [b"1"], {}, seen_ids)

        self.assertEqual(len(sent), 2)  # Only one forward + reply pair

    def test_seen_ids_returned_include_processed_message(self):
        """seen_ids is updated with processed Message-ID"""
        config = make_test_config()
        handler = WorkEmail(config, send_fn=lambda *args: None)

        raw_email = make_raw_email(message_id="<tracked@example.com>")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        _, _, seen_ids = handler(server, [b"1"], {}, set())

        self.assertIn("<tracked@example.com>", seen_ids)

    def test_continues_if_forward_fails(self):
        """Reply is still attempted if forward fails"""
        import smtplib

        call_count = [0]

        def failing_then_success(options, from_addr, to_addr, msg):
            call_count[0] += 1
            if call_count[0] == 1:
                raise smtplib.SMTPException("Forward failed")

        config = make_test_config()
        handler = WorkEmail(config, send_fn=failing_then_success)

        raw_email = make_raw_email(from_addr="boss@workplace.edu")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        self.assertEqual(call_count[0], 2)  # Both attempts made


class TestObnoxiousHandler(unittest.TestCase):
    """Tests for Obnoxious handler behavior"""

    def test_deletes_before_sending_reply(self):
        """Email is deleted before reply is sent"""
        operations = []

        def capture_send(options, from_addr, to_addr, msg):
            operations.append("send")

        config = make_test_config()
        handler = Obnoxious(config, send_fn=capture_send)

        raw_email = make_raw_email(from_addr="spammer@spam.com")

        def track_uid(*args):
            if args[0] == "STORE":
                operations.append("delete")
            return ("OK", [(b"1 (RFC822", raw_email)])

        server = Mock()
        server.uid.side_effect = track_uid
        server.expunge.return_value = ("OK", [])

        handler(server, [b"1"], {}, set())

        self.assertEqual(operations[0], "delete")
        self.assertIn("send", operations)

    def test_sends_reply_to_sender(self):
        """Snarky reply is sent to the obnoxious sender"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"from": from_addr, "to": to_addr})

        config = make_test_config()
        handler = Obnoxious(config, send_fn=capture_send)

        raw_email = make_raw_email(from_addr="spammer@spam.com")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["to"], "spammer@spam.com")
        self.assertEqual(sent[0]["from"], config.obnoxious_reply_from)

    def test_uses_german_template_when_content_language_is_de(self):
        """German snarky reply when Content-Language is German"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"msg": msg})

        config = make_test_config()
        handler = Obnoxious(config, send_fn=capture_send)

        raw_email = make_raw_email(from_addr="spammer@spam.com", content_language="de")
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        handler(server, [b"1"], {}, set())

        body = sent[0]["msg"].get_content()
        self.assertIn("automatische Antwort", body)

    def test_deduplicates_by_message_id(self):
        """Same Message-ID twice results in only one reply"""
        sent = []

        def capture_send(options, from_addr, to_addr, msg):
            sent.append({"to": to_addr})

        config = make_test_config()
        handler = Obnoxious(config, send_fn=capture_send)

        raw_email = make_raw_email(
            from_addr="spammer@spam.com", message_id="<spam123@spam.com>"
        )
        server = make_mock_server([(b"1 (RFC822", raw_email)])

        _, _, seen_ids = handler(server, [b"1"], {}, set())
        handler(server, [b"1"], {}, seen_ids)

        self.assertEqual(len(sent), 1)


class TestHandlerComposition(unittest.TestCase):
    """Tests for handler composition behavior"""

    def test_move_calls_copy_then_delete(self):
        """Move handler copies to folder then marks deleted"""
        handler = Move("INBOX.Archive")

        server = Mock()
        server.uid.return_value = ("OK", [])

        handler(server, [b"1", b"2"], {}, set())

        calls = server.uid.call_args_list
        self.assertEqual(len(calls), 2)

        # First call is COPY
        self.assertEqual(calls[0][0][0], "COPY")
        self.assertEqual(calls[0][0][2], "INBOX.Archive")

        # Second call is STORE with Deleted flag
        self.assertEqual(calls[1][0][0], "STORE")
        self.assertIn("Deleted", calls[1][0][3])

    def test_move_stops_on_copy_failure(self):
        """Move doesn't delete if copy fails"""
        handler = Move("INBOX.Archive")

        server = Mock()
        server.uid.return_value = ("NO", [b"Copy failed"])

        res, data, seen = handler(server, [b"1"], {}, set())

        self.assertEqual(res, "NO")
        self.assertEqual(server.uid.call_count, 1)  # Only COPY attempted

    def test_setflagsandmove_sets_flags_then_moves(self):
        """SetFlagsAndMove sets flags before moving"""
        handler = SetFlagsAndMove(r"(\Seen)", "INBOX.Read")

        server = Mock()
        server.uid.return_value = ("OK", [])

        handler(server, [b"1"], {}, set())

        calls = server.uid.call_args_list
        self.assertEqual(len(calls), 3)  # STORE flags, COPY, STORE delete

        # First is setting flags
        self.assertEqual(calls[0][0][0], "STORE")
        self.assertIn("Seen", calls[0][0][3])

    def test_handlers_pass_through_seen_ids(self):
        """Handlers correctly pass through and update seen_ids"""
        handler = SetFlags(r"(\Seen)")

        server = Mock()
        server.uid.return_value = ("OK", [])

        initial_seen = {"<old@example.com>"}
        _, _, returned_seen = handler(server, [b"1"], {}, initial_seen)

        self.assertEqual(returned_seen, initial_seen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
