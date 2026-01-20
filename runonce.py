#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single-run email processor.
Connects to IMAP, processes inbox once, and exits.
"""

import config_data
import config_queries
import handlers
import imap_utils

password = imap_utils.get_credential("EMAIL_PASSWORD", "password", "Password: ")
imap_utils.run(config_data, config_queries.Queries, handlers, password, once=True)
