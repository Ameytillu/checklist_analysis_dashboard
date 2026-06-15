from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --rm-navy: #172033;
            --rm-blue: #1f6feb;
            --rm-teal: #16857a;
            --rm-border: #d9e2ef;
            --rm-muted: #667085;
            --rm-soft: #f6f8fb;
            --rm-panel: #ffffff;
        }

        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #eef3f8 100%);
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--rm-border);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] a {
            font-weight: 600;
        }

        .block-container {
            max-width: 1380px;
            padding-top: 2.25rem;
            padding-bottom: 4rem;
        }

        .rm-header {
            background: linear-gradient(135deg, #152238 0%, #1f6feb 68%, #16857a 100%);
            color: #ffffff;
            border-radius: 8px;
            padding: 28px 32px;
            margin-bottom: 24px;
            box-shadow: 0 18px 45px rgba(23, 32, 51, 0.14);
        }

        .rm-eyebrow {
            margin: 0 0 8px 0;
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .rm-header h1 {
            margin: 0;
            font-size: 2.35rem;
            line-height: 1.1;
            letter-spacing: 0;
        }

        .rm-header p {
            max-width: 860px;
            margin: 12px 0 0 0;
            color: rgba(255, 255, 255, 0.84);
            font-size: 1.02rem;
        }

        .rm-section-title {
            margin: 24px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--rm-border);
            color: var(--rm-navy);
            font-size: 1.15rem;
            font-weight: 760;
        }

        .rm-panel {
            background: var(--rm-panel);
            border: 1px solid var(--rm-border);
            border-radius: 8px;
            padding: 18px 20px;
            box-shadow: 0 10px 26px rgba(23, 32, 51, 0.06);
        }

        .rm-callout {
            background: #edf5ff;
            border: 1px solid #c8ddff;
            border-left: 4px solid var(--rm-blue);
            border-radius: 8px;
            padding: 14px 16px;
            color: var(--rm-navy);
        }

        .rm-callout strong {
            display: block;
            margin-bottom: 4px;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--rm-border);
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: 0 8px 22px rgba(23, 32, 51, 0.055);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--rm-muted);
            font-size: 0.86rem;
            font-weight: 650;
        }

        div[data-testid="stMetricValue"] {
            color: var(--rm-navy);
            font-weight: 780;
        }

        .stButton > button,
        .stDownloadButton > button,
        button[kind="primary"] {
            border-radius: 7px;
            font-weight: 700;
            min-height: 42px;
        }

        .stDataFrame,
        [data-testid="stDataFrame"] {
            border: 1px solid var(--rm-border);
            border-radius: 8px;
            overflow: hidden;
            background: #ffffff;
        }

        [data-testid="stFileUploader"] section {
            border: 1px dashed #9eb7d7;
            border-radius: 8px;
            background: #f8fbff;
        }

        div[data-testid="stAlert"] {
            border-radius: 8px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 1px solid var(--rm-border);
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 7px 7px 0 0;
            font-weight: 700;
        }

        @media (max-width: 900px) {
            .rm-header {
                padding: 22px 20px;
            }

            .rm-header h1 {
                font-size: 1.85rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, eyebrow: str = "Revenue Management") -> None:
    st.markdown(
        f"""
        <div class="rm-header">
            <p class="rm-eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(label: str) -> None:
    st.markdown(f'<div class="rm-section-title">{label}</div>', unsafe_allow_html=True)


def callout(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="rm-callout">
            <strong>{title}</strong>
            <span>{body}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
