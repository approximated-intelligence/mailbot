# -*- coding: utf-8 -*-
"""
Email handlers: IMAP operations and processing logic.
All handlers are factory functions that return configured handler functions.
Handler signature: handler(server, listofuids, options, seen_ids) -> (res, data, seen_ids)
"""

import email
import smtplib
import time

import email_utils
import imap_utils
import proxy_utils


def Expunge():
    """Factory: Create handler that permanently removes deleted messages"""

    def handler(server, listofuids, options, seen_ids):
        res, data = server.expunge()
        return (res, data, seen_ids)

    return handler


def Delete():
    """Factory: Create handler that marks messages as deleted"""

    def handler(server, listofuids, options, seen_ids):
        theuids = b",".join(listofuids)
        res, data = server.uid("STORE", theuids, "+FLAGS", r"(\Deleted)")
        return (res, data, seen_ids)

    return handler


def Copy(folder):
    """Factory: Create handler that copies messages to folder"""

    def handler(server, listofuids, options, seen_ids):
        theuids = b",".join(listofuids)
        res, data = server.uid("COPY", theuids, folder)
        return (res, data, seen_ids)

    return handler


def Move(folder):
    """Factory: Create handler that moves messages (copy + delete)"""
    copy_handler = Copy(folder)
    delete_handler = Delete()

    def handler(server, listofuids, options, seen_ids):
        res, data, seen_ids = copy_handler(server, listofuids, options, seen_ids)
        if res == "OK":
            return delete_handler(server, listofuids, options, seen_ids)
        return (res, data, seen_ids)

    return handler


def SetFlags(flag):
    """Factory: Create handler that sets IMAP flags on messages"""

    def handler(server, listofuids, options, seen_ids):
        theuids = b",".join(listofuids)
        res, data = server.uid("STORE", theuids, "+FLAGS", flag)
        return (res, data, seen_ids)

    return handler


def SetFlagsAndMove(flag, folder):
    """Factory: Create handler that sets flags and moves messages"""
    set_flags_handler = SetFlags(flag)
    move_handler = Move(folder)

    def handler(server, listofuids, options, seen_ids):
        res, data, seen_ids = set_flags_handler(server, listofuids, options, seen_ids)
        if res == "OK":
            return move_handler(server, listofuids, options, seen_ids)
        return (res, data, seen_ids)

    return handler


def WorkEmail(config, send_fn=None):
    """
    Factory: Create handler that auto-forwards work-related emails with reply to sender.
    Language is detected from Content-Language header.

    Uses Message-ID deduplication to prevent duplicate replies/forwards.
    Forward is sent first (more reliable), reply is best-effort.

    Args:
        config: Configuration with templates and addresses
        send_fn: Optional (options, from_addr, to_addr, message) -> None
                 Defaults to email_utils.send_via_smtp
    """
    send_fn = send_fn or email_utils.send_via_smtp

    def handler(server, listofuids, options, seen_ids):
        theuids = b",".join(listofuids)
        res, data = server.uid("FETCH", theuids, "RFC822")

        for ret in data:
            if isinstance(ret, (list, tuple)):
                try:
                    message = ret[1]
                except IndexError:
                    continue

                themail = email.message_from_string(message.decode("utf-8"))
                if not themail:
                    continue

                should_process, seen_ids = email_utils.should_process_message(
                    themail["Message-ID"], seen_ids
                )
                if not should_process:
                    continue

                themid = themail["Message-ID"]
                thesender = themail["Reply-To"] or themail["From"] or themail["Sender"]
                subject = themail["Subject"]

                lang = email_utils.detect_language(
                    themail, config.work_reply.keys(), default="en"
                )
                reply_body = config.work_reply.get(lang, config.work_reply["en"])
                fwd_note = config.work_forward_note.get(
                    lang, config.work_forward_note["en"]
                ).format(sender=thesender)

                print(f"WorkEmail ({lang}):", thesender)

                reply_msg = email_utils.build_message(
                    subject=subject,
                    from_addr=config.work_reply_from,
                    to_addr=thesender,
                    body=reply_body,
                    subject_prefix="Re:",
                    in_reply_to=themid,
                    reply_to=config.work_forward_to,
                    message_id_domain="away",
                )

                forward_msg = email_utils.build_message(
                    subject=subject,
                    from_addr=config.work_forward_by,
                    to_addr=config.work_forward_to,
                    body=fwd_note,
                    subject_prefix="Fwd:",
                    in_reply_to=themid,
                    reply_to=thesender,
                    attach_bytes=themail.as_bytes(),
                    attach_maintype="message",
                    attach_subtype="rfc822",
                )

                # Forward first (internal, more reliable)
                try:
                    send_fn(
                        options,
                        config.work_forward_by,
                        config.work_forward_to,
                        forward_msg,
                    )
                except smtplib.SMTPException as e:
                    print(f"Forward failed to {config.work_forward_to}: {e}")

                # Reply second (external, best-effort)
                try:
                    send_fn(options, config.work_reply_from, thesender, reply_msg)
                except smtplib.SMTPException as e:
                    print(f"Reply failed to {thesender}: {e}")

        return (res, data, seen_ids)

    return handler


