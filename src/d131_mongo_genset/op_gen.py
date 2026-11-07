"""
Genset Operation
================
A small, mobile-friendly Streamlit app that records a genset's ON/OFF status
in a MongoDB Atlas collection, together with an IST timestamp.

Layers (each with a single responsibility - the "S" in SOLID):

    1. Config      - every tunable value lives in one frozen dataclass
    2. Domain      - enums + the OpsLog record (no I/O)
    3. Clock       - supplies "now" in IST (swappable, e.g. for tests)
    4. Repository  - abstract storage contract + Mongo / no-DB implementations
    5. Service     - the use case: "record an operation"
    6. UI          - theme (CSS), widgets, and the page itself

Dependencies point inwards: the UI knows the service, the service knows the
repository *interface*, and only the factory knows the concrete classes
(Dependency Inversion). New storage back-ends can be added without touching
existing code (Open/Closed).

Run with:   streamlit run app.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from string import Template
from typing import Protocol
from urllib.parse import quote_plus

import streamlit as st

# =============================================================================
# 1. CONFIGURATION  (change values here - nothing else needs editing)
# =============================================================================

# ---- Master switch ----------------------------------------------------------
# False (default): the app never touches the database; submissions are only
#                  acknowledged on screen.
# True           : records are written to MongoDB.
USE_DB: bool = True


@dataclass(frozen=True)
class Config:
    """All configurable values in one place."""

    # --- App --------------------------------------------------------------
    app_title: str = "Genset Operation"
    page_icon: str = "⚡"

    # --- Database ---------------------------------------------------------
    mongo_host: str = "cluster0.hte6gm5.mongodb.net"
    db_name: str = "genset_db"
    collection_name: str = "ops_logs"
    counters_collection_name: str = "counters"  # used for the auto "sl_no"
    server_selection_timeout_ms: int = 5000

    # --- Domain -----------------------------------------------------------
    recent_rows_to_show: int = 10

    # --- Colours (balanced, toned) ---------------------------------------
    body_bg: str = "#F1E3D8"            # light blueish-orange (soft peach with a cool undertone)
    title_color: str = "#0B1F4B"        # navy blue
    text_color: str = "#33415C"         # muted slate for secondary text
    card_bg: str = "rgba(255, 255, 255, 0.55)"
    card_border: str = "rgba(11, 31, 75, 0.12)"

    btn_idle: str = "#4A5568"           # dark slate  (unselected radio)
    btn_genset_selected: str = "#0B1F4B"  # dark navy
    btn_on_selected: str = "#1F6B4F"      # dark green
    btn_off_selected: str = "#8B2E2E"     # dark brick red
    btn_selected_ring: str = "#E08A3C"    # warm accent ring around the selection
    btn_submit: str = "#0B1F4B"
    btn_submit_hover: str = "#183A7A"
    btn_label_color: str = "#FFFFFF"      # all button labels are white

    # --- Sizing (all configurable) ---------------------------------------
    radio_font_size: str = "clamp(1.4rem, 5vw, 1.9rem)"  # label size
    radio_button_height: str = "4.5rem"                   # button height
    radio_button_gap: str = "0.9rem"                      # gap between the two buttons of a set
    section_gap_rem: float = 3.0                          # vertical space between the two radio sets
    submit_height: str = "3.8rem"
    submit_font_size: str = "1.35rem"


CFG = Config()

# Indian Standard Time = UTC+05:30 (fixed offset, so no tz database needed).
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


# =============================================================================
# 2. DOMAIN
# =============================================================================


class GensetName(str, Enum):
    """Allowed genset names."""

    ABC = "ABC"
    DEF = "DEF"


class Status(str, Enum):
    """Allowed statuses (stored in lowercase, as 'on' / 'off')."""

    ON = "on"
    OFF = "off"


@dataclass(frozen=True)
class OpsLog:
    """One row of the ops_logs collection."""

    sl_no: int | None       # None when nothing was persisted (USE_DB = False)
    genset_name: str        # "ABC" | "DEF"
    status: str             # "on" | "off"
    timestamp: str          # ISO-8601 in IST, e.g. 2026-11-07T14:05:09+05:30

    def to_document(self) -> dict:
        """Mongo document with the four agreed fields."""
        return asdict(self)


# =============================================================================
# 3. CLOCK
# =============================================================================


class Clock(Protocol):
    """Anything that can tell the current time in IST."""

    def now_ist(self) -> datetime: ...


class SystemClock:
    """Real clock."""

    def now_ist(self) -> datetime:
        return datetime.now(IST)


# =============================================================================
# 4. REPOSITORIES  (storage abstraction + implementations)
# =============================================================================


class OpsLogRepository(ABC):
    """Storage contract used by the service. Swap implementations freely (LSP)."""

    @abstractmethod
    def add(self, genset: GensetName, status: Status, timestamp: str) -> OpsLog:
        """Persist one log entry and return it."""

    @abstractmethod
    def recent(self, limit: int) -> list[dict]:
        """Most recent entries first."""


class NoDbOpsLogRepository(OpsLogRepository):
    """Used when USE_DB is False: nothing is stored and no connection is made."""

    def add(self, genset: GensetName, status: Status, timestamp: str) -> OpsLog:
        return OpsLog(None, genset.value, status.value, timestamp)

    def recent(self, limit: int) -> list[dict]:
        return []


class MongoOpsLogRepository(OpsLogRepository):
    """MongoDB implementation. Receives its collections (dependency injection)."""

    def __init__(self, logs_collection, counters_collection) -> None:
        self._logs = logs_collection
        self._counters = counters_collection
        # sl_no must never repeat.
        self._logs.create_index("sl_no", unique=True)

    def _next_sl_no(self) -> int:
        """Atomic auto-increment, safe even with several users submitting at once."""
        from pymongo import ReturnDocument

        doc = self._counters.find_one_and_update(
            {"_id": self._logs.name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc["seq"])

    def add(self, genset: GensetName, status: Status, timestamp: str) -> OpsLog:
        log = OpsLog(self._next_sl_no(), genset.value, status.value, timestamp)
        self._logs.insert_one(log.to_document())
        return log

    def recent(self, limit: int) -> list[dict]:
        cursor = self._logs.find({}, {"_id": 0}).sort("sl_no", -1).limit(limit)
        return list(cursor)


# =============================================================================
# 5. SERVICE  (the use case)
# =============================================================================


class OpsLogService:
    """Records a genset operation. Depends on abstractions only (DIP)."""

    def __init__(self, repository: OpsLogRepository, clock: Clock) -> None:
        self._repo = repository
        self._clock = clock

    def record(self, genset: GensetName, status: Status) -> OpsLog:
        # The timestamp is created on the server, not in the browser.
        stamp = self._clock.now_ist().isoformat(timespec="seconds")
        return self._repo.add(genset, status, stamp)

    def recent(self, limit: int) -> list[dict]:
        return self._repo.recent(limit)


# =============================================================================
# 5b. COMPOSITION ROOT  (the only place that knows the concrete classes)
# =============================================================================


def _read_mongo_credentials() -> tuple[str, str]:
    """Read credentials from .streamlit/secrets.toml.

    Supports either layout:
        [mongo]                      db_username = "..."
        db_username = "..."          db_password = "..."
        db_password = "..."
    """
    secrets = st.secrets["mongo"] if "mongo" in st.secrets else st.secrets
    return secrets["db_username"], secrets["db_password"]


def build_mongo_uri(cfg: Config) -> str:
    """mongodb+srv://<user>:<password>@cluster0.hte6gm5.mongodb.net/"""
    user, password = _read_mongo_credentials()
    # quote_plus keeps special characters in the password from breaking the URI
    return (
        f"mongodb+srv://{quote_plus(user)}:{quote_plus(password)}"
        f"@{cfg.mongo_host}/?retryWrites=true&w=majority"
    )


