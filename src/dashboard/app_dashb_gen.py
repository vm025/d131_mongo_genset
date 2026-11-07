"""Streamlit UI. Run with:  uv run streamlit run app.py"""
from datetime import datetime

import streamlit as st

from dashboard import config as cfg
from dashboard.charts import METRICS, build_chart
from  dashboard.processor import fmt_hours, summarise, to_wide
from dashboard.repository import (DemoEventRepository, EventRepository,
                               MongoEventRepository, build_mongo_client)
from dashboard.service import UsageService

st.set_page_config(page_title="Genset Usage", page_icon="⚡", layout="wide")


# ------------------------------------------------------------------ styling
def inject_css() -> None:
    st.markdown(f"""
    <style>
      .stApp {{ background-color: {cfg.BODY_BG_COLOR}; }}
      .app-title {{ color: {cfg.TITLE_COLOR}; font-weight: 800; margin-bottom: 0;
                    font-size: clamp(1.6rem, 5vw, 2.6rem); }}
      .app-sub {{ color: #5b5b4a; margin-bottom: 1rem; }}
      /* all buttons: dark background, white label */
      .stButton > button, .stDownloadButton > button,
      button[data-testid^="stBaseButton"] {{
          background-color: {cfg.BUTTON_BG}; color: {cfg.BUTTON_FG};
          border: none; border-radius: 8px; }}
      .stButton > button p, .stDownloadButton > button p {{ color: {cfg.BUTTON_FG}; }}
      .stButton > button:hover, .stDownloadButton > button:hover {{
          background-color: #1d332b; color: {cfg.BUTTON_FG}; }}
      div[data-testid="stMetric"] {{ background: {cfg.CARD_BG}; border-radius: 10px;
          padding: 0.6rem 0.9rem; border: 1px solid #d9d6a8; }}
      .block-container {{ padding-top: 2rem; }}
    </style>""", unsafe_allow_html=True)


# ------------------------------------------------- repository wiring (DIP)
@st.cache_resource(show_spinner=False)
def get_mongo_client():
    creds = st.secrets["mongo"]
    return build_mongo_client(creds["db_username"], creds["db_password"])


def get_repository() -> EventRepository:
    if cfg.USE_DB:                      # connect only when explicitly enabled
        return MongoEventRepository(get_mongo_client())
    return DemoEventRepository()


@st.cache_data(ttl=300, show_spinner="Fetching & processing data…")
def load_daily(year: int, month: int):
    return UsageService(get_repository()).daily_usage(year, month)


# ---------------------------------------------------------------------- UI
def render_summary(daily) -> None:
    summary = summarise(daily)
    st.subheader("Monthly usage")
    cols = st.columns(3)
    for col, name in zip(cols, [*cfg.GENSETS, "Combined"]):
        row = summary.loc[name]
        col.metric(f"{name}" if name != "Combined" else "Combined (all gensets)",
                   fmt_hours(row["total_hours"]),
                   f"{int(row['switch_ons'])} switch-ons · avg {row['avg_hours_per_day']:.1f} h/day",
                   delta_color="off")


def main() -> None:
    inject_css()
    st.markdown('<h1 class="app-title">⚡ Genset Usage Dashboard</h1>', unsafe_allow_html=True)
    mode = "Live MongoDB data" if cfg.USE_DB else "Demo data (USE_DB = False)"
    st.markdown(f'<div class="app-sub">Source: {mode}</div>', unsafe_allow_html=True)

    now = datetime.now()
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1], vertical_alignment="bottom")
    year = c1.selectbox("Year", range(now.year, now.year - 6, -1))
    month = c2.selectbox("Month", range(1, 13), index=now.month - 1,
                         format_func=lambda m: datetime(2000, m, 1).strftime("%B"))
    kind = c3.segmented_control("Graph", ["Bar", "Line"], default="Bar") or "Bar"
    metric = c4.selectbox("Show", list(METRICS))

    if st.button("🔄 Refresh data"):
        load_daily.clear()

    try:
        daily = load_daily(year, month)
    except Exception as exc:            # network / auth / schema problems
        st.error(f"Could not load data: {exc}")
        return

    render_summary(daily)

    st.subheader(f"{metric} per day — {datetime(year, month, 1):%B %Y}")
    st.plotly_chart(build_chart(daily, kind, metric), width="stretch")

    st.subheader("Daily details")
    wide = to_wide(daily)
    st.dataframe(wide, width="stretch", hide_index=True)
    st.download_button("⬇ Download CSV", wide.to_csv(index=False).encode("utf-8"),
                       file_name=f"genset_usage_{year}_{month:02d}.csv", mime="text/csv")


main()