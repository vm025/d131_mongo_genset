"""Data-access layer.

`EventRepository` is an abstraction (Dependency Inversion): the rest of the app
only depends on it, so MongoDB or demo data can be swapped without other changes.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from dashboard import config as cfg
from dashboard.models import Event

IST = ZoneInfo(cfg.TIMEZONE)
_IST_OFFSET = timedelta(hours=5, minutes=30)




class EventRepository(ABC):
    @abstractmethod
    def fetch_events(self, start: datetime, end: datetime) -> list[Event]:
        """Return events in [start, end) PLUS context events (the last event before
        `start` and the first one at/after `end` for each genset) so that runs
        crossing the month boundaries are computed correctly."""


# ------------------------------------------------------------------ MongoDB
class MongoEventRepository(EventRepository):
    """Reads events from MongoDB. Does no processing beyond normalising fields."""

    def __init__(self, client: MongoClient):
        self._coll = client[cfg.DB_NAME][cfg.COLLECTION_NAME]

    # --- timezone helpers -------------------------------------------------
    @staticmethod
    def _to_db(ist_naive: datetime):
        """Query bound in the format stored in the DB."""
        if cfg.TIMESTAMP_IS_STRING:
            # ISO strings sort lexicographically, so a string range query works
            # (assumes the stored strings carry IST, e.g. "...+05:30").
            return ist_naive.strftime("%Y-%m-%dT%H:%M:%S")
        return ist_naive if cfg.STORED_AS_IST_WALL_CLOCK else ist_naive - _IST_OFFSET

    @staticmethod
    def _from_db(value) -> datetime:
        """Stored value (datetime or ISO string) -> naive IST datetime."""
        if isinstance(value, str):
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if value.tzinfo is not None:                       # tz-aware -> IST
            return value.astimezone(IST).replace(tzinfo=None)
        return value if cfg.STORED_AS_IST_WALL_CLOCK else value + _IST_OFFSET

    def _to_event(self, doc: dict) -> Event | None:
        status = str(doc.get(cfg.FIELD_STATUS, "")).strip().lower()
        genset = str(doc.get(cfg.FIELD_GENSET, "")).strip().upper()
        ts = doc.get(cfg.FIELD_TIMESTAMP)
        if status not in ("on", "off") or genset not in cfg.GENSETS or ts is None:
            return None                                    # ignore malformed rows
        try:
            return Event(genset, status == "on", self._from_db(ts))
        except (ValueError, TypeError):
            return None                                    # unparsable timestamp

    # --- public API -------------------------------------------------------
    def fetch_events(self, start: datetime, end: datetime) -> list[Event]:
        ts_f, name_f = cfg.FIELD_TIMESTAMP, cfg.FIELD_GENSET
        s, e = self._to_db(start), self._to_db(end)
        docs = list(self._coll.find(
            {ts_f: {"$gte": s, "$lt": e}, name_f: {"$in": list(cfg.GENSETS)}}
        ))
        for g in cfg.GENSETS:                              # context events
            prev = self._coll.find_one({name_f: g, ts_f: {"$lt": s}}, sort=[(ts_f, -1)])
            nxt = self._coll.find_one({name_f: g, ts_f: {"$gte": e}}, sort=[(ts_f, 1)])
            docs += [d for d in (prev, nxt) if d]
        events = (self._to_event(d) for d in docs)
        return sorted((ev for ev in events if ev), key=lambda ev: ev.timestamp)


    def diagnose(self) -> dict:
        """Quick health-check of the collection (shown in the UI's diagnostics panel)."""
        sample = self._coll.find_one()
        expected = [cfg.FIELD_GENSET, cfg.FIELD_STATUS, cfg.FIELD_TIMESTAMP]
        return {
            "database": cfg.DB_NAME,
            "collection": cfg.COLLECTION_NAME,
            "total_documents": self._coll.count_documents({}),
            "fields_in_sample": list(sample) if sample else [],
            "missing_expected_fields": [f for f in expected if not sample or f not in sample],
            "timestamp_type_in_sample": type(sample.get(cfg.FIELD_TIMESTAMP)).__name__ if sample else None,
            "sample_document": {k: str(v) for k, v in sample.items()} if sample else None,
        }


# --------------------------------------------------------------- Demo data
class DemoEventRepository(EventRepository):
    """Deterministic synthetic data used when USE_DB is False."""

    def fetch_events(self, start: datetime, end: datetime) -> list[Event]:
        rng = random.Random(start.year * 100 + start.month)
        horizon = end + timedelta(days=1)
        events: list[Event] = []
        # Each genset is generated independently, so ABC and DEF may run in
        # parallel; but within ONE genset the next run always starts after the
        # previous one has stopped (a genset cannot be switched on twice).
        for genset in cfg.GENSETS:
            cursor = start - timedelta(days=1)
            while cursor < horizon:
                on = cursor + timedelta(minutes=rng.randint(30, 12 * 60))
                off = on + timedelta(minutes=rng.randint(20, 300))   # may pass midnight
                if on >= horizon:
                    break
                events += [Event(genset, True, on), Event(genset, False, off)]
                cursor = off
        return sorted(events, key=lambda ev: ev.timestamp)


# ------------------------------------------------------------------ Factory
def build_mongo_client(username: str, password: str) -> MongoClient:
    uri = (f"mongodb+srv://{quote_plus(username)}:{quote_plus(password)}"
           f"@{cfg.MONGO_HOST}/?retryWrites=true&w=majority")
    return MongoClient(uri, serverSelectionTimeoutMS=8000, tz_aware=False)
