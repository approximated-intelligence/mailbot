# -*- coding: utf-8 -*-
"""
HTTP fetching and disk caching utilities.
"""

import gzip
import hashlib
import os
import struct
import urllib.error
import urllib.request
import zlib
from io import BytesIO

import config_data

URLOpener = urllib.request.build_opener()
URLOpener.addheaders = [
    ("Cache-Control", "no-transform"),
    ("User-Agent", config_data.http_user_agent),
]


def fetch_url(url, timeout=30, max_size=100 * 1024 * 1024):
    """
    Fetch URL with timeout and size limit.

    Args:
        url: URL to fetch
        timeout: Connection timeout in seconds
        max_size: Maximum download size in bytes

    Returns:
        (content, base_href, headers, info) tuple

    Raises:
        urllib.error.URLError: On network errors
        ValueError: If content exceeds max_size
    """
    try:
        httpcon = URLOpener.open(url, timeout=timeout)

        content = httpcon.read(max_size)

        extra = httpcon.read(1)
        if extra:
            httpcon.close()
            raise ValueError(f"Content exceeds max size of {max_size} bytes")

        httpcon.close()

    except urllib.error.URLError as e:
        print(f"Failed to fetch {url}")
        if hasattr(e, "reason"):
            print("Reason:", e.reason)
        elif hasattr(e, "code"):
            print("Error code:", e.code)
        raise

    base_href = httpcon.geturl()
    headers = dict((k.lower(), v) for k, v in httpcon.headers.items())
    info = httpcon.info()

    if content and "gzip" in headers.get("content-encoding", ""):
        try:
            content = gzip.GzipFile(fileobj=BytesIO(content)).read()
        except (EOFError, IOError, struct.error):
            content = None
    elif content and "deflate" in headers.get("content-encoding", ""):
        try:
            content = zlib.decompress(content)
        except zlib.error:
            try:
                content = zlib.decompress(content, -15)
            except zlib.error:
                content = None

    return (content, base_href, headers, info)


def fetch_and_decode_url(url, timeout=30, max_size=100 * 1024 * 1024):
    """
    Fetch URL and extract mimetype information.

    Args:
        url: URL to fetch
        timeout: Connection timeout in seconds
        max_size: Maximum download size in bytes

    Returns:
        (content, base_href, headers, info, mimetype, subtype) tuple
    """
    content, base_href, headers, info = fetch_url(url, timeout, max_size)

    mimetype = headers.get("content-type", "application/octet-stream")
    reststring = mimetype.split("/", 2)[1] if "/" in mimetype else ""
    subtype = reststring.split(";", 2)[0]

    return (content, base_href, headers, info, mimetype, subtype)


def get_filename_from_headers_or_url(headers, url):
    """
    Extract filename from Content-Disposition header or URL.

    Args:
        headers: Dict of HTTP headers
        url: Fallback URL to extract filename from

    Returns:
        Filename string
    """
    if "content-disposition" in headers:
        cd = headers["content-disposition"]
        if "filename=" in cd:
            start = cd.index("filename=") + 9
            end = cd.find(";", start)
            filename = cd[start:end] if end > 0 else cd[start:]
            return filename.strip("\"'")

    name = (
        url.replace("http://", "")
        .replace("https://", "")
        .replace("/", " ")
        .replace(".", " ")
    )
    return os.path.basename(name) if name else "download"


def get_cached(url):
    """
    Get content from cache if available.

    Args:
        url: URL to check

    Returns:
        Cached content or None if not cached
    """
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = os.path.join(config_data.cache_prefix, cache_key)

    if os.path.isfile(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()

    return None


def store_cached(url, content):
    """
    Store content in cache.

    Args:
        url: URL key
        content: Content to cache
    """
    os.makedirs(config_data.cache_prefix, exist_ok=True)
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = os.path.join(config_data.cache_prefix, cache_key)

    with open(cache_path, "wb") as f:
        f.write(content)


def get_or_fetch(url, timeout=30):
    """
    Get content from cache or fetch and cache.

    Args:
        url: URL to fetch
        timeout: Connection timeout in seconds

    Returns:
        Content bytes
    """
    cached = get_cached(url)
    if cached:
        return cached

    content, _, _, _ = fetch_url(url, timeout=timeout)
    if content:
        store_cached(url, content)

    return content