@st.cache_resource(show_spinner="Connecting to database…")
def get_mongo_repository(cfg: Config) -> OpsLogRepository:
    """Create the MongoClient once and reuse it across reruns / sessions."""
    from pymongo import MongoClient  # imported lazily: not needed when USE_DB is False

    client = MongoClient(
        build_mongo_uri(cfg),
        serverSelectionTimeoutMS=cfg.server_selection_timeout_ms,
    )
    client.admin.command("ping")  # fail fast with a clear error
    db = client[cfg.db_name]
    return MongoOpsLogRepository(db[cfg.collection_name], db[cfg.counters_collection_name])


def build_service(cfg: Config, use_db: bool) -> OpsLogService:
    """Pick the repository based on USE_DB and wire everything together."""
    repo: OpsLogRepository = get_mongo_repository(cfg) if use_db else NoDbOpsLogRepository()
    return OpsLogService(repo, SystemClock())


# =============================================================================
# 6. UI
# =============================================================================

# ---- 6a. Theme --------------------------------------------------------------

_CSS = Template(
    """
<style>
/* ---------- Page ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"] { background: $bg !important; }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 640px; padding: 2rem 1rem 3rem; }

/* ---------- Title ---------- */
.app-title {
    color: $title; text-align: center; font-weight: 800;
    font-size: clamp(2rem, 8vw, 2.9rem); line-height: 1.15; margin: 0.5rem 0 1.5rem;
}
.section-label {
    color: $text; font-weight: 700; font-size: 1.1rem; margin: 0 0 0.6rem 0.2rem;
}

/* ---------- Card around the form ---------- */
[data-testid="stForm"] {
    background: $card_bg; border: 1px solid $card_border;
    border-radius: 22px; padding: 1.6rem 1.2rem 1.4rem;
}

/* ---------- Large radio "buttons" (shared) ---------- */
/* The widget's own title is replaced by our .section-label, so hide it
   (it is also a <label> element and must not be styled as a button). */
.st-key-genset_group [data-testid="stWidgetLabel"],
.st-key-status_group [data-testid="stWidgetLabel"] { display: none !important; }

/* Two equal columns; works whatever wrapper Streamlit puts around each option */
.st-key-genset_group [role="radiogroup"],
.st-key-status_group [role="radiogroup"] {
    display: grid !important; grid-template-columns: 1fr 1fr;
    gap: $btn_gap; width: 100%;
}
/* Only the option labels INSIDE the radiogroup become buttons */
.st-key-genset_group [role="radiogroup"] label,
.st-key-status_group [role="radiogroup"] label {
    box-sizing: border-box; width: 100%; min-height: $btn_h; margin: 0;
    padding: 0.4rem 1rem; display: flex; align-items: center; justify-content: center;
    background: $btn_idle; border: 4px solid transparent; border-radius: 16px;
    cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease;
}
/* Hide the small native radio circle: any child block that does NOT hold the text */
.st-key-genset_group [role="radiogroup"] label > div:not(:has([data-testid="stMarkdownContainer"])),
.st-key-status_group [role="radiogroup"] label > div:not(:has([data-testid="stMarkdownContainer"])) {
    display: none !important;
}
/* White, large, centred option text */
.st-key-genset_group [role="radiogroup"] label [data-testid="stMarkdownContainer"],
.st-key-status_group [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
    width: 100%; display: block !important;
}
.st-key-genset_group [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
.st-key-status_group [role="radiogroup"] label [data-testid="stMarkdownContainer"] p {
    color: $label !important; font-size: $btn_fs !important; font-weight: 800;
    letter-spacing: 0.04em; text-align: center; margin: 0;
}
/* Selected states */
.st-key-genset_group [role="radiogroup"] label:has(input:checked) {
    background: $genset_sel; border-color: $ring;
}
.st-key-status_group [role="radiogroup"] > label:nth-child(1):has(input:checked),
.st-key-status_group [role="radiogroup"] > *:nth-child(1) label:has(input:checked) {
    background: $on_sel; border-color: $ring;
}
.st-key-status_group [role="radiogroup"] > label:nth-child(2):has(input:checked),
.st-key-status_group [role="radiogroup"] > *:nth-child(2) label:has(input:checked) {
    background: $off_sel; border-color: $ring;
}
.st-key-genset_group [role="radiogroup"] label:focus-within,
.st-key-status_group [role="radiogroup"] label:focus-within { outline: 3px solid $ring; outline-offset: 2px; }

/* ---------- Dark buttons with white labels ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
    background: $submit; border: none; border-radius: 16px; min-height: $submit_h;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
    background: $submit_hover;
}
.stButton > button *, [data-testid="stFormSubmitButton"] > button * {
    color: $label !important; font-size: $submit_fs; font-weight: 700;
}

/* ---------- Small screens ---------- */
@media (max-width: 480px) {
    .block-container { padding: 1.2rem 0.6rem 2rem; }
    [data-testid="stForm"] { padding: 1.2rem 0.8rem 1.1rem; }
}
</style>
"""
)


