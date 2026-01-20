# -*- coding: utf-8 -*-
"""
Proxy handler utilities: URL fetching, option parsing, message building.
All functions prefixed with proxy_ to indicate scope.
"""

import email.parser
import imaplib
import re
import time
import traceback
import urllib.error

import lxml.html

import email_utils
import html_utils
import http_utils

# ============================================================================
# URL extraction
# ============================================================================

# Original regex (kept for documentation):
# r"http[s]?://(?:[a-zA-Z]|[0-9]|[~$-_@.&+|]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
#
# Problems with this pattern:
# - [$-_] is a range including unintended characters
# - Captures trailing punctuation like ) and ,
# - Missing common URL characters

# Current pattern:
# - Matches http:// or https://
# - Excludes characters that are never in URLs or are prose delimiters
# - Strips trailing punctuation that may be captured
_URL_PATTERN = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]'()]+")

# Valid in URLs but often appear as trailing prose punctuation
_TRAILING_PUNCTUATION = ".,;:!?*"


def _proxy_extract_urls_from_text(text):
    """
    Extract URLs from text, stripping trailing punctuation.

    Args:
        text: String to scan for URLs

    Returns:
        Set of cleaned URLs
    """
    found = _URL_PATTERN.findall(text)
    return {url.rstrip(_TRAILING_PUNCTUATION) for url in found}


def proxy_parse_options(to_addr, config, sender):
    """
    Extract processing options from To address.

    Options are encoded as substrings in the email address:
    - txt: convert to plain text
    - bleach: sanitize HTML
    - images: inline images as base64
    - wolinks: plain text without links
    - inline: content inline (not attachment)
    - kindle: send via SMTP to Kindle

    Args:
        to_addr: The To address (e.g., "txt+kindle+81823@domain")
        config: Config with proxy_to, kindle_send_from, kindle_send_to, proxy_send_from
        sender: Original sender address (for reply routing)

    Returns:
        Dict of options
    """
    to_lower = (to_addr or "").lower()
    is_kindle = "kindle" in to_lower

    return {
        "as_txt": "txt" in to_lower,
        "bleach_html": "bleach" in to_lower,
        "include_images": "images" in to_lower,
        "txt_without_links": "wolinks" in to_lower,
        "send_using_smtp": is_kindle,
        "as_inline": "inline" in to_lower,
        "send_from": config.kindle_send_from if is_kindle else config.proxy_send_from,
        "send_to": config.kindle_send_to if is_kindle else sender,
    }


def proxy_decode_text_content(content, charset):
    """
    Decode bytes to string with fallback encodings.

    Args:
        content: Bytes to decode
        charset: Declared charset to try first

    Returns:
        Decoded string with normalized newlines
    """
    content_str = None
    for encoding in [charset, "utf-8", "iso-8859-1"]:
        try:
            content_str = content.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if content_str is None:
        content_str = content.decode("utf-8", errors="replace")

    return content_str.replace("\r\n", "\n").replace("\n\r", "\n").replace("\r", "\n")


def proxy_fix_filename_extension(filename, subtype):
    """
    Ensure filename has correct extension for content type.

    Args:
        filename: Original filename
        subtype: MIME subtype ('plain', 'html', etc.)

    Returns:
        Filename with appropriate extension
    """
    if subtype == "plain" and not filename.endswith(".txt"):
        return filename + ".txt"
    if subtype == "html" and not filename.endswith(".html"):
        return filename + ".html"
    return filename


def proxy_extract_urls(themail, subject):
    """
    Extract deduplicated URLs from email body and subject.

    Args:
        themail: Parsed email message
        subject: Email subject (also scanned for URLs)

    Returns:
        Set of URLs
    """
    urls = set()

    # Extract from email body (all text parts)
    converter = html_utils.make_html2text_converter()

    parts = themail.iter_parts() if themail.is_multipart() else [themail]

    for part in parts:
        decoded = email_utils.decode_part(part)
        if not decoded:
            continue

        content_type = part.get_content_type()

        if content_type == "text/html":
            text = converter.handle(decoded)
        else:
            text = decoded

        urls.update(_proxy_extract_urls_from_text(text))

    # Extract from subject
    if subject:
        urls.update(_proxy_extract_urls_from_text(subject))

    return urls


