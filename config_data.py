# -*- coding: utf-8 -*-
"""
Configuration data: servers, addresses, templates, and limits.
Pure data only - no functions, no side effects at import time.
"""

import os

# ============================================================================
# SERVER SETTINGS
# ============================================================================

imap_server = "imap.provider.com"
imap_user = "username"
smtp_server = "smtp.provider.com"
smtp_user = imap_user

inbox = "INBOX"

# ============================================================================
# DOMAIN AND IDENTITY
# ============================================================================

mydomain = "@example.com"
proxy_to = "ae2931cf" + mydomain

# ============================================================================
# FILTER ADDRESSES - which emails trigger which handlers
# ============================================================================

work_senders = ["boss@", "@workplace.edu"]

newsletters = [
    "newsletter@",
    "digest@",
    "weekly@",
    "updates@",
    "noreply@medium.com",
    "notifications@github.com",
]

for_the_record_only = ["allanswered@", "archive@"]

obnoxious_senders = ["spam@", "marketing@annoyingcompany.com"]

# ============================================================================
# HANDLER EMAIL ADDRESSES
# ============================================================================

# Work auto-responder
work_forward_to = "Work <user@workplace.edu>"
work_reply_from = "Answermachine <answermachine" + mydomain + ">"
work_forward_by = "Answermachine <work-forwarder" + mydomain + ">"

# Obnoxious handler
obnoxious_reply_from = "Answermachine <devnull" + mydomain + ">"

# Proxy handler
proxy_send_from = "Proxy <proxy" + mydomain + ">"
proxy_store_to = "INBOX.Later"

# Kindle integration
kindle_send_from = "Kindle <kindle" + mydomain + ">"
kindle_send_to = "myaccount@kindle.com"

# ============================================================================
# REPLY TEMPLATES
# ============================================================================

work_reply = {
    "en": """Work-related emails should be sent to user@workplace.edu

This email will now be forwarded there.""",
    "de": """Die Arbeit betreffende E-Mails bitte an user@workplace.edu senden.

Diese E-Mail wird jetzt dorthin weitergeleitet.""",
}

work_forward_note = {
    "en": "Forwarded message from {sender}",
    "de": "Weitergeleitete Nachricht von {sender}",
}

obnoxious_reply = {
    "en": """Hello,

This is an automated response.

Your email has been filtered as unsolicited correspondence and will not be delivered.

If you believe this classification is incorrect, please contact me through official channels.

Best regards
""",
    "de": """Guten Tag,

dies ist eine automatische Antwort.

Ihre E-Mail wurde als unerwünschte Korrespondenz eingestuft und wird nicht zugestellt.

Falls Sie glauben, dass diese Einordnung nicht korrekt ist, kontaktieren Sie mich bitte über offizielle Kanäle.

Mit freundlichen Grüßen
""",
}

# ============================================================================
# HTTP SETTINGS
# ============================================================================

# Common mobile user agent - appears as iPhone Safari
http_user_agent = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# ============================================================================
# FETCH SETTINGS
# ============================================================================

default_fetch_timeout = 30
default_max_download_size = 100 * 1024 * 1024  # 100MB
default_image_timeout = 10
default_max_images = 100

# ============================================================================
# CACHE SETTINGS
# ============================================================================

cache_prefix = os.path.expanduser(os.environ.get("CACHE_PREFIX", "~/.mailbot_cache"))

# ============================================================================
# DEOBFUSCATORS
# ============================================================================

deobfuscators = {
    "spiegel.de": "deobfuscate_spiegel",
}
