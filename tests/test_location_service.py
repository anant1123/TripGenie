import pytest
import requests

from config.settings import settings
from services.location_service import Location, LocationService

NOMINATIM_RESULT = {
    "display_name": "Kota, Ladpura Tehsil, Kota, Rajasthan, 324001, India",
    "lat": "25.18",
    "lon": "75.83",
    "address": {"city": "Kota", "state": "Rajasthan", "country": "India"},
}


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings.location, "rate_limit_delay", 0)  # no waiting in tests
    return LocationService()


def test_short_name_uses_city_state_country():
    place = Location.from_nominatim(NOMINATIM_RESULT)
    assert place.short_name() == "Kota, Rajasthan, India"
    assert place.lat == 25.18


def test_short_name_falls_back_to_the_label():
    place = Location(label="Red Fort, Chandni Chowk, Delhi, India, Earth", lat=1, lon=2)
    assert place.short_name() == "Red Fort, Chandni Chowk, Delhi"


def test_same_search_is_only_sent_once(service, monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs["params"]["q"])
        return FakeResponse([NOMINATIM_RESULT])

    monkeypatch.setattr("services.location_service.requests.get", fake_get)

    assert len(service.search("Kota")) == 1
    assert len(service.search("kota")) == 1  # same search, different capital letters
    assert calls == ["Kota"]


def test_results_without_coordinates_are_skipped(service, monkeypatch):
    broken = {"display_name": "Nowhere", "address": {}}
    monkeypatch.setattr(
        "services.location_service.requests.get", lambda *a, **k: FakeResponse([broken, NOMINATIM_RESULT])
    )
    assert len(service.search("Kota")) == 1


def test_network_error_returns_empty_list_and_is_not_cached(service, monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("services.location_service.requests.get", fail)
    assert service.search("Kota") == []

    # The internet is back: the next search must really try again
    monkeypatch.setattr("services.location_service.requests.get", lambda *a, **k: FakeResponse([NOMINATIM_RESULT]))
    assert len(service.search("Kota")) == 1


def test_geocode_place_returns_coordinates(service, monkeypatch):
    monkeypatch.setattr("services.location_service.requests.get", lambda *a, **k: FakeResponse([NOMINATIM_RESULT]))
    assert service.geocode_place("Kota Garh", "Kota") == (25.18, 75.83)
