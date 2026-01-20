# -*- coding: utf-8 -*-
"""
IMAP protocol utilities: IDLE implementation, connection helpers, credentials, main run loop.
"""

import getpass
import imaplib
import os
import select
import socket
import sys
import time

CRLF = b"\r\n"
imaplib.Commands["IDLE"] = ("AUTH", "SELECTED")


def get_credential(env_var, arg_name, prompt):
    """
    Get credential from environment, command line args, or prompt.

    Priority:
    1. Environment variable
    2. Command line --arg=value or --arg value
    3. Interactive prompt (masked input)
    """
    value = os.environ.get(env_var)
    if value:
        return value

    for i, arg in enumerate(sys.argv):
        if arg.startswith(f"--{arg_name}="):
            return arg.split("=", 1)[1]
        elif arg == f"--{arg_name}" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]

    return getpass.getpass(prompt)


def idle(connection, timeout=(29 * 60 - 1)):
    """
    Implements IMAP IDLE extension as described in RFC 2177.
    Waits until state of current mailbox changes.

    Args:
        connection: IMAP4 connection
        timeout: Maximum idle time in seconds (default: 29 minutes)

    Returns:
        (typ, untagged_responses) tuple
    """
    if "IDLE" not in connection.capabilities:
        raise connection.error("server does not support IDLE command.")

    connection.untagged_responses = {}
    tag = connection._command("IDLE")
    connection._get_response()

    select.select([connection.socket()], [], [], timeout)

    connection.send(b"DONE" + CRLF)
    typ, data = connection._command_complete("IDLE", tag)
    return typ, connection.untagged_responses


def connect_and_select(config, password):
    """
    Connect to IMAP server and select inbox.

    Args:
        config: Configuration module with imap_server, imap_user, inbox
        password: IMAP password

    Returns:
        IMAP4_SSL connection object

    Raises:
        socket.error, imaplib.IMAP4.abort on connection failures
    """
    connection = imaplib.IMAP4_SSL(config.imap_server)
    connection.login(config.imap_user, password)
    connection.select(config.inbox)
    return connection


def disconnect(connection):
    """Cleanly close IMAP connection"""
    try:
        connection.close()
        connection.logout()
    except:
        pass


def run(
    config,
    queries,
    handler_module,
    password,
    once=False,
    initial_delay=60,
    max_delay=3600,
):
    """
    Run query processor.

    Args:
        config: Configuration module with server settings
        queries: Query list from config_queries
        handler_module: handlers module with runQueries()
        password: IMAP/SMTP password
        once: True for single pass, False for daemon with IDLE
        initial_delay: Initial retry delay in seconds
        max_delay: Maximum retry delay in seconds
    """
    runtime_options = {
        "smtp_server": config.smtp_server,
        "smtp_user": config.smtp_user,
        "smtp_pass": password,
    }

    retry_delay = initial_delay

    while True:
        try:
            connection = connect_and_select(config, password)
            handler_module.runQueries(connection, queries, runtime_options)
            disconnect(connection)

            if once:
                break

            retry_delay = initial_delay

        except (socket.error, imaplib.IMAP4.abort) as e:
            if once:
                raise
            print(f"Connection failed: {e}")
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)

        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            break

        except Exception as e:
            if once:
                raise
            print(f"Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
