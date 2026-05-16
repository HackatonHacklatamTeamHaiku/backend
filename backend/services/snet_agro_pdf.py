"""
Extract the latest agro bulletin PDF URL from the SNET viewer page.
"""

from __future__ import annotations

import logging
import re

from config import Config
from utils.http import get_html, head

logger = logging.getLogger(__name__)


def fetch() -> dict:
    """Return ``{"url": ..., "title": ..., "last_modified": ...}``."""
    logger.info("Fetching agro bulletin PDF metadata from SNET")
    html = get_html(Config.SNET_AGRO_VIEWER_URL)

    # Look for boletin PDF links
    pdf_urls = re.findall(
        r'(https?://[^\s"\'<>]*boletin[^\s"\'<>]*\.pdf)',
        html,
        re.IGNORECASE,
    )

    if not pdf_urls:
        # Fallback: any .pdf link
        pdf_urls = re.findall(
            r'(https?://[^\s"\'<>]+\.pdf)', html, re.IGNORECASE
        )

    if not pdf_urls:
        logger.warning("No PDF link found on the agro viewer page")
        return {"url": None, "title": None, "last_modified": None}

    # Pick the last (latest numbered) bulletin
    url = pdf_urls[-1]
    filename = url.rsplit("/", 1)[-1].replace(".pdf", "")

    # Try HEAD for last-modified
    last_modified = None
    try:
        headers = head(url)
        last_modified = headers.get("Last-Modified")
    except Exception:
        logger.warning("HEAD request failed for agro PDF: %s", url)

    return {"url": url, "title": filename, "last_modified": last_modified}
