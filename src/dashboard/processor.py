"""Pure business logic: events -> runs -> per-day usage. No I/O, easy to test."""
from __future__ import annotations
from datetime import datetime, time, timedelta
import pandas as pd
from dashboard import config as cfg
from dashboard.models import Event, Run


def month_window(year: int, month: int) -> tuple[datetime, datetime]:
    """[start, end) of a month, as naive IST datetimes."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def build_runs(events: list[Event], open_run_end: datetime) -> list[Run]:
    """Pair ON/OFF events per genset. A run still ON at the end of the data
    is closed at `open_run_end`. Duplicate ON/OFF entries are ignored."""
    runs: list[Run] = []
    on_since: dict[str, datetime | None] = {g: None for g in cfg.GENSETS}
    for ev in sorted(events, key=lambda e: e.timestamp):
        started = on_since[ev.genset]
        if ev.is_on and started is None:
            on_since[ev.genset] = ev.timestamp
        elif not ev.is_on and started is not None:
            runs.append(Run(ev.genset, started, ev.timestamp))
            on_since[ev.genset] = None
    for genset, started in on_since.items():
        if started is not None and open_run_end > started:
            runs.append(Run(genset, started, open_run_end))
    return runs


def runs_to_daily(runs: list[Run], start: datetime, end: datetime) -> pd.DataFrame:
    """Per day & genset: number of switch-ons and running hours.

    * A switch-on is counted on the day it happened.
    * Running time is split at midnight: a run past 12 am is accounted up to
      24:00 for that day and the remainder goes to the next day.
    """
    days = [(start + timedelta(days=i)).date() for i in range((end - start).days)]
    seconds = {(g, d): 0.0 for g in cfg.GENSETS for d in days}
    starts = {(g, d): 0 for g in cfg.GENSETS for d in days}

    for run in runs:
        if start <= run.start < end:
            starts[(run.genset, run.start.date())] += 1
        cursor, stop = max(run.start, start), min(run.end, end)   # clip to month
        while cursor < stop:
            midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min)
            piece_end = min(stop, midnight)
            seconds[(run.genset, cursor.date())] += (piece_end - cursor).total_seconds()
            cursor = piece_end

    rows = [
        {"date": pd.Timestamp(d), "genset": g,
         "switch_ons": starts[(g, d)], "hours": round(seconds[(g, d)] / 3600, 2)}
        for d in days for g in cfg.GENSETS
    ]
    return pd.DataFrame(rows)


def to_wide(daily: pd.DataFrame) -> pd.DataFrame:
    """One row per day: per-genset and combined figures (used for table & CSV)."""
    wide = daily.pivot(index="date", columns="genset", values=["switch_ons", "hours"])
    out = pd.DataFrame(index=wide.index)
    for g in cfg.GENSETS:
        out[f"{g} switch-ons"] = wide[("switch_ons", g)].astype(int)
        out[f"{g} hours"] = wide[("hours", g)]
    out["Total switch-ons"] = wide["switch_ons"].sum(axis=1).astype(int)
    out["Total hours"] = wide["hours"].sum(axis=1).round(2)
    out.index = out.index.strftime("%Y-%m-%d")
    out.index.name = "Date"
    return out.reset_index()


def summarise(daily: pd.DataFrame) -> pd.DataFrame:
    """Monthly figures for each genset plus a consolidated row."""
    per = daily.groupby("genset").agg(
        total_hours=("hours", "sum"), switch_ons=("switch_ons", "sum"))
    per.loc["Combined"] = per.sum()
    per["avg_hours_per_day"] = per["total_hours"] / daily["date"].nunique()
    return per.round(2)


def fmt_hours(hours: float) -> str:
    """12.5 -> '12h 30m'."""
    total_min = int(round(hours * 60))
    return f"{total_min // 60}h {total_min % 60:02d}m"
