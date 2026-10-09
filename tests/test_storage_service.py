import json

from services.storage_service import TripStorage
from tests.helpers import make_draft, make_request


def make_plan_dict() -> dict:
    return make_draft().model_dump()


def test_save_list_update_delete(tmp_path):
    storage = TripStorage(tmp_path / "history.json")
    trip_id = storage.save_trip(make_request(), make_plan_dict())

    trips = storage.get_all_trips()
    assert len(trips) == 1
    assert trips[0].id == trip_id
    assert trips[0].plan["title"] == "Delhi in 2 days"

    new_plan = make_draft(title="Changed").model_dump()
    assert storage.update_plan(trip_id, new_plan) is True
    assert storage.get_all_trips()[0].plan["title"] == "Changed"

    assert storage.delete_trip(trip_id) is True
    assert storage.get_all_trips() == []
    assert storage.delete_trip(trip_id) is False


def test_two_quick_saves_get_different_ids(tmp_path):
    storage = TripStorage(tmp_path / "history.json")
    first = storage.save_trip(make_request(), make_plan_dict())
    second = storage.save_trip(make_request(), make_plan_dict())
    assert first != second
    assert len(storage.get_all_trips()) == 2


def test_damaged_file_is_kept_and_history_is_not_silently_wiped(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    storage = TripStorage(path)

    # Saving still works ...
    storage.save_trip(make_request(), make_plan_dict())
    assert len(storage.get_all_trips()) == 1

    # ... and the damaged file was moved aside, not deleted
    damaged_files = list(tmp_path.glob("history.damaged-*.json"))
    assert len(damaged_files) == 1
    assert "not valid json" in damaged_files[0].read_text(encoding="utf-8")


def test_memory_mode_does_not_create_files(tmp_path):
    storage = TripStorage(None)
    storage.save_trip(make_request(), make_plan_dict())
    assert len(storage.get_all_trips()) == 1
    assert list(tmp_path.iterdir()) == []


def test_export_and_import_roundtrip():
    first = TripStorage(None)
    first.save_trip(make_request(), make_plan_dict())
    exported = first.export_json()

    second = TripStorage(None)
    assert second.import_json(exported) == 1
    assert second.import_json(exported) == 1  # importing twice must not clash on ids
    ids = [trip.id for trip in second.get_all_trips()]
    assert len(set(ids)) == 2


def test_import_ignores_garbage():
    storage = TripStorage(None)
    assert storage.import_json("not json") == 0
    assert storage.import_json('{"a": 1}') == 0


def test_trips_saved_by_version_1_can_still_be_read(tmp_path):
    path = tmp_path / "history.json"
    old_record = {
        "id": "20260106_093632",
        "timestamp": "2026-01-06T09:36:32",
        "from_city": "Kota",
        "to_city": "New Delhi",
        "days": 5,
        "people": 8,
        "group_type": "Friends",
        "trip_plan": "Old plan text",
    }
    path.write_text(json.dumps([old_record]), encoding="utf-8")

    trip = TripStorage(path).get_all_trips()[0]
    assert trip.legacy_text == "Old plan text"
    assert trip.plan == {}
