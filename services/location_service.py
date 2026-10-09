"""Location search using OpenStreetMap Nominatim (free, no API key)."""
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Location:
    """One place found by the search."""

    label: str  # full name shown in the picker, e.g. "Kota, Ladpura Tehsil, Kota, Rajasthan, India"
    lat: float
    lon: float
    city: str = ""
    state: str = ""
    country: str = ""

    @classmethod
    def from_nominatim(cls, data: dict) -> "Location":
        """Build a Location from one Nominatim result. Raises KeyError/ValueError if lat/lon are missing."""
        address = data.get("address", {})
        return cls(
            label=data.get("display_name", ""),
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            city=address.get("city") or address.get("town") or address.get("village") or "",
            state=address.get("state", ""),
            country=address.get("country", ""),
        )

    def short_name(self) -> str:
        """A short readable name: 'Kota, Rajasthan, India'."""
        parts = [part for part in (self.city, self.state, self.country) if part]
        if parts:
            return ", ".join(parts)
        # No address details (for example a landmark): use the first parts of the long name
        return ", ".join(self.label.split(", ")[:3])


class LocationService:
    """Searches places. Results are remembered, so repeated searches cost nothing."""

    def __init__(self):
        self.config = settings.location
        self._cache: Dict[str, Tuple[float, List[Location]]] = {}
        self._last_request_time = 0.0
        # Many visitors share one LocationService, so requests wait for each other
        # (Nominatim allows only 1 request per second).
        self._lock = threading.Lock()

    def search(self, query: str, limit: Optional[int] = None) -> List[Location]:
        """Find places that match the text. Returns an empty list if nothing is found."""
        query = (query or "").strip()
        if len(query) < 2:
            return []

        limit = limit or self.config.max_results
        cache_key = f"{query.lower()}|{limit}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < self.config.cache_seconds:
            return cached[1]

        locations = self._fetch(query, limit)
        if locations is None:  # network problem: do not remember it, try again next time
            return []
        self._cache[cache_key] = (time.time(), locations)
        return locations

    def geocode_place(self, place: str, near: str) -> Optional[Tuple[float, float]]:
        """Find the coordinates of one place near a city. Returns (lat, lon) or None."""
        results = self.search(f"{place}, {near}", limit=1)
        return (results[0].lat, results[0].lon) if results else None

    def _fetch(self, query: str, limit: int) -> Optional[List[Location]]:
        """Call Nominatim. Returns None if the request failed."""
        params = {"q": query, "format": "json", "limit": limit, "addressdetails": 1}
        headers = {"User-Agent": self.config.user_agent}

        with self._lock:
            # Wait if the last request was less than 1 second ago
            wait = self.config.rate_limit_delay - (time.time() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)
            start = time.time()
            try:
                response = requests.get(
                    self.config.nominatim_url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as error:
                logger.error(f"Location search failed for '{query}': {error}")
                return None
            finally:
                self._last_request_time = time.time()

        locations = []
        for item in data:
            try:
                locations.append(Location.from_nominatim(item))
            except (KeyError, ValueError, TypeError):
                continue  # skip results without usable coordinates

        logger.log_search(query, len(locations), time.time() - start)
        return locations
