"""
Extract the latest weekly forecast PDF URL from the SNET page.
"""

from __future__ import annotations

import logging
import re

from config import Config
from utils.http import get_html, head

logger = logging.getLogger(__name__)


def fetch() -> dict:
    """Return ``{"url": ..., "title": ..., "last_modified": ...}``."""
    logger.info("Fetching weekly forecast PDF metadata from SNET")
    html = get_html(Config.SNET_WEEKLY_PDF_PAGE_URL)

    # Look for direct .pdf links in the page
    pdf_urls = re.findall(
        r'href=["\']([^"\']*\.pdf)["\']', html, re.IGNORECASE
    )
    if not pdf_urls:
        # Try to find any embedded PDF URL
        pdf_urls = re.findall(
            r'(https?://[^\s"\'<>]+\.pdf)', html, re.IGNORECASE
        )

    if not pdf_urls:
        logger.warning("No PDF link found on the weekly forecast page")
        return {"url": None, "title": None, "last_modified": None}

    # Pick the last one (usually the most recent)
    url = pdf_urls[-1]

    # Make URL absolute if needed
    if url.startswith("/"):
        url = "https://www.snet.gob.sv" + url

    # Extract a title from the filename
    filename = url.rsplit("/", 1)[-1].replace(".pdf", "")

    # Try HEAD for last-modified
    last_modified = None
    try:
        headers = head(url)
        last_modified = headers.get("Last-Modified")
    except Exception:
        logger.warning("HEAD request failed for weekly PDF: %s", url)

    return {"url": url, "title": filename, "last_modified": last_modified}
