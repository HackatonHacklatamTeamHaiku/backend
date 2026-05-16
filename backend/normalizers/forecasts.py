"""
Parse the SNET 48-hour forecast HTML page into a ``Forecast48h`` object.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from models.schemas import Forecast48h, ForecastPeriods, CityForecast

logger = logging.getLogger(__name__)


def normalize_48h(html: str) -> Forecast48h:
    """Extract structured forecast data from the SNET 48-hour HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    # ── Issue date ───────────────────────────────────────────
    issued_for = None
    next_update = None
    headline = None

    # The page typically has the date in various places; look for common patterns
    # Try to find "Viernes, 15 de Mayo de 2026" style text
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Look for date patterns like "Viernes, 15 de Mayo de 2026"
    date_pattern = re.compile(
        r"(?:Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo)"
        r",?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}",
        re.IGNORECASE,
    )
    dates = date_pattern.findall(text)
    if dates:
        issued_for = dates[0]

    # Look for "Próxima actualización" text
    update_pattern = re.compile(
        r"Pr[oó]xima\s+actualizaci[oó]n[:\s]*(.*?)(?:\n|$)", re.IGNORECASE
    )
    update_match = update_pattern.search(text)
    if update_match:
        next_update = update_match.group(1).strip()

    # ── Forecast paragraphs ──────────────────────────────────
    # Find the main content area — usually in a div with forecast text
    morning = None
    afternoon = None
    night = None

    # Look for period markers
    manana_pattern = re.compile(r"(?:ma[ñn]ana|mañana)[:\s]*(.*?)(?=(?:tarde|noche)|$)", re.IGNORECASE | re.DOTALL)
    tarde_pattern = re.compile(r"tarde[:\s]*(.*?)(?=noche|$)", re.IGNORECASE | re.DOTALL)
    noche_pattern = re.compile(r"noche[:\s]*(.*?)$", re.IGNORECASE | re.DOTALL)

    # Try to extract paragraphs from the content
    content_div = soup.find("div", class_="field-item") or soup.find("div", id="content")
    if content_div:
        paragraphs = content_div.find_all("p")
        para_texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]

        if para_texts:
            # First substantial paragraph is usually the headline
            for pt in para_texts:
                if len(pt) > 20:
                    headline = pt
                    break
    else:
        # Fallback: try to grab the first substantial text block
        for line in lines:
            if len(line) > 40 and not date_pattern.search(line):
                headline = line
                break

    # ── City temperature table ───────────────────────────────
    cities: list[CityForecast] = []
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 3:
                city_text = cells[0].get_text(strip=True)
                # Skip header rows
                if city_text.lower() in ("ciudad", "city", "localidad", "municipio", ""):
                    continue
                try:
                    max_c = float(cells[1].get_text(strip=True))
                    min_c = float(cells[2].get_text(strip=True))
                    cities.append(CityForecast(
                        city=city_text,
                        max_c=max_c,
                        min_c=min_c,
                    ))
                except (ValueError, IndexError):
                    continue

    return Forecast48h(
        issued_for=issued_for,
        next_update=next_update,
        headline=headline,
        periods=ForecastPeriods(
            morning=morning,
            afternoon=afternoon,
            night=night,
        ),
        cities=cities,
    )
