#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Continuous email processor daemon.
Monitors IMAP inbox using IDLE, processes emails as they arrive.
Automatically reconnects with exponential backoff on failures.
"""

import config_data
import config_queries
import handlers
import imap_utils

password = imap_utils.get_credential("EMAIL_PASSWORD", "password", "Password: ")
imap_utils.run(config_data, config_queries.Queries, handlers, password)
