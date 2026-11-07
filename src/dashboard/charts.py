"""Plotly figure builders (stacked bar / stacked line)."""
import pandas as pd
import plotly.graph_objects as go

from dashboard import config as cfg

AUTO = "Running time (auto unit)"
AUTO_SWITCH_HOURS = 2    # peak stacked daily total below this -> show minutes

METRICS = {AUTO: (None, None), "Running hours": ("hours", "Hours"), "Running minutes": ("minutes", "Minutes"), "Switch-ons": ("switch_ons", "Times switched on")}


def resolve_metric(daily: pd.DataFrame, metric_label: str) -> tuple[str, str]:
    """(column, axis title). 'Auto' picks minutes for light months, hours otherwise."""
    if metric_label == AUTO:
        peak_hours = daily.groupby("date")["hours"].sum().max()
        return ("minutes", "Minutes") if peak_hours < AUTO_SWITCH_HOURS else ("hours", "Hours")
    return METRICS[metric_label]


def build_chart(daily: pd.DataFrame, kind: str, metric_label: str) -> go.Figure:
    if "minutes" not in daily.columns:          # tolerate an older processor.py
        daily = daily.assign(minutes=daily["hours"] * 60)
    column, y_title = resolve_metric(daily, metric_label)
    fig = go.Figure()
    for genset in cfg.GENSETS:
        d = daily[daily["genset"] == genset]
        colour = cfg.GENSET_COLORS[genset]
        if kind == "Bar":
            fig.add_bar(x=d["date"], y=d[column], name=genset, marker_color=colour)
        else:
            fig.add_scatter(x=d["date"], y=d[column], name=genset, mode="lines+markers",
                            stackgroup="usage", line=dict(color=colour, width=2))
    fig.update_layout(
        barmode="stack",
        xaxis_title="Day of month", yaxis_title=y_title,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=cfg.CARD_BG,
        margin=dict(l=10, r=10, t=30, b=10), height=420,
        legend=dict(orientation="h", y=1.12, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(tickformat="%d", dtick=86400000 * 2)
    fig.update_yaxes(rangemode="tozero")   # axis range then adapts to the data
    return fig
