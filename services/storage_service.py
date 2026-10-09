"""
Saves the trip history.

Two modes (chosen by STORAGE_MODE in .env, see config/settings.py):
- file mode:   history is saved in data/trip_history.json   (running on your own computer)
- memory mode: history only lives in the visitor's session  (public website, so people
               never see each other's trips)
"""
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from models import TripRequest
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TripRecord:
    """One saved trip."""

    id: str
    timestamp: str
    from_city: str
    to_city: str
    days: int
    people: int
    group_type: str = ""
    start_date: str = ""
    plan: dict = field(default_factory=dict)  # the TripPlan as a dict
    legacy_text: str = ""  # trips saved by version 1 were plain text

    @classmethod
    def from_dict(cls, data: dict) -> "TripRecord":
        data = dict(data)
        if "trip_plan" in data:  # old name used by version 1
            data["legacy_text"] = data.pop("trip_plan")
        known = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


class TripStorage:
    """Save, list, update and delete trips."""

    def __init__(self, storage_path: Optional[Path] = None):
        """storage_path=None means memory mode."""
        self.path = Path(storage_path) if storage_path else None
        self._memory_records: List[Dict] = []
        # Many visitors can use the app at the same time, so one change happens at a time
        self._lock = threading.Lock()

        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write_all([])

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------
    def save_trip(self, request: TripRequest, plan: dict) -> str:
        """Save a new trip and return its id."""
        record = TripRecord(
            id=uuid.uuid4().hex[:12],  # random id, so two saves can never clash
            timestamp=datetime.now().isoformat(timespec="seconds"),
            from_city=request.from_city,
            to_city=request.to_city,
            days=request.days,
            people=request.people,
            group_type=request.group_type,
            start_date=request.start_date,
            plan=plan,
        )
        with self._lock:
            records = self._read_all()
            records.append(asdict(record))
            self._write_all(records)
        logger.info(f"Saved trip {record.id}")
        return record.id

    def update_plan(self, trip_id: str, plan: dict) -> bool:
        """Replace the plan of a saved trip (used after a follow-up change)."""
        with self._lock:
            records = self._read_all()
            for record in records:
                if record.get("id") == trip_id:
                    record["plan"] = plan
                    self._write_all(records)
                    return True
        return False

    def get_all_trips(self, limit: Optional[int] = None) -> List[TripRecord]:
        """All saved trips, newest first."""
        with self._lock:
            raw_records = self._read_all()

        trips = []
        for raw in raw_records:
            try:
                trips.append(TripRecord.from_dict(raw))
            except TypeError:
                logger.warning("Skipped a saved trip that could not be read")
        trips.sort(key=lambda trip: trip.timestamp, reverse=True)
        return trips[:limit] if limit else trips

    def delete_trip(self, trip_id: str) -> bool:
        """Delete one trip. Returns False if it was not found."""
        with self._lock:
            records = self._read_all()
            kept = [record for record in records if record.get("id") != trip_id]
            if len(kept) == len(records):
                return False
            self._write_all(kept)
        return True

    def clear_all(self) -> None:
        """Delete every saved trip."""
        with self._lock:
            self._write_all([])

    def export_json(self) -> str:
        """All trips as JSON text (for a download button)."""
        with self._lock:
            return json.dumps(self._read_all(), indent=2, ensure_ascii=False)

    def import_json(self, text: str) -> int:
        """Add trips from JSON text made by export_json(). Returns how many were added."""
        try:
            imported = json.loads(text)
        except json.JSONDecodeError:
            return 0
        if not isinstance(imported, list):
            return 0

        with self._lock:
            records = self._read_all()
            known_ids = {record.get("id") for record in records}
            added = 0
            for item in imported:
                if not isinstance(item, dict):
                    continue
                if item.get("id") in known_ids or not item.get("id"):
                    item["id"] = uuid.uuid4().hex[:12]
                known_ids.add(item["id"])
                records.append(item)
                added += 1
            self._write_all(records)
        return added

    # ------------------------------------------------------------------
    # Reading and writing (the lock is already held when these are called)
    # ------------------------------------------------------------------
    def _read_all(self) -> List[Dict]:
        if self.path is None:
            return list(self._memory_records)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            # The file is damaged. Move it aside (do NOT lose it) and start with an empty list.
            broken = self.path.with_name(f"{self.path.stem}.damaged-{datetime.now():%Y%m%d-%H%M%S}.json")
            self.path.replace(broken)
            logger.error(f"History file was damaged. It was moved to {broken.name}")
            return []
        except FileNotFoundError:
            return []

    def _write_all(self, records: List[Dict]) -> None:
        if self.path is None:
            self._memory_records = list(records)
            return
        # Write to a temporary file first, then swap it in. If the computer crashes
        # half-way, the old history file is still complete.
        temp_path = self.path.with_name(self.path.name + ".tmp")
        temp_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, self.path)
