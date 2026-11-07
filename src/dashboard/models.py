"""Plain data objects shared by all layers."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Event:
    """One log entry: a genset was switched ON or OFF at `timestamp` (naive IST)."""
    genset: str
    is_on: bool
    timestamp: datetime


@dataclass(frozen=True)
class Run:
    """A continuous running period of one genset (naive IST datetimes)."""
    genset: str
    start: datetime
    end: datetime
