# -*- coding: utf-8 -*-
"""
Query definitions: email filtering rules with handlers.
Pure wiring - all data comes from config.
"""

import config_data as config
from handlers import Expunge
from handlers import Move
from handlers import Obnoxious
from handlers import Proxy
from handlers import SetFlags
from handlers import WorkEmail
from query_dsl import AllOf
from query_dsl import AnyOf
from query_dsl import Ccs
from query_dsl import Froms
from query_dsl import Match
from query_dsl import Not
from query_dsl import Tos

Queries = [
    # Work emails: auto-reply and forward
    (
        Match(AnyOf(Froms(*config.work_senders))),
        [WorkEmail(config), SetFlags(r"(\Seen)"), Move("INBOX.Arbeit"), Expunge()],
    ),
    # Newsletters: defer to later
    (Match(AnyOf(Tos(*config.newsletters))), [Move("INBOX.Later"), Expunge()]),
    # Received only for the Record: move and mark read
    (
        Match(AnyOf(Tos(*config.for_the_record_only))),
        [SetFlags(r"(\Seen)"), Move("INBOX.Read"), Expunge()],
    ),
    # Obnoxious senders: delete and send snarky reply
    (Match(AnyOf(Froms(*config.obnoxious_senders))), [Obnoxious(config)]),
    # Proxy: fetch URLs from email and convert to readable format
    (
        Match(AllOf(Froms(config.mydomain), Tos(config.proxy_to))),
        [Proxy(config), SetFlags(r"(\Seen)"), Move("INBOX.Read"), Expunge()],
    ),
    # Emails from self without explicit recipients: hints folder
    (
        Match(
            AllOf(
                Froms(config.mydomain),
                AnyOf(Tos(config.mydomain), Not(AnyOf(Tos("@"), Ccs("@")))),
            )
        ),
        [SetFlags(r"(\Seen)"), Move("INBOX.Hints"), Expunge()],
    ),
    # Other emails from self: mark read
    (
        Match(AnyOf(Froms(config.mydomain))),
        [SetFlags(r"(\Seen)"), Move("INBOX.Read"), Expunge()],
    ),
]
