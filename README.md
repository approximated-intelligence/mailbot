# Mailbot

A personal IMAP email automation system that runs continuously, filtering, routing, and responding to emails as they arrive.

## Why

I wanted help with inbox zero. This daemon monitors my inbox via IMAP IDLE and automatically:

- Forwards work emails to my work account (and tells colleagues where to reach me)
- Moves newsletters to a "Later" folder
- Archives emails I only need for the record
- Politely rejects persistent spam with an auto-reply, then deletes without trace
- Fetches URLs from emails, converts, stores and forwards them using readable format (useful for Kindle)

## Structure

- `config_data.py` — All configuration: servers, addresses, templates
- `config_queries.py` — Rules wiring email patterns to handlers
- `query_dsl.py` — DSL for building IMAP SEARCH queries
- `handlers.py` — Handler factories (WorkEmail, Obnoxious, Proxy, Move, etc.)
- `runonce.py` — Process inbox until first failure (loops with IMAP IDLE
- `runloop.py` — Daemon entry point (runs forever with exponential retry)

Supporting modules: `email_utils.py`, `http_utils.py`, `html_utils.py`, `imap_utils.py`, `proxy_utils.py`

## Usage

```bash
# Set password via environment
export EMAIL_PASSWORD="..."
python runloop.py

# Or pass via command line
python runloop.py --password=...

# Or get prompted
python runloop.py
```

## Proxy Options

Send an email to your proxy address with options encoded in the To address:

| Option    | Effect                                      |
|-----------|---------------------------------------------|
| `txt`     | Convert HTML to plain text                  |
| `bleach`  | Sanitize HTML (remove scripts, styles)      |
| `images`  | Inline images as base64 data URIs           |
| `wolinks` | Plain text without links                    |
| `inline`  | Content in email body (not as attachment)   |
| `kindle`  | Send via SMTP to configured Kindle address  |

Combine options: `txt+bleach+kindle+proxy@example.com`

## Environment Variables

| Variable         | Default               | Description                        |
|------------------|-----------------------|------------------------------------|
| `EMAIL_PASSWORD` | (prompt)              | IMAP/SMTP password                 |
| `CACHE_PREFIX`   | `~/.mailbot_cache`  | Directory for HTTP response cache  |

## Reconnection

The daemon (`runloop.py`) automatically reconnects on connection failures using exponential backoff:

- Initial delay: 60 seconds
- Doubles on each failure: 60s → 120s → 240s → ...
- Capped at 1 hour maximum
- Resets to 60 seconds on successful connection

## Customization

Edit `config_data.py` for your servers and addresses. Edit `config_queries.py` to define your own rules. The query DSL reads naturally:

```python
Match(AllOf(Froms("@workplace.edu"), Not(Tos("@private.com"))))
```

## Tests

```bash
python -m pytest tests/ -v
```

## Dependencies

- `lxml`
- `html2text`

## License

MIT
