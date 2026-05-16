"""
Normalize agro / weekly PDF metadata into ``PDFMeta`` objects.
"""

from __future__ import annotations

import logging

from models.schemas import PDFMeta

logger = logging.getLogger(__name__)


def normalize_pdf(raw: dict, pdf_type: str) -> PDFMeta:
    """Wrap raw service output into a ``PDFMeta`` schema."""
    return PDFMeta(
        type=pdf_type,
        title=raw.get("title"),
        url=raw.get("url"),
        last_modified=raw.get("last_modified"),
    )
