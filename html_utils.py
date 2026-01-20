# -*- coding: utf-8 -*-
"""
HTML transformation: sanitization, deobfuscation, image inlining, text conversion.
"""

import base64
import string

import html2text
import lxml.html
import lxml.html.clean

import http_utils

# Spiegel.de deobfuscation table
ourAlphabet = string.ascii_letters + string.digits + string.punctuation + "äöüÄÖÜß"
ourShiftedAlphabet = "".join([chr(ord(x) + 1) for x in ourAlphabet])
ourTable = str.maketrans(ourShiftedAlphabet, ourAlphabet)


# HTML cleaner configuration
ourCleaner = lxml.html.clean.Cleaner(
    scripts=True,
    javascript=True,
    comments=True,
    style=True,
    inline_style=True,
    links=True,
    meta=True,
    page_structure=False,
    processing_instructions=True,
    embedded=True,
    frames=True,
    forms=True,
    annoying_tags=True,
    remove_tags=["span"],
    remove_unknown_tags=True,
    safe_attrs_only=True,
    safe_attrs=[
        "abbr",
        "accesskey",
        "alt",
        "border",
        "charset",
        "checked",
        "cite",
        "clear",
        "cols",
        "colspan",
        "datetime",
        "descr",
        "dir",
        "disabled",
        "download",
        "height",
        "href",
        "hreflang",
        "id",
        "label",
        "lang",
        "longdesc",
        "maxlength",
        "media",
        "name",
        "nohref",
        "rows",
        "rowspan",
        "selected",
        "src",
        "summary",
        "tabindex",
        "title",
        "type",
        "usemap",
        "value",
        "width",
        "xml:lang",
    ],
    add_nofollow=False,
)


def deobfuscate_spiegel(tree):
    """
    Spiegel.de uses character shifting to prevent scraping.
    This reverses their obfuscation by shifting characters back.
    """
    for parent in tree.find_class("obfuscated"):
        for child in parent:
            for grandchild in child:
                for orphan in grandchild:
                    if orphan.tail:
                        orphan.tail = orphan.tail.translate(ourTable)
                if grandchild.text and not (grandchild.tag in ("a", "br")):
                    grandchild.text = grandchild.text.translate(ourTable)
                if grandchild.tail:
                    grandchild.tail = grandchild.tail.translate(ourTable)
            if child.text and not (child.tag in ("a", "br")):
                child.text = child.text.translate(ourTable)
            if child.tail:
                child.tail = child.tail.translate(ourTable)
        if parent.text:
            parent.text = parent.text.translate(ourTable)

    return tree


def apply_deobfuscation(tree, url, deobfuscators):
    """Apply registered deobfuscators based on URL"""
    for domain, func_name in deobfuscators.items():
        if domain in url:
            deobfuscator = globals().get(func_name)
            if deobfuscator and callable(deobfuscator):
                tree = deobfuscator(tree)
    return tree


def bleach_content(tree, base_href, deobfuscators=None):
    """Remove dangerous HTML elements and apply site-specific deobfuscation"""
    if deobfuscators:
        tree = apply_deobfuscation(tree, base_href, deobfuscators)

    tree = ourCleaner.clean_html(tree)
    return tree


def include_images_in_tree(tree, timeout=10, max_images=100):
    """
    Fetch and inline images as base64 data URIs.

    Args:
        tree: lxml HTML tree
        timeout: Per-image fetch timeout in seconds
        max_images: Maximum number of images to process

    Returns:
        Modified tree with inlined images
    """
    images = tree.xpath("//img")
    images_processed = 0

    for img in images:
        if images_processed >= max_images:
            img.drop_tag()
            continue

        src = img.get("src")
        awidth = img.get("width", "0")
        aheight = img.get("height", "0")

        def parse_dimension(dim_str):
            if "%" in dim_str or "auto" in dim_str or len(dim_str) < 1:
                return 100
            if "px" in dim_str:
                return int(dim_str[: dim_str.index("px")])
            if "." in dim_str:
                return int(dim_str[: dim_str.index(".")])
            return int(dim_str) if dim_str.isdigit() else 100

        width = parse_dimension(awidth)
        height = parse_dimension(aheight)
        area = width * height

        if ((area < 1) or (area >= (100 * 100))) and src:
            print(f"IMG: {src}")

            cached = http_utils.get_cached(src)
            if cached:
                all_data = cached
            else:
                try:
                    content, base_href, headers, info = http_utils.fetch_url(
                        src, timeout=timeout
                    )
                    content_base64 = base64.b64encode(content)
                    mimetype = headers.get(
                        "content-type", "application/octet-stream"
                    ).encode("ascii")
                    all_data = b"data:" + mimetype + b";base64," + content_base64

                    http_utils.store_cached(src, all_data)
                    http_utils.store_cached(base_href, all_data)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    all_data = b""

            if all_data:
                img.set("src", all_data.decode("ascii"))
                img.set("width", "100%")
                img.set("height", "auto")
                images_processed += 1
            else:
                img.drop_tag()
        else:
            img.drop_tag()

    return tree


def make_html2text_converter():
    """Create configured html2text parser for converting HTML to plain text."""
    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.single_line_break = False
    converter.ul_item_mark = "-"
    converter.emphasis_mark = "*"
    converter.strong_mark = "**"
    converter.ignore_emphasis = False
    converter.ignore_images = True
    converter.images_to_alt = True
    converter.images_with_size = False
    converter.default_image_alt = ""
    converter.hide_strikethrough = False
    converter.escape_snob = False
    converter.unicode_snob = False
    converter.ignore_tables = False
    converter.bypass_tables = False
    converter.pad_tables = False
    converter.ignore_links = False
    converter.skip_internal_links = True
    converter.use_automatic_links = False
    converter.inline_links = True
    converter.wrap_links = False
    converter.protect_links = False
    converter.links_each_paragraph = False
    converter.mark_code = True
    return converter


def transform_html_content(
    tree, base_href, config, bleach_html, include_images, as_txt, txt_without_links
):
    """
    Apply HTML transformations: bleaching, image inlining, text conversion.

    Args:
        tree: lxml HTML tree (already with absolute links)
        base_href: Base URL for deobfuscation context
        config: Configuration module with deobfuscators, timeouts, limits
        bleach_html: Whether to sanitize HTML
        include_images: Whether to inline images as base64
        as_txt: Whether to convert to plain text
        txt_without_links: Whether to strip links when converting to text

    Returns:
        (content, title, subtype, prefix) tuple
    """
    prefix = ""

    if bleach_html:
        prefix = "B" + prefix
        tree = bleach_content(tree, base_href, deobfuscators=config.deobfuscators)

    if include_images:
        prefix = "I" + prefix
        tree = include_images_in_tree(
            tree,
            timeout=config.default_image_timeout,
            max_images=config.default_max_images,
        )

    content = lxml.html.tostring(tree).decode("utf-8")

    if as_txt:
        converter = make_html2text_converter()
        if txt_without_links:
            converter.ignore_links = True
            prefix = "TP" + prefix
        else:
            prefix = "TL" + prefix
        content = converter.handle(content)
        subtype = "plain"
    else:
        subtype = "html"

    try:
        title = tree.findtext(".//title").strip()
    except AttributeError:
        title = None

    return content, title, subtype, prefix
