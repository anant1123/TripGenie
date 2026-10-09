"""Opens the real Streamlit app in a test and checks that the first screen draws without errors."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from config.settings import settings

APP_FILE = str(Path(__file__).resolve().parent.parent / "app.py")


def test_missing_key_shows_a_friendly_message_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(settings.api, "groq_api_key", "")

    app = AppTest.from_file(APP_FILE).run(timeout=30)

    assert not app.exception
    assert "GROQ_API_KEY" in app.error[0].value


def test_first_screen_shows_the_form(monkeypatch):
    monkeypatch.setattr(settings.api, "groq_api_key", "test-key-not-real")
    monkeypatch.setattr(settings.api, "tavily_api_key", "")
    monkeypatch.setattr(settings.storage, "mode", "session")  # do not touch data/trip_history.json

    app = AppTest.from_file(APP_FILE).run(timeout=30)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Plan a trip", "History", "Tips"]
    assert any(button.label == "✨ Plan my trip" for button in app.button)