def Obnoxious(config, send_fn=None):
    """
    Factory: Create handler that sends polite rejection and permanently deletes spam.
    Language is detected from Content-Language header.

    Deletes emails immediately, then uses Message-ID deduplication
    to prevent sending duplicate replies.

    Args:
        config: Configuration with templates and addresses
        send_fn: Optional (options, from_addr, to_addr, message) -> None
                 Defaults to email_utils.send_via_smtp
    """
    send_fn = send_fn or email_utils.send_via_smtp
    delete_handler = Delete()
    expunge_handler = Expunge()

    def handler(server, listofuids, options, seen_ids):
        theuids = b",".join(listofuids)
        res, data = server.uid("FETCH", theuids, "RFC822")

        delete_handler(server, listofuids, options, seen_ids)
        expunge_handler(server, listofuids, options, seen_ids)

        for ret in data:
            if isinstance(ret, (list, tuple)):
                try:
                    message = ret[1]
                except IndexError:
                    continue

                themail = email.message_from_string(message.decode("utf-8"))
                if not themail:
                    continue

                should_process, seen_ids = email_utils.should_process_message(
                    themail["Message-ID"], seen_ids
                )
                if not should_process:
                    continue

                themid = themail["Message-ID"]
                thesender = themail["Reply-To"] or themail["From"] or themail["Sender"]
                subject = themail["Subject"]

                lang = email_utils.detect_language(
                    themail, config.obnoxious_reply.keys(), default="en"
                )
                reply_body = config.obnoxious_reply.get(
                    lang, config.obnoxious_reply["en"]
                )

                print(f"Obnoxious ({lang}):", thesender)

                reply_msg = email_utils.build_message(
                    subject=subject,
                    from_addr=config.obnoxious_reply_from,
                    to_addr=thesender,
                    body=reply_body,
                    subject_prefix="Re:",
                    in_reply_to=themid,
                    message_id_domain="noteventrashcan",
                )

                try:
                    send_fn(options, config.obnoxious_reply_from, thesender, reply_msg)
                except smtplib.SMTPException as e:
                    print(f"Obnoxious reply failed to {thesender}: {e}")

        return (res, data, seen_ids)

    return handler


def Proxy(config, send_fn=None):
    """
    Factory: Create handler that fetches URLs from email body and converts to readable format.

    Args:
        config: Configuration with proxy settings
        send_fn: Optional (options, from_addr, to_addr, message) -> None
                 Defaults to email_utils.send_via_smtp
    """
    send_fn = send_fn or email_utils.send_via_smtp

    def handler(server, listofuids, options, seen_ids):
        theuids = b",".join(listofuids)
        res, data = server.uid("FETCH", theuids, "RFC822")

        for ret in data:
            seen_ids = proxy_utils.proxy_process_email(
                ret, server, options, seen_ids, config, send_fn
            )

        return (res, data, seen_ids)

    return handler


def runQueries(connection, queries, runtime_options=None):
    """
    Execute query loop with IDLE.
    Processes queries whenever mailbox changes.

    Args:
        connection: IMAP connection
        queries: List of (query_string, handlers) tuples
        runtime_options: Dict with smtp_server, smtp_user, smtp_pass
    """
    runtime_options = runtime_options or {}

    result = "OK"
    response = True

    processed_message_ids = set()
    previous_message_ids = set()

    while result == "OK":
        if response:
            print(time.strftime("%Y.%m.%d %H.%M.%S"), response)

            previous_message_ids = processed_message_ids
            processed_message_ids = set()

            for query_def in queries:
                query, handler_funcs = query_def

                result, data = connection.uid("SEARCH", None, query)

                if result == "OK":
                    listofuids = data[0].split()
                    if len(listofuids) > 0:
                        seen_ids = processed_message_ids | previous_message_ids

                        for handlef in handler_funcs:
                            if result == "OK":
                                result, data, seen_ids = handlef(
                                    connection, listofuids, runtime_options, seen_ids
                                )

                        processed_message_ids = seen_ids - previous_message_ids

        (result, response) = imap_utils.idle(connection)
