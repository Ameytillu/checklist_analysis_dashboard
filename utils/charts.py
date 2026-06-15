from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


PLOTLY_TEMPLATE = "plotly_white"


def line_chart(df: pd.DataFrame, x: str, y, title: str, labels: dict | None = None):
    fig = px.line(df, x=x, y=y, markers=True, title=title, labels=labels, template=PLOTLY_TEMPLATE)
    fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=55, b=10))
    return fig


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, labels: dict | None = None):
    fig = px.bar(df, x=x, y=y, title=title, labels=labels, template=PLOTLY_TEMPLATE)
    fig.update_layout(margin=dict(l=10, r=10, t=55, b=10))
    return fig


def pickup_chart(df: pd.DataFrame):
    return line_chart(
        df,
        x="pickup_time",
        y="pickup_rooms",
        title="Pickup By Hour",
        labels={"pickup_time": "Time", "pickup_rooms": "Pickup Rooms"},
    )


def comparison_bar(metrics: list[dict], title: str):
    df = pd.DataFrame(metrics)
    fig = go.Figure()
    fig.add_bar(name="Day 1", x=df["metric"], y=df["day_1"])
    fig.add_bar(name="Day 2", x=df["metric"], y=df["day_2"])
    fig.update_layout(
        title=title,
        barmode="group",
        template=PLOTLY_TEMPLATE,
        margin=dict(l=10, r=10, t=55, b=10),
        legend_title_text="",
    )
    return fig

