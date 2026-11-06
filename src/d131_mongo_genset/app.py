"""
Genset Operation
================
A small Streamlit app that lets a user pick the generator state (ON / OFF),
submit it, and have the server persist it in MongoDB (Atlas) together with an
IST timestamp.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import streamlit as st
from pymongo import DESCENDING, MongoClient
from pymongo.errors import PyMongoError

# =============================================================================
# 1. CONFIGURATION  (tweak these values to customise the app)
# =============================================================================
APP_TITLE = "Genset Operation"

# --- Feature switch ----------------------------------------------------------
# True  -> connect to MongoDB, save submissions, show recent activity.
# False -> never touch the database (UI-only / demo mode).
USE_DB = False

# --- Radio-button look & feel (size is configurable here) --------------------
RADIO_FONT_SIZE_PX = 34      # label text size
RADIO_PADDING_V_PX = 38      # vertical padding  -> overall button height
RADIO_PADDING_H_PX = 46      # horizontal padding -> overall button width

# --- Explicit button widths (the panel/form width is NOT changed) ------------
# Previous natural widths were roughly 150px (radio) and 100px (submit);
# these are ~double. Tune freely.
RADIO_WIDTH_PX = 800         # width of EACH radio button (ON / OFF)
SUBMIT_WIDTH_PX = 240        # width of the Submit button
APP_MAX_WIDTH_PX = 760       # panel width (unchanged)

# --- Toned colour palette ----------------------------------------------------
COLOR_PAGE_BG   = "#d5a56e"  # light brownish-orange page (body) background
COLOR_TITLE     = "#1E90FF"  # bright blue app title
COLOR_ON_PAGE   = "#FFF3E6"  # soft cream for plain text sitting on the page
COLOR_BG        = "#F4F1EC"  # warm off-white (radio cards inside the form)
COLOR_CARD      = "#FFFFFF"
COLOR_TEXT      = "#2F3E46"  # deep slate
COLOR_MUTED     = "#7A8791"
COLOR_ON        = "#52796F"  # muted green
COLOR_ON_BG     = "#E3EFEA"
COLOR_OFF       = "#B5655C"  # muted terracotta
COLOR_OFF_BG    = "#F6E6E3"
COLOR_BORDER    = "#D9D3C9"

# --- MongoDB -----------------------------------------------------------------
MONGO_HOST = "cluster0.hte6gm5.mongodb.net"
DB_NAME = "genset_db"
COLLECTION_NAME = "operation_logs"

# --- Time zone ---------------------------------------------------------------
IST = ZoneInfo("Asia/Kolkata")

# =============================================================================
# 2. PAGE SETUP & STYLING
# =============================================================================
st.set_page_config(page_title=APP_TITLE, page_icon="⚡", layout="centered")


def inject_css() -> None:
    """Inject custom CSS: palette, big radio 'cards', responsive tweaks."""
    st.markdown(
        f"""
        <style>
        /* ---------- Page ---------- */
        .stApp {{ background: {COLOR_PAGE_BG}; color: {COLOR_TEXT}; }}
        .block-container {{ max-width: {APP_MAX_WIDTH_PX}px !important; padding-top: 2.5rem; }}
        header[data-testid="stHeader"] {{ background: transparent; }}

        /* ---------- Title ---------- */
        .app-title {{
            text-align: center; font-weight: 700; letter-spacing: .5px;
            font-size: clamp(1.8rem, 5vw, 2.6rem); color: {COLOR_TITLE};
            margin-bottom: .2rem;
        }}
        .app-subtitle {{
            text-align: center; color: {COLOR_ON_PAGE};
            margin-bottom: 1.8rem; font-size: 1rem;
        }}
        /* headings / captions that sit directly on the orange page */
        .stApp h4, [data-testid="stCaptionContainer"] {{ color: {COLOR_ON_PAGE}; }}

        /* ---------- Form card ---------- */
        [data-testid="stForm"] {{
            background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER};
            border-radius: 20px; padding: 1.8rem;
            box-shadow: 0 6px 24px rgba(47,62,70,.07);
        }}

        /* ---------- Large radio buttons ---------- */
        div[data-testid="stRadio"] div[role="radiogroup"] {{
            display: flex; flex-direction: row; flex-wrap: wrap;
            justify-content: center; gap: 1.2rem; width: 100%;
        }}
        div[data-testid="stRadio"] label[data-baseweb="radio"] {{
            flex: 0 0 auto; width: {RADIO_WIDTH_PX}px; max-width: 100%;
            box-sizing: border-box; justify-content: center; cursor: pointer;
            padding: {RADIO_PADDING_V_PX}px {RADIO_PADDING_H_PX}px;
            border: 2px solid {COLOR_BORDER}; border-radius: 16px;
            background: {COLOR_BG}; transition: all .2s ease;
        }}
        /* hide the tiny native circle; the whole card acts as the button */
        div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{
            display: none;
        }}
        div[data-testid="stRadio"] label[data-baseweb="radio"] p {{
            font-size: {RADIO_FONT_SIZE_PX}px; font-weight: 700;
            letter-spacing: 2px; color: {COLOR_MUTED}; margin: 0;
        }}
        div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(47,62,70,.12);
        }}
        /* selected states: 1st card = ON (green), 2nd card = OFF (red) */
        div[data-testid="stRadio"] label:nth-child(1):has(input:checked) {{
            background: {COLOR_ON_BG}; border-color: {COLOR_ON};
        }}
        div[data-testid="stRadio"] label:nth-child(1):has(input:checked) p {{
            color: {COLOR_ON};
        }}
        div[data-testid="stRadio"] label:nth-child(2):has(input:checked) {{
            background: {COLOR_OFF_BG}; border-color: {COLOR_OFF};
        }}
        div[data-testid="stRadio"] label:nth-child(2):has(input:checked) p {{
            color: {COLOR_OFF};
        }}

        /* ---------- Submit button ---------- */
        div[data-testid="stFormSubmitButton"] {{
            display: flex; justify-content: center; width: 100%;
        }}
        div[data-testid="stFormSubmitButton"] button {{
            width: {SUBMIT_WIDTH_PX}px; max-width: 100%; padding: .9rem 0; font-size: 1.15rem; font-weight: 600;
            border-radius: 12px; border: none;
            background: {COLOR_TEXT}; color: #fff; transition: opacity .2s;
        }}
        div[data-testid="stFormSubmitButton"] button:hover {{
            opacity: .88; color: #fff;
        }}

        /* ---------- Responsive (phones / small tablets) ---------- */
        @media (max-width: 640px) {{
            .block-container {{ padding: 1.2rem .8rem; }}
            [data-testid="stForm"] {{ padding: 1rem; }}
            div[data-testid="stRadio"] div[role="radiogroup"] {{ flex-direction: column; gap: .8rem; }}
            div[data-testid="stRadio"] label[data-baseweb="radio"] {{
                width: 100%; padding: {int(RADIO_PADDING_V_PX * 0.7)}px 16px;
            }}
            div[data-testid="stRadio"] label[data-baseweb="radio"] p {{
                font-size: {int(RADIO_FONT_SIZE_PX * 0.8)}px;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# 3. DATABASE LAYER
# =============================================================================
@st.cache_resource(show_spinner="Connecting to database…")
def get_collection():
    """
    Create (once per server process) and return the MongoDB collection.

    Credentials are read from .streamlit/secrets.toml and URL-encoded so that
    special characters in the password do not break the connection string.
    """
    user = quote_plus(st.secrets["db_username"])
    pwd = quote_plus(st.secrets["db_password"])
    uri = f"mongodb+srv://{user}:{pwd}@{MONGO_HOST}/?retryWrites=true&w=majority"

    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")  # fail fast if credentials / network are wrong
    return client[DB_NAME][COLLECTION_NAME]


def save_status(status: str) -> datetime:
    """
    Persist the genset status with a server-generated IST timestamp.

    Note: MongoDB stores BSON dates in UTC internally, so an IST-aware datetime
    would be silently converted. To keep the IST value visible and exact we
    store BOTH:
      * timestamp_ist  -> ISO-8601 string with +05:30 offset (human readable)
      * timestamp_utc  -> real BSON date (for sorting / range queries)
    """
    now_ist = datetime.now(IST)  # timestamp is taken on the server side
    get_collection().insert_one(
        {
            "status": status,                         # "ON" | "OFF"
            "timestamp_ist": now_ist.isoformat(timespec="seconds"),
            "timestamp_utc": now_ist.astimezone(ZoneInfo("UTC")),
        }
    )
    return now_ist


def fetch_recent(limit: int = 5) -> list[dict]:
    """Return the latest `limit` records, newest first."""
    cursor = (
        get_collection()
        .find({}, {"_id": 0, "status": 1, "timestamp_ist": 1})
        .sort("timestamp_utc", DESCENDING)
        .limit(limit)
    )
    return list(cursor)


# =============================================================================
# 4. UI
# =============================================================================
def render_header() -> None:
    st.markdown(f'<div class="app-title">⚡ {APP_TITLE}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Select the generator state and submit</div>',
        unsafe_allow_html=True,
    )


def render_form() -> None:
    """Radio selection (default ON) + submit button inside a form."""
    with st.form("genset_form", clear_on_submit=False):
        status = st.radio(
            "Genset status",
            options=["ON", "OFF"],
            index=0,                      # default = ON
            horizontal=True,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Submit")

    if submitted:
        if not USE_DB:
            st.info(f"Database is disabled (USE_DB = False). Selected: **{status}** — nothing was saved.")
            return
        try:
            ts = save_status(status)
            st.success(f"Genset **{status}** saved at {ts:%d-%b-%Y %I:%M:%S %p} IST")
        except PyMongoError as exc:
            st.error(f"Could not save to database: {exc}")


def render_history() -> None:
    """Show the last few submissions (skipped when the DB is disabled)."""
    if not USE_DB:
        return
    st.markdown("#### Recent activity")
    try:
        rows = fetch_recent()
        if rows:
            st.dataframe(
                rows,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "status": "Status",
                    "timestamp_ist": "Timestamp (IST)",
                },
            )
        else:
            st.caption("No records yet.")
    except PyMongoError as exc:
        st.warning(f"Could not load history: {exc}")


def main() -> None:
    inject_css()
    render_header()
    if USE_DB:  # only connect when the DB is enabled
        try:
            get_collection()  # connect early so config errors show up clearly
        except (KeyError, PyMongoError) as exc:
            st.error(f"Database connection failed: {exc}")
            st.stop()
    render_form()
    st.write("")
    render_history()


if __name__ == "__main__":
    main()