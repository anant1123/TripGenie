"""Currency conversion using Frankfurter (free, no API key, European Central Bank rates)."""
import time
from typing import Dict, Optional, Tuple

import requests

from utils.logger import get_logger

logger = get_logger(__name__)

RATES_URL = "https://api.frankfurter.dev/v1/latest"
CACHE_SECONDS = 6 * 3600  # rates change once a day, so 6 hours is plenty


class CurrencyService:
    """Gives the exchange rate from INR (the currency all plans use) to another currency."""

    def __init__(self):
        self._cache: Dict[str, Tuple[float, float]] = {}  # currency -> (time, rate)

    def get_rate_from_inr(self, currency: str) -> Optional[float]:
        """How much 1 INR is worth in `currency`. Returns None if the rate cannot be loaded."""
        if currency == "INR":
            return 1.0

        cached = self._cache.get(currency)
        if cached and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]

        try:
            response = requests.get(RATES_URL, params={"base": "INR", "symbols": currency}, timeout=10)
            response.raise_for_status()
            rate = float(response.json()["rates"][currency])
        except (requests.RequestException, KeyError, ValueError, TypeError) as error:
            logger.warning(f"Could not load the INR->{currency} rate: {error}")
            return None

        self._cache[currency] = (time.time(), rate)
        return rate
