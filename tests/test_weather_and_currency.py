from datetime import date, timedelta

import requests

from services import weather_service
from services.currency_service import CurrencyService
from services.weather_service import FORECAST_URL, get_weather, weather_to_text


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def weather_data(days: int) -> dict:
    return {
        "daily": {
            "time": ["x"] * days,
            "temperature_2m_max": [31.2] * days,
            "temperature_2m_min": [20.4] * days,
            "precipitation_sum": [0.0] * days,
        }
    }


def test_near_trip_uses_the_forecast(monkeypatch):
    urls = []

    def fake_get(url, **kwargs):
        urls.append(url)
        return FakeResponse(weather_data(2))

    monkeypatch.setattr(weather_service.requests, "get", fake_get)
    start = date.today() + timedelta(days=3)

    weather = get_weather(28.6, 77.2, start, days=2)

    assert urls == [FORECAST_URL]
    assert weather["kind"] == "forecast"
    assert weather["days"][0] == {"date": start.isoformat(), "temp_min": 20, "temp_max": 31, "rain_mm": 0.0}


def test_far_trip_uses_last_years_weather_but_shows_this_years_dates(monkeypatch):
    seen = {}

    def fake_get(url, params, **kwargs):
        seen["start_date"] = params["start_date"]
        return FakeResponse(weather_data(2))

    monkeypatch.setattr(weather_service.requests, "get", fake_get)
    start = date.today() + timedelta(days=90)

    weather = get_weather(28.6, 77.2, start, days=2)

    assert weather["kind"] == "last_year"
    assert seen["start_date"] == (start - timedelta(days=365)).isoformat()
    assert weather["days"][0]["date"] == start.isoformat()


def test_weather_failure_returns_none(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(weather_service.requests, "get", fail)
    assert get_weather(28.6, 77.2, date.today() + timedelta(days=3), days=2) is None
    assert weather_to_text(None) == "Weather information is not available."


def test_weather_text_says_when_it_is_not_a_forecast():
    weather = {"kind": "last_year", "days": [{"date": "2026-12-01", "temp_min": 8, "temp_max": 20, "rain_mm": 0.0}]}
    assert "LAST YEAR" in weather_to_text(weather)


def test_currency_rate_is_loaded_once_and_inr_needs_no_request(monkeypatch):
    calls = []

    def fake_get(url, params, **kwargs):
        calls.append(params)
        return FakeResponse({"rates": {"USD": 0.012}})

    monkeypatch.setattr("services.currency_service.requests.get", fake_get)
    service = CurrencyService()

    assert service.get_rate_from_inr("INR") == 1.0
    assert service.get_rate_from_inr("USD") == 0.012
    assert service.get_rate_from_inr("USD") == 0.012
    assert len(calls) == 1


def test_currency_failure_returns_none(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("services.currency_service.requests.get", fail)
    assert CurrencyService().get_rate_from_inr("EUR") is None