def inject_theme(cfg: Config) -> None:
    """Inject the app's CSS (colours, sizes, responsive rules)."""
    css = _CSS.substitute(
        bg=cfg.body_bg, title=cfg.title_color, text=cfg.text_color,
        card_bg=cfg.card_bg, card_border=cfg.card_border,
        btn_idle=cfg.btn_idle, genset_sel=cfg.btn_genset_selected,
        on_sel=cfg.btn_on_selected, off_sel=cfg.btn_off_selected,
        ring=cfg.btn_selected_ring, label=cfg.btn_label_color,
        btn_h=cfg.radio_button_height, btn_fs=cfg.radio_font_size,
        btn_gap=cfg.radio_button_gap,
        submit=cfg.btn_submit, submit_hover=cfg.btn_submit_hover,
        submit_h=cfg.submit_height, submit_fs=cfg.submit_font_size,
    )
    st.markdown(css, unsafe_allow_html=True)


# ---- 6b. Widgets ------------------------------------------------------------


def vertical_space(rem: float) -> None:
    """Blank vertical gap (configurable via Config.section_gap_rem)."""
    st.markdown(f'<div style="height:{rem}rem"></div>', unsafe_allow_html=True)


def radio_set(title: str, key: str, options: list[str]) -> str:
    """A titled set of large radio buttons. First option is the default."""
    st.markdown(f'<div class="section-label">{title}</div>', unsafe_allow_html=True)
    # The container's key becomes the CSS class "st-key-<key>" used by the theme.
    with st.container(key=key):
        return st.radio(
            title, options, index=0, horizontal=True, label_visibility="collapsed"
        )


