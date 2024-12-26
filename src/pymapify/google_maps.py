from __future__ import annotations

import logging
import re

import requests

_logger = logging.getLogger(__name__)


def extractCoordinates(full_url: str) -> tuple[float | None, ...]:
    """Extract latitude and longitude from full URL."""
    pattern = r'@(-?\d+\.\d+),(-?\d+\.\d+)'  # Matches "@latitude,longitude"
    match = re.search(pattern, full_url)
    if match:
        latitude, longitude = match.groups()
        return float(latitude), float(longitude)
    return None, None


def extractPlaceName(full_url: str) -> str:
    """Extract address or place name from the URL."""
    pattern = r'/maps/place/([^/]+)'  # Matches "/maps/place/Place+Name"
    match = re.search(pattern, full_url)
    if not match:
        return ""
    place_name = match.group(1).replace("+", " ")  # Decode "+" into spaces
    return place_name


def resolveShortenedURL(short_url: str) -> str | None:
    try:
        response = requests.get(short_url, allow_redirects=True)
        if response.status_code == 200:
            return response.url
        else:
            _logger.debug(f"Failed to resolve URL: {short_url}")
            return None
    except Exception as e:
        _logger.error(f"Error resolving URL: {e}")
        return None