def proxy_build_message_from_url(url, subject, ref_mid, proxy_options, config):
    """
    Fetch URL and construct email message.

    Args:
        url: URL to fetch
        subject: Base subject for email
        ref_mid: Message-ID to reference
        proxy_options: Options dict from proxy_parse_options
        config: Config with timeouts and limits

    Returns:
        Complete email message
    """
    print("Fetch URL:", url)

    content, base_href, headers, info, mimetype, subtype = (
        http_utils.fetch_and_decode_url(
            url, config.default_fetch_timeout, config.default_max_download_size
        )
    )

    filename = http_utils.get_filename_from_headers_or_url(headers, base_href)
    charset = "utf-8"
    title = subject
    prefix = ""

    if mimetype.startswith("text/"):
        charset = info.get_param("charset") or "utf-8"
        content = proxy_decode_text_content(content, charset)

        if "html" in subtype:
            tree = lxml.html.fromstring(content)
            tree.make_links_absolute(base_href, resolve_base_href=True)

            content, html_title, subtype, prefix = html_utils.transform_html_content(
                tree,
                base_href,
                config,
                proxy_options["bleach_html"],
                proxy_options["include_images"],
                proxy_options["as_txt"],
                proxy_options["txt_without_links"],
            )

            if html_title:
                title = html_title

            filename = proxy_fix_filename_extension(filename, subtype)

        elif "plain" in subtype:
            filename = proxy_fix_filename_extension(filename, "plain")

    final_subject = f"[{prefix}]: {title}" if prefix else title
    full_filename = f"{subject}: {filename}"
    maintype = mimetype.split("/")[0]

    # Text content: inline or as attachment
    if mimetype.startswith("text/"):
        if proxy_options["as_inline"]:
            msg = email_utils.build_message(
                subject=final_subject,
                from_addr=proxy_options["send_from"],
                to_addr=proxy_options["send_to"],
                body=f"{info}\n\n{content}",
                in_reply_to=ref_mid,
                message_id_domain="proxy",
            )
        else:
            msg = email_utils.build_message(
                subject=final_subject,
                from_addr=proxy_options["send_from"],
                to_addr=proxy_options["send_to"],
                body=str(info),
                in_reply_to=ref_mid,
                message_id_domain="proxy",
                attach_bytes=content.encode(charset),
                attach_maintype="text",
                attach_subtype=subtype,
                attach_filename=full_filename,
            )
    # Binary content: always as attachment
    else:
        if (
            maintype == "application"
            and "pdf" in subtype
            and not filename.endswith(".pdf")
        ):
            full_filename = f"{subject}: {filename}.pdf"
        msg = email_utils.build_message(
            subject=final_subject,
            from_addr=proxy_options["send_from"],
            to_addr=proxy_options["send_to"],
            body=str(info),
            in_reply_to=ref_mid,
            message_id_domain="proxy",
            attach_bytes=content,
            attach_maintype=maintype,
            attach_subtype=subtype,
            attach_filename=full_filename,
        )

    return msg


def proxy_fetch_and_store_url(
    url, subject, ref_mid, proxy_options, server, smtp_options, config, send_fn
):
    """
    Fetch URL, build message, store and optionally send.

    Args:
        url: URL to fetch
        subject: Email subject
        ref_mid: Message-ID to reference
        proxy_options: Options dict from proxy_parse_options
        server: IMAP connection
        smtp_options: SMTP credentials dict
        config: Config with proxy_store_to
        send_fn: Function (options, from_addr, to_addr, message) -> None
    """
    try:
        msg = proxy_build_message_from_url(url, subject, ref_mid, proxy_options, config)

        res, data = server.append(
            config.proxy_store_to.encode("ascii"),
            b"",
            imaplib.Time2Internaldate(time.time()),
            msg.as_bytes(),
        )

        print(f"APPEND to {config.proxy_store_to}: {res} {data}")

        if proxy_options["send_using_smtp"]:
            try:
                send_fn(
                    smtp_options,
                    proxy_options["send_from"],
                    proxy_options["send_to"],
                    msg,
                )
            except Exception as e:
                print(f"SMTP failed for {url}: {e}")
                traceback.print_exc()

    except urllib.error.URLError as e:
        print(f"Failed to fetch {url}: {e}")
        traceback.print_exc()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"Error processing {url}: {e}")
        traceback.print_exc()


def proxy_process_email(ret, server, smtp_options, seen_ids, config, send_fn):
    """
    Process single email for URL proxying.

    Args:
        ret: Single result from IMAP FETCH
        server: IMAP connection
        smtp_options: SMTP credentials dict
        seen_ids: Set of processed Message-IDs
        config: Config module
        send_fn: Function (options, from_addr, to_addr, message) -> None

    Returns:
        Updated seen_ids set
    """
    if not isinstance(ret, (list, tuple)):
        return seen_ids

    try:
        message = ret[1]
    except IndexError:
        return seen_ids

    themail = email.parser.Parser().parsestr(message.decode("utf-8"))
    if not themail:
        return seen_ids

    should_process, seen_ids = email_utils.should_process_message(
        themail["Message-ID"], seen_ids
    )
    if not should_process:
        return seen_ids

    subject = themail["Subject"]
    themid = themail["Message-ID"]
    thesender = themail["From"] or themail["Sender"]

    print("Proxy URLs for:", thesender)

    proxy_options = proxy_parse_options(themail["To"], config, thesender)
    urls = proxy_extract_urls(themail, subject)

    for u in urls:
        proxy_fetch_and_store_url(
            u, subject, themid, proxy_options, server, smtp_options, config, send_fn
        )

    return seen_ids
