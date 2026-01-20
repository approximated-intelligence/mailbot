# -*- coding: utf-8 -*-
"""
Email utilities: parsing, construction, language detection, SMTP sending.
Uses the modern EmailMessage API (Python 3.6+).
"""

import email
import email.message
import email.policy
import email.utils
import smtplib


EMAIL_POLICY = email.policy.EmailPolicy(utf8=True)


# ============================================================================
# Message deduplication
# ============================================================================


def should_process_message(message_id, seen_ids):
    """
    Check if message should be processed based on Message-ID deduplication.

    Args:
        message_id: The Message-ID header value
        seen_ids: Set of already processed message IDs

    Returns:
        (should_process, updated_seen_ids) tuple
    """
    if message_id in seen_ids:
        return False, seen_ids
    return True, seen_ids | {message_id}


# ============================================================================
# Language detection
# ============================================================================


def detect_language(email_message, available_languages, default="en"):
    """
    Detect language from Content-Language header.

    Args:
        email_message: Parsed email message
        available_languages: List/keys of supported language codes
        default: Fallback language code

    Returns:
        Language code (e.g., "de", "en")
    """
    content_lang = email_message.get("Content-Language", "")
    for lang in available_languages:
        if lang in content_lang.lower():
            return lang

    return default


# ============================================================================
# Email construction
# ============================================================================


def build_message(
    *,
    subject,
    from_addr,
    to_addr,
    body,
    subject_prefix=None,
    in_reply_to=None,
    reply_to=None,
    message_id=None,
    message_id_domain=None,
    content_language=None,
    attach_bytes=None,
    attach_maintype=None,
    attach_subtype=None,
    attach_filename=None,
):
    """
    Build an email message.

    Args:
        subject: Email subject
        from_addr: Sender address
        to_addr: Recipient address
        body: Message body (string)
        subject_prefix: Optional prefix ('Re:', 'Fwd:', etc.)
        in_reply_to: Optional Message-ID being replied to/forwarded
        reply_to: Optional Reply-To address
        message_id: Optional explicit Message-ID (overrides message_id_domain)
        message_id_domain: Optional domain for Message-ID generation
        content_language: Optional Content-Language header
        attach_bytes: Optional attachment content (bytes)
        attach_maintype: Attachment MIME main type (e.g., 'message', 'application')
        attach_subtype: Attachment MIME subtype (e.g., 'rfc822', 'pdf')
        attach_filename: Optional attachment filename

    Returns:
        EmailMessage object
    """
    msg_subject = f"{subject_prefix} {subject}" if subject_prefix else subject

    msg = email.message.EmailMessage(policy=EMAIL_POLICY)
    msg["Subject"] = msg_subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    if reply_to:
        msg["Reply-To"] = reply_to

    if message_id:
        msg["Message-ID"] = message_id
    elif message_id_domain:
        msg["Message-ID"] = email.utils.make_msgid(domain=message_id_domain)
    else:
        msg["Message-ID"] = email.utils.make_msgid()

    msg["Date"] = email.utils.formatdate(localtime=True)

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    msg.set_content(body)

    if content_language:
        msg["Content-Language"] = content_language

    if attach_bytes is not None:
        if attach_filename:
            msg.add_attachment(
                attach_bytes,
                maintype=attach_maintype,
                subtype=attach_subtype,
                filename=attach_filename,
            )
        else:
            msg.add_attachment(
                attach_bytes,
                maintype=attach_maintype,
                subtype=attach_subtype,
            )

    return msg


# ============================================================================
# SMTP sending
# ============================================================================


def send_via_smtp(options, from_addr, to_addr, message):
    """
    Send message via SMTP with connection handling.

    Args:
        options: Dict with smtp_server, smtp_user, smtp_pass
        from_addr: Sender address
        to_addr: Recipient address (or list)
        message: EmailMessage object or string or bytes
    """
    smtp_connection = smtplib.SMTP_SSL(options["smtp_server"])
    smtp_connection.login(options["smtp_user"], options["smtp_pass"])
    try:
        match message:
            case str() | bytes():
                msg_data = message
            case _:
                msg_data = message.as_bytes()
        smtp_connection.sendmail(from_addr, to_addr, msg_data)
    finally:
        smtp_connection.quit()


# ============================================================================
# Email parsing
# ============================================================================


def decode_part(part):
    """
    Decode a single MIME part to string.

    Args:
        part: MIME part

    Returns:
        Decoded string or None on failure
    """
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return None

        charset = part.get_content_charset() or "utf-8"

        for encoding in [charset, "utf-8", "iso-8859-1"]:
            try:
                return payload.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue

        return payload.decode("utf-8", errors="replace")
    except Exception:
        return None


def get_decoded_email_body(msg):
    """
    Decode email body.
    Extract text/plain, fallback to text/html.

    Args:
        msg: Parsed email message

    Returns:
        Message body as unicode string
    """
    if msg.is_multipart():
        text_part = None
        html_part = None

        for part in msg.iter_parts():
            content_type = part.get_content_type()

            if content_type == "text/plain" and text_part is None:
                text_part = decode_part(part)
            elif content_type == "text/html" and html_part is None:
                html_part = decode_part(part)

        return (text_part or html_part or "").strip()
    else:
        return (decode_part(msg) or "").strip()
