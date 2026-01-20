# -*- coding: utf-8 -*-
"""
Tests for imap_utils.py - IMAP protocol utilities and credentials.
"""

import os
import sys
import unittest

from ..imap_utils import get_credential


class TestGetCredential(unittest.TestCase):
    """Tests for credential retrieval from different sources"""

    def test_reads_from_environment(self):
        os.environ["TEST_CRED_ENV"] = "secret_from_env"
        try:
            result = get_credential("TEST_CRED_ENV", "test", "Prompt: ")
            self.assertEqual(result, "secret_from_env")
        finally:
            del os.environ["TEST_CRED_ENV"]

    def test_environment_takes_priority_over_cli(self):
        os.environ["TEST_CRED_PRIO"] = "from_env"
        original_argv = sys.argv
        sys.argv = ["prog", "--prio=from_cli"]
        try:
            result = get_credential("TEST_CRED_PRIO", "prio", "Prompt: ")
            self.assertEqual(result, "from_env")
        finally:
            del os.environ["TEST_CRED_PRIO"]
            sys.argv = original_argv

    def test_reads_from_cli_with_equals(self):
        if "TEST_CRED_CLI1" in os.environ:
            del os.environ["TEST_CRED_CLI1"]

        original_argv = sys.argv
        sys.argv = ["prog", "--mycred=clivalue"]
        try:
            result = get_credential("TEST_CRED_CLI1", "mycred", "Prompt: ")
            self.assertEqual(result, "clivalue")
        finally:
            sys.argv = original_argv

    def test_reads_from_cli_with_space(self):
        if "TEST_CRED_CLI2" in os.environ:
            del os.environ["TEST_CRED_CLI2"]

        original_argv = sys.argv
        sys.argv = ["prog", "--mycred2", "spacevalue"]
        try:
            result = get_credential("TEST_CRED_CLI2", "mycred2", "Prompt: ")
            self.assertEqual(result, "spacevalue")
        finally:
            sys.argv = original_argv


if __name__ == "__main__":
    unittest.main(verbosity=2)