def render_recent(service: OpsLogService, cfg: Config) -> None:
    """Optional table of the latest saved entries (only when USE_DB is on)."""
    with st.expander("Recent entries"):
        try:
            rows = service.recent(cfg.recent_rows_to_show)
        except Exception as exc:  # network / auth problems should not crash the page
            st.error(f"Could not load entries: {exc}")
            return
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No entries yet.")


# ---- 6c. Page ---------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title=CFG.app_title, page_icon=CFG.page_icon,
        layout="centered", initial_sidebar_state="collapsed",
    )
    inject_theme(CFG)
    st.markdown(f'<h1 class="app-title">{CFG.app_title}</h1>', unsafe_allow_html=True)

    # Build the service (connects to MongoDB only if USE_DB is True).
    try:
        service = build_service(CFG, USE_DB)
    except Exception as exc:
        st.error(f"Database connection failed: {exc}")
        st.stop()

    with st.form("genset_form", border=True):
        # Set 1: genset name
        genset = radio_set("Genset", "genset_group", [g.value for g in GensetName])

        # Configurable gap between the two sets
        vertical_space(CFG.section_gap_rem)

        # Set 2: on / off  (default = ON)
        status = radio_set("Status", "status_group", ["ON", "OFF"])

        vertical_space(1.2)
        submitted = st.form_submit_button("Submit", width="stretch")

    if submitted:
        try:
            log = service.record(GensetName(genset), Status(status.lower()))
        except Exception as exc:
            st.error(f"Could not save the entry: {exc}")
        else:
            where = "Saved" if USE_DB else "Received (database is off, nothing stored)"
            sl = f"#{log.sl_no} · " if log.sl_no is not None else ""
            st.success(
                f"{where}: {sl}Genset {log.genset_name} is {log.status.upper()} "
                f"at {log.timestamp.replace('T', ' ')} IST"
            )

    if USE_DB:
        render_recent(service, CFG)


if __name__ == "__main__":
    main()