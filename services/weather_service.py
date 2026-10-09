"""Weather for the trip dates, using Open-Meteo (free, no API key)."""
from datetime import date, timedelta
from typing import Optional

import requests

from utils.logger import get_logger

logger = get_logger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_DAYS_AHEAD = 15  # the forecast service looks about 2 weeks ahead


def get_weather(lat: float, lon: float, start: date, days: int) -> Optional[dict]:
    """Get daily weather for the trip.

    If the whole trip is within the next ~2 weeks we use the real forecast.
    Otherwise we show the weather of the SAME dates last year (a rough guide only).
    Returns None if the weather service cannot be reached.
    """
    end = start + timedelta(days=days - 1)

    if end <= date.today() + timedelta(days=FORECAST_DAYS_AHEAD):
        url, kind = FORECAST_URL, "forecast"
        first, last = start, end
    else:
        url, kind = ARCHIVE_URL, "last_year"
        first, last = start - timedelta(days=365), end - timedelta(days=365)

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "start_date": first.isoformat(),
        "end_date": last.isoformat(),
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        daily = response.json()["daily"]
    except (requests.RequestException, KeyError, ValueError) as error:
        logger.warning(f"Weather lookup failed: {error}")
        return None

    rows = []
    for index, temp_max in enumerate(daily.get("temperature_2m_max", [])):
        temp_min = daily["temperature_2m_min"][index]
        rain = daily["precipitation_sum"][index]
        if temp_max is None or temp_min is None:
            continue  # no data for this day
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),  # always show the TRIP date
                "temp_min": round(temp_min),
                "temp_max": round(temp_max),
                "rain_mm": round(rain or 0, 1),
            }
        )
    return {"kind": kind, "days": rows} if rows else None


def weather_to_text(weather: Optional[dict]) -> str:
    """Turn the weather into text for the AI prompt."""
    if not weather:
        return "Weather information is not available."
    if weather["kind"] == "forecast":
        header = "Weather forecast for the trip:"
    else:
        header = "Weather on the same dates LAST YEAR (not a forecast, only a rough guide):"
    lines = [header]
    for day in weather["days"]:
        lines.append(f"{day['date']}: {day['temp_min']}-{day['temp_max']} C, rain {day['rain_mm']} mm")
    return "\n".join(lines)
