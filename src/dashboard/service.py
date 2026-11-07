"""Application service: orchestrates repository + processor."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from dashboard import config as cfg
from dashboard.processor import build_runs, month_window, runs_to_daily
from dashboard.repository import EventRepository

  
class UsageService:
    def __init__(self, repository: EventRepository):
        self._repo = repository

    def daily_usage(self, year: int, month: int) -> pd.DataFrame:
        start, end = month_window(year, month)
        events = self._repo.fetch_events(start, end)
        now_ist = datetime.now(ZoneInfo(cfg.TIMEZONE)).replace(tzinfo=None)
        # A genset still running is counted up to "now" (or month end if in the past)
        runs = build_runs(events, open_run_end=min(end, now_ist))
        return runs_to_daily(runs, start, end)
