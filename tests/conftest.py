# -*- coding: utf-8 -*-
"""
Shared test fixtures for email proxy tests.
"""

import sys
from pathlib import Path

# Ensure project root is importable without pip install
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_server():
    """Factory fixture for creating mock IMAP servers."""
    def _make_mock_server(fetch_data):
        server = Mock()
        server.uid.return_value = ("OK", fetch_data)
        server.expunge.return_value = ("OK", [])
        return server
    return _make_mock_server


@pytest.fixture
def test_config():
    """Minimal config object for testing."""
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
