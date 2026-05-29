# Fordsworth app.py
# Full Streamlit terminal with terminal header, market strip, filters, stock tear sheet, valuation lab, agents, reports, portfolio, risk, scheduler.

import streamlit as st
import pandas as pd
import yfinance as yf
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import html
from html.parser import HTMLParser
import hashlib
from pathlib import Path
import re
import json
import os
from urllib.parse import quote

# Optional export libraries.
# Word export requires: pip install python-docx
# PDF export uses reportlab if installed, otherwise uses built-in fallback PDF export
try:
    from docx import Document
except Exception:
    Document = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
except Exception:
    A4 = None
    getSampleStyleSheet = None
    SimpleDocTemplate = None
    Paragraph = None
    Spacer = None
    inch = None


from services.config_service import load_settings
from services.portfolio_service import portfolio_summary, get_position_by_ticker
from services.news_service import fetch_company_news
from services.market_data_service import (
    fetch_stock_snapshot,
    format_large_number,
    format_number_or_na,
    format_percent_or_na,
)
from services.report_service import (
    list_reports,
    read_report,
    search_reports_for_text,
    save_markdown_report,
)
from services.valuation_service import (
    fetch_valuation_inputs,
    suggest_assumptions,
    run_three_case_dcf,
    build_valuation_markdown_report,
    format_currency_value,
)

from agents.morning_analyst import run_morning_analyst
from agents.thesis_tracker import run_thesis_tracker
from agents.event_calendar import run_event_calendar
from agents.market_curator import run_market_curator
from agents.deep_digger import run_deep_digger

from scheduler.scheduler_engine import (
    get_or_start_scheduler,
    stop_scheduler,
    get_scheduler_jobs,
)


st.set_page_config(
    page_title="Fordsworth",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

settings = load_settings()
summary = portfolio_summary()
positions = summary["positions"]

REPORT_CONFIG = {
    "Morning Analyst": {"report_type": "morning_briefs", "description": "Daily thesis-aware morning briefing", "emoji": "☀️"},
    "Market Curator": {"report_type": "market_curator", "description": "End-of-day relevance filter", "emoji": "📰"},
    "Thesis Tracker": {"report_type": "thesis_reviews", "description": "Weekly thesis health review", "emoji": "🧭"},
    "Event Calendar": {"report_type": "weekly_calendars", "description": "Weekly catalyst and macro calendar", "emoji": "📅"},
    "Deep Digger": {"report_type": "deep_research", "description": "On-demand investment memo engine", "emoji": "🔎"},
}

MARKET_TICKERS = [
    {"label": "S&P 500", "symbol": "^GSPC"},
    {"label": "Nasdaq", "symbol": "^IXIC"},
    {"label": "Dow", "symbol": "^DJI"},
    {"label": "FTSE 100", "symbol": "^FTSE"},
    {"label": "US 10Y", "symbol": "^TNX"},
    {"label": "Crude Oil", "symbol": "CL=F"},
    {"label": "Gold", "symbol": "GC=F"},
    {"label": "USD/ZAR", "symbol": "USDZAR=X"},
    {"label": "Bitcoin", "symbol": "BTC-USD"},
]


def inject_custom_css():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
        .block-container { padding-top: 0rem; padding-left: 0rem; padding-right: 0rem; max-width: 100%; }
        .content-container { padding-left: 2.2rem; padding-right: 2.2rem; padding-bottom: 2rem; }
        .terminal-topbar { background: #000; color: #fff; padding: .35rem .75rem; font-size: .78rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; }
        .terminal-topbar-left span, .terminal-topbar-right span { margin-right: 1rem; color: #fff; }
        .terminal-brand-bar { background: #000; color: #fff; padding: .85rem .75rem; display: flex; justify-content: space-between; align-items: center; }
        .terminal-brand { font-size: 2.25rem; font-weight: 850; letter-spacing: -.055em; }
        .terminal-actions span { margin-left: 1rem; font-size: .9rem; }
        .terminal-nav { background: #1f1f1f; color: #fff; padding: .55rem .75rem; display: flex; gap: 1.4rem; align-items: center; font-size: .9rem; border-bottom: 1px solid #333; }
        .terminal-nav span { color: #fff; }
        .terminal-nav .active-nav { background: #000; padding: .25rem .45rem; border-bottom: 2px solid #fff; }
        .market-strip { display: flex; gap: .6rem; overflow-x: auto; padding: .65rem .75rem; border-bottom: 1px solid #d1d5db; background: #fff; margin-bottom: 1.1rem; }
        .market-pill { background: #111827; color: #fff; border-radius: 8px; padding: .45rem .65rem; white-space: nowrap; font-size: .86rem; font-weight: 650; }
        .market-up { color: #22c55e; }
        .market-down { color: #ef4444; }
        .market-flat { color: #d1d5db; }
        .terminal-section-title { font-size: 2.4rem; font-weight: 850; letter-spacing: -.045em; margin-top: .6rem; margin-bottom: .5rem; }
        .terminal-subnav { display: flex; gap: 1.4rem; padding-bottom: .8rem; border-bottom: 1px solid #e5e7eb; margin-bottom: 1.2rem; font-size: .95rem; }
        .agent-card { padding: 1rem; border-radius: 16px; border: 1px solid #e5e7eb; background: #fff; box-shadow: 0 1px 5px rgba(0,0,0,.05); min-height: 145px; }
        .agent-title { font-size: 1rem; font-weight: 700; margin-bottom: .25rem; }
        .agent-description { font-size: .86rem; color: #4b5563; margin-bottom: .5rem; }
        .status-pill { display: inline-block; padding: .15rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 600; background: #dcfce7; color: #166534; }
        .small-muted { color: #6b7280; font-size: .85rem; }
        .action-panel { padding: 1.1rem; border-radius: 18px; border: 1px solid #e5e7eb; background: #fff; box-shadow: 0 1px 5px rgba(0,0,0,.05); min-height: 245px; }
        .action-panel h4 { margin-top: 0; margin-bottom: .5rem; }
        .action-panel-note { color: #6b7280; font-size: .86rem; margin-bottom: 1rem; }
        .tear-sheet-card { padding: 1.2rem; border-radius: 18px; border: 1px solid #d1d5db; background: #f9fafb; box-shadow: 0 1px 5px rgba(0,0,0,.04); margin-bottom: .5rem; }
        .tear-sheet-title { font-size: 1.05rem; font-weight: 700; margin-bottom: .25rem; }
        .tear-sheet-text { color: #4b5563; font-size: .9rem; margin-bottom: 0; }

        .market-module-card {
            padding: 1rem;
            border-radius: 16px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            box-shadow: 0 1px 5px rgba(0,0,0,0.04);
            min-height: 120px;
            margin-bottom: 0.7rem;
        }

        .market-module-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: #111827;
            margin-bottom: 0.25rem;
        }

        .market-module-text {
            font-size: 0.9rem;
            color: #4b5563;
            margin-bottom: 0;
        }

        .instrument-detail-card {
            padding: 1rem;
            border-radius: 16px;
            border: 1px solid #d1d5db;
            background: #f9fafb;
            margin-top: 1rem;
            margin-bottom: 1rem;
        }

        .instrument-detail-title {
            font-size: 1.25rem;
            font-weight: 850;
            color: #111827;
            margin-bottom: 0.2rem;
        }

        .instrument-detail-subtitle {
            font-size: 0.9rem;
            color: #4b5563;
            margin-bottom: 0;
        }
        /* Working market ticker buttons */
        .stButton > button {
            border-radius: 10px;
            border: 1px solid #1f2937;
            background: #111827;
            color: #ffffff;
            font-weight: 750;
            min-height: 48px;
            width: 100%;
            white-space: normal;
        }

        .stButton > button:hover {
            border-color: #ffffff;
            background: #000000;
            color: #ffffff;
        }


        /* Fordsworth terminal shell */
        .content-container {
            background: #0b0f14;
            color: #e5e7eb;
            padding-top: 0.35rem;
        }

        .terminal-page-title {
            color: #f9fafb;
            font-size: 1.6rem;
            font-weight: 850;
            letter-spacing: -0.02em;
            margin-bottom: 0.2rem;
        }

        .terminal-page-subtitle {
            color: #9ca3af;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }
.market-module-card,
        .tear-sheet-card,
        .action-panel,
        .agent-card,
        .instrument-detail-card,
        .overview-card {
            background: #111827 !important;
            border: 1px solid #1f2937 !important;
            color: #e5e7eb !important;
        }

        .market-module-title,
        .tear-sheet-title,
        .instrument-detail-title,
        .agent-title {
            color: #f9fafb !important;
        }

        .market-module-text,
        .tear-sheet-text,
        .instrument-detail-subtitle,
        .agent-description,
        .small-muted,
        .action-panel-note {
            color: #9ca3af !important;
        }

        div[data-testid="stMetric"] {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 0.75rem;
        }

        div[data-testid="stMetric"] label {
            color: #9ca3af !important;
        }

        div[data-testid="stMetric"] div {
            color: #f9fafb !important;
        }


        /* Fordsworth color layer */
        .home-summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.1rem;
        }

        .home-summary-card {
            border-radius: 16px;
            padding: 1rem;
            border: 1px solid #1f2937;
            background: linear-gradient(135deg, #111827 0%, #172033 100%);
            box-shadow: 0 1px 8px rgba(0,0,0,0.25);
        }

        .home-summary-card.blue {
            border-left: 4px solid #3b82f6;
        }

        .home-summary-card.green {
            border-left: 4px solid #22c55e;
        }

        .home-summary-card.amber {
            border-left: 4px solid #f59e0b;
        }

        .home-summary-card.purple {
            border-left: 4px solid #a855f7;
        }

        .home-summary-label {
            color: #9ca3af;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.25rem;
        }

        .home-summary-value {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .home-summary-note {
            color: #cbd5e1;
            font-size: 0.84rem;
        }

        .daily-update-box {
            border-radius: 14px;
            padding: 0.95rem;
            border: 1px solid #1f2937;
            background: #0f172a;
            margin-top: 0.8rem;
            margin-bottom: 0.8rem;
        }

        .daily-update-title {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .daily-update-text {
            color: #cbd5e1;
            font-size: 0.9rem;
            margin-bottom: 0;
        }

        .positive-text {
            color: #22c55e;
            font-weight: 800;
        }

        .negative-text {
            color: #ef4444;
            font-weight: 800;
        }

        .neutral-text {
            color: #d1d5db;
            font-weight: 800;
        }

        .function-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 0.8rem;
            margin-bottom: 1rem;
        }

        .function-chip {
            background: #111827;
            border: 1px solid #1f2937;
            color: #e5e7eb;
            border-radius: 999px;
            padding: 0.35rem 0.7rem;
            font-size: 0.82rem;
            font-weight: 750;
        }


        .tear-section-card {
            padding: 1rem;
            border-radius: 16px;
            border: 1px solid #1f2937;
            background: #111827;
            margin-bottom: 1rem;
            color: #e5e7eb;
        }

        .tear-section-title {
            font-size: 1.05rem;
            font-weight: 850;
            color: #f9fafb;
            margin-bottom: 0.25rem;
        }

        .tear-section-note {
            font-size: 0.88rem;
            color: #9ca3af;
            margin-bottom: 0.2rem;
        }

        .tear-action-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 0.65rem;
            margin-top: 0.7rem;
            margin-bottom: 0.7rem;
        }

        .tear-quality-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.25rem 0.6rem;
            margin: 0.1rem 0.2rem 0.1rem 0;
            background: #0f172a;
            border: 1px solid #1f2937;
            color: #e5e7eb;
            font-size: 0.8rem;
            font-weight: 700;
        }


        /* =====================================================
           FORDSWORTH VISUAL POLISH
           ===================================================== */

        .block-container {
            padding-top: 0rem !important;
            padding-left: 0rem !important;
            padding-right: 0rem !important;
            max-width: 100% !important;
        }

        .content-container {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-top: 0.75rem !important;
            padding-bottom: 2rem !important;
        }

        .terminal-brand-bar {
            min-height: 64px;
            border-bottom: 1px solid #111827;
        }

        .terminal-brand {
            font-size: 2rem !important;
            font-weight: 900 !important;
            letter-spacing: -0.04em !important;
        }

        .working-ribbon {
            background: #111827 !important;
            padding: 0.45rem 0.75rem !important;
            border-bottom: 1px solid #1f2937 !important;
        }

        .working-ribbon [role="radiogroup"] {
            gap: 0.4rem !important;
            flex-wrap: wrap !important;
        }

        .working-ribbon [role="radiogroup"] label {
            background: #111827 !important;
            border: 1px solid transparent !important;
            border-radius: 999px !important;
            padding: 0.35rem 0.75rem !important;
            min-height: 34px !important;
        }

        .working-ribbon [role="radiogroup"] label:hover {
            background: #020617 !important;
            border: 1px solid #334155 !important;
        }

        .working-ribbon [role="radiogroup"] label:has(input:checked) {
            background: #2563eb !important;
            border: 1px solid #3b82f6 !important;
        }

        .working-ribbon [role="radiogroup"] label span {
            font-size: 0.84rem !important;
            font-weight: 750 !important;
        }

        .market-strip-wrapper {
            margin-bottom: 0rem !important;
            padding-top: 0.55rem !important;
            padding-bottom: 0.55rem !important;
            border-bottom: 1px solid #111827 !important;
        }

        .market-strip-title {
            font-size: 0.72rem !important;
            color: #9ca3af !important;
            margin-bottom: 0.35rem !important;
        }

        .market-pill {
            min-height: 56px !important;
            border-radius: 12px !important;
            background: #0f172a !important;
            border: 1px solid #1f2937 !important;
        }

        .terminal-page-title {
            font-size: 1.55rem !important;
            margin-top: 0.2rem !important;
            margin-bottom: 0.15rem !important;
            color: #f9fafb !important;
        }

        .terminal-page-subtitle {
            margin-bottom: 1rem !important;
            color: #9ca3af !important;
            font-size: 0.88rem !important;
        }

        h1, h2, h3 {
            letter-spacing: -0.02em;
        }

        h3 {
            margin-top: 0.6rem !important;
            margin-bottom: 0.55rem !important;
        }

        hr {
            margin-top: 1rem !important;
            margin-bottom: 1rem !important;
            border-color: #1f2937 !important;
        }

        div[data-testid="stMetric"] {
            background: #0f172a !important;
            border: 1px solid #1f2937 !important;
            border-radius: 14px !important;
            padding: 0.85rem !important;
            box-shadow: 0 1px 6px rgba(0,0,0,0.18) !important;
        }

        div[data-testid="stMetric"] label {
            color: #9ca3af !important;
            font-size: 0.78rem !important;
            font-weight: 700 !important;
        }

        div[data-testid="stMetric"] div {
            color: #f9fafb !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem !important;
            border-bottom: 1px solid #1f2937 !important;
        }

        .stTabs [data-baseweb="tab"] {
            background: #111827 !important;
            border-radius: 10px 10px 0 0 !important;
            padding: 0.45rem 0.8rem !important;
            color: #cbd5e1 !important;
            border: 1px solid #1f2937 !important;
            border-bottom: none !important;
        }

        .stTabs [aria-selected="true"] {
            background: #2563eb !important;
            color: #ffffff !important;
            border-color: #3b82f6 !important;
        }

        .stDataFrame {
            border-radius: 14px !important;
            overflow: hidden !important;
            border: 1px solid #1f2937 !important;
        }

        .stButton > button {
            border-radius: 12px !important;
            border: 1px solid #334155 !important;
            background: #111827 !important;
            color: #f9fafb !important;
            font-weight: 750 !important;
            min-height: 42px !important;
            transition: all 0.15s ease-in-out !important;
        }

        .stButton > button:hover {
            background: #2563eb !important;
            border-color: #3b82f6 !important;
            color: #ffffff !important;
            transform: translateY(-1px);
        }

        .market-module-card,
        .tear-section-card,
        .tear-sheet-card,
        .action-panel,
        .agent-card,
        .instrument-detail-card,
        .overview-card {
            background: #0f172a !important;
            border: 1px solid #1f2937 !important;
            border-radius: 16px !important;
            box-shadow: 0 1px 8px rgba(0,0,0,0.20) !important;
        }

        .market-module-title,
        .tear-section-title,
        .tear-sheet-title,
        .instrument-detail-title,
        .agent-title {
            color: #f9fafb !important;
        }

        .market-module-text,
        .tear-section-note,
        .tear-sheet-text,
        .instrument-detail-subtitle,
        .agent-description,
        .small-muted,
        .action-panel-note {
            color: #9ca3af !important;
        }

        .element-container:has(.stAlert) {
            margin-top: 0.4rem !important;
            margin-bottom: 0.4rem !important;
        }

        div[data-testid="stExpander"] {
            border: 1px solid #1f2937 !important;
            border-radius: 12px !important;
            background: #0f172a !important;
        }

        input, textarea {
            border-radius: 10px !important;
        }

        .compact-note {
            color: #9ca3af;
            font-size: 0.84rem;
            margin-top: -0.25rem;
            margin-bottom: 0.75rem;
        }

        .executive-summary-card {
            background: linear-gradient(135deg, #0f172a 0%, #111827 55%, #172554 100%);
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1.05rem 1.15rem;
            margin-bottom: 1rem;
        }

        .executive-summary-title {
            color: #f9fafb;
            font-size: 1.15rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .executive-summary-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            margin-bottom: 0;
        }


        /* =====================================================
           FORDSWORTH HOME PAGE UPGRADE
           ===================================================== */

        .home-hero-v2 {
            background: linear-gradient(135deg, #020617 0%, #0f172a 45%, #1e3a8a 100%);
            border: 1px solid #1f2937;
            border-radius: 22px;
            padding: 1.35rem 1.45rem;
            margin-bottom: 1.1rem;
            box-shadow: 0 2px 16px rgba(0,0,0,0.28);
        }

        .home-hero-eyebrow {
            color: #38bdf8;
            font-size: 0.78rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }

        .home-hero-title-v2 {
            color: #f9fafb;
            font-size: 1.75rem;
            font-weight: 950;
            letter-spacing: -0.04em;
            margin-bottom: 0.35rem;
        }

        .home-hero-text-v2 {
            color: #cbd5e1;
            font-size: 0.98rem;
            line-height: 1.45;
            max-width: 980px;
            margin-bottom: 0.65rem;
        }

        .home-hero-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.85rem;
        }

        .home-hero-pill {
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid #334155;
            border-radius: 999px;
            padding: 0.32rem 0.68rem;
            color: #e5e7eb;
            font-size: 0.78rem;
            font-weight: 750;
        }

        .home-kpi-grid-v2 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 0.8rem;
            margin-bottom: 1.1rem;
        }

        .home-kpi-card-v2 {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1rem;
            box-shadow: 0 1px 8px rgba(0,0,0,0.2);
        }

        .home-kpi-card-v2.blue { border-left: 4px solid #3b82f6; }
        .home-kpi-card-v2.green { border-left: 4px solid #22c55e; }
        .home-kpi-card-v2.red { border-left: 4px solid #ef4444; }
        .home-kpi-card-v2.purple { border-left: 4px solid #a855f7; }

        .home-kpi-label-v2 {
            color: #9ca3af;
            font-size: 0.75rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }

        .home-kpi-value-v2 {
            color: #f9fafb;
            font-size: 1.55rem;
            font-weight: 950;
            margin-bottom: 0.15rem;
        }

        .home-kpi-note-v2 {
            color: #cbd5e1;
            font-size: 0.82rem;
        }

        .home-workflow-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.95rem;
            margin-bottom: 0.75rem;
        }

        .home-workflow-title {
            color: #f9fafb;
            font-weight: 900;
            font-size: 0.98rem;
            margin-bottom: 0.25rem;
        }

        .home-workflow-text {
            color: #9ca3af;
            font-size: 0.84rem;
            margin-bottom: 0;
        }

        .home-section-panel {
            background: #0b1220;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        .home-section-title {
            color: #f9fafb;
            font-size: 1.05rem;
            font-weight: 900;
            margin-bottom: 0.4rem;
        }

        .home-section-subtitle {
            color: #9ca3af;
            font-size: 0.86rem;
            margin-bottom: 0.75rem;
        }


        /* =====================================================
           HOME SCREENER STYLE
           ===================================================== */

        .screener-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 52%, #1d4ed8 100%);
            border: 1px solid #1f2937;
            border-radius: 22px;
            padding: 1.25rem 1.4rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 16px rgba(0,0,0,0.28);
        }

        .screener-hero-title {
            color: #f9fafb;
            font-size: 1.65rem;
            font-weight: 950;
            letter-spacing: -0.04em;
            margin-bottom: 0.25rem;
        }

        .screener-hero-text {
            color: #cbd5e1;
            font-size: 0.95rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .screener-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.75rem;
        }

        .screener-pill {
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid #334155;
            border-radius: 999px;
            padding: 0.3rem 0.65rem;
            color: #e5e7eb;
            font-size: 0.78rem;
            font-weight: 750;
        }

        .screener-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .screener-kpi {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            box-shadow: 0 1px 8px rgba(0,0,0,0.2);
        }

        .screener-kpi.blue { border-left: 4px solid #3b82f6; }
        .screener-kpi.green { border-left: 4px solid #22c55e; }
        .screener-kpi.red { border-left: 4px solid #ef4444; }
        .screener-kpi.amber { border-left: 4px solid #f59e0b; }

        .screener-kpi-label {
            color: #9ca3af;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }

        .screener-kpi-value {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            margin-bottom: 0.1rem;
        }

        .screener-kpi-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }

        .screener-panel {
            background: #0b1220;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        .screener-panel-title {
            color: #f9fafb;
            font-size: 1.05rem;
            font-weight: 900;
            margin-bottom: 0.35rem;
        }

        .screener-panel-text {
            color: #9ca3af;
            font-size: 0.86rem;
            margin-bottom: 0.75rem;
        }


        /* =====================================================
           HOME BUSINESS NEWS LAYOUT
           ===================================================== */

        .news-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 52%, #1e3a8a 100%);
            border: 1px solid #1f2937;
            border-radius: 22px;
            padding: 1.25rem 1.4rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 16px rgba(0,0,0,0.28);
        }

        .news-hero-title {
            color: #f9fafb;
            font-size: 1.65rem;
            font-weight: 950;
            letter-spacing: -0.04em;
            margin-bottom: 0.25rem;
        }

        .news-hero-text {
            color: #cbd5e1;
            font-size: 0.95rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .news-section-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 8px rgba(0,0,0,0.20);
        }

        .news-section-title {
            color: #f9fafb;
            font-size: 1.06rem;
            font-weight: 900;
            margin-bottom: 0.2rem;
        }

        .news-section-subtitle {
            color: #9ca3af;
            font-size: 0.84rem;
            margin-bottom: 0.75rem;
        }

        .news-item {
            border-bottom: 1px solid #1f2937;
            padding: 0.65rem 0;
        }

        .news-item:last-child {
            border-bottom: none;
        }

        .news-title {
            color: #e5e7eb;
            font-weight: 800;
            font-size: 0.92rem;
            margin-bottom: 0.18rem;
        }

        .news-meta {
            color: #94a3b8;
            font-size: 0.76rem;
            margin-bottom: 0.22rem;
        }

        .news-summary {
            color: #cbd5e1;
            font-size: 0.82rem;
            line-height: 1.38;
        }

        .news-tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.75rem;
        }

        .news-tag {
            background: #111827;
            border: 1px solid #334155;
            color: #e5e7eb;
            border-radius: 999px;
            padding: 0.25rem 0.58rem;
            font-size: 0.76rem;
            font-weight: 750;
        }

        .news-grid-2 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 1rem;
        }

        .news-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .news-kpi {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
        }

        .news-kpi.blue { border-left: 4px solid #3b82f6; }
        .news-kpi.green { border-left: 4px solid #22c55e; }
        .news-kpi.amber { border-left: 4px solid #f59e0b; }
        .news-kpi.purple { border-left: 4px solid #a855f7; }

        .news-kpi-label {
            color: #9ca3af;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .news-kpi-value {
            color: #f9fafb;
            font-size: 1.3rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .news-kpi-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }


        /* =====================================================
           HOME CONTINUOUS BUSINESS NEWS FEED
           ===================================================== */

        .home-news-terminal {
            background: #020617;
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.05rem 1.15rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .home-news-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .home-news-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            margin-bottom: 0;
            max-width: 980px;
        }

        .live-news-grid {
            display: grid;
            grid-template-columns: 1.45fr 1fr;
            gap: 1rem;
            align-items: start;
        }

        .live-news-section {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.95rem;
            margin-bottom: 1rem;
        }

        .live-news-section-title {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 0.25rem;
        }

        .live-news-section-subtitle {
            color: #94a3b8;
            font-size: 0.8rem;
            margin-bottom: 0.65rem;
        }

        .live-news-item {
            padding: 0.7rem 0;
            border-bottom: 1px solid #1f2937;
        }

        .live-news-item:last-child {
            border-bottom: none;
        }

        .live-news-headline {
            color: #e5e7eb;
            font-weight: 850;
            font-size: 0.92rem;
            line-height: 1.32;
            margin-bottom: 0.22rem;
        }

        .live-news-meta {
            color: #64748b;
            font-size: 0.74rem;
            margin-bottom: 0.25rem;
        }

        .live-news-summary {
            color: #cbd5e1;
            font-size: 0.82rem;
            line-height: 1.38;
        }

        .breaking-strip {
            background: #7f1d1d;
            border: 1px solid #991b1b;
            color: #fee2e2;
            border-radius: 14px;
            padding: 0.65rem 0.85rem;
            margin-bottom: 1rem;
            font-weight: 800;
            font-size: 0.88rem;
        }
@media (max-width: 950px) {
            .live-news-grid {
                grid-template-columns: 1fr;
            }
        }


        .selected-news-panel {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 10px rgba(0,0,0,0.25);
        }

        .selected-news-label {
            color: #38bdf8;
            font-size: 0.75rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.3rem;
        }

        .selected-news-title {
            color: #f9fafb;
            font-size: 1.15rem;
            font-weight: 950;
            line-height: 1.28;
            margin-bottom: 0.35rem;
        }

        .selected-news-meta {
            color: #94a3b8;
            font-size: 0.78rem;
            margin-bottom: 0.6rem;
        }

        .selected-news-summary {
            color: #cbd5e1;
            font-size: 0.9rem;
            line-height: 1.5;
        }

        .clickable-news-note {
            color: #94a3b8;
            font-size: 0.78rem;
            margin-top: -0.2rem;
            margin-bottom: 0.55rem;
        }


        .story-reader {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 20px;
            padding: 1.15rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .story-reader-label {
            color: #38bdf8;
            font-size: 0.76rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .story-reader-title {
            color: #f9fafb;
            font-size: 1.35rem;
            font-weight: 950;
            line-height: 1.25;
            margin-bottom: 0.45rem;
        }

        .story-reader-meta {
            color: #94a3b8;
            font-size: 0.8rem;
            margin-bottom: 0.85rem;
        }

        .story-reader-body {
            color: #d1d5db;
            font-size: 0.94rem;
            line-height: 1.58;
            white-space: pre-wrap;
        }

        .story-reader-warning {
            background: #451a03;
            border: 1px solid #92400e;
            color: #fed7aa;
            border-radius: 12px;
            padding: 0.7rem 0.85rem;
            font-size: 0.84rem;
            margin-top: 0.8rem;
            margin-bottom: 0.8rem;
        }

        .story-brief-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-top: 0.7rem;
        }

        .story-brief-title {
            color: #f9fafb;
            font-weight: 900;
            font-size: 0.95rem;
            margin-bottom: 0.35rem;
        }

        .story-brief-text {
            color: #cbd5e1;
            font-size: 0.86rem;
            line-height: 1.45;
        }


        .external-news-note {
            color: #94a3b8;
            font-size: 0.78rem;
            margin-top: -0.2rem;
            margin-bottom: 0.55rem;
        }

        .external-news-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 0.75rem;
            margin-bottom: 0.7rem;
        }

        .external-news-meta {
            color: #64748b;
            font-size: 0.74rem;
            margin-bottom: 0.25rem;
        }

        .external-news-summary {
            color: #cbd5e1;
            font-size: 0.82rem;
            line-height: 1.38;
        }


        /* =====================================================
           PROFESSIONAL MARKET INTELLIGENCE TERMINAL
           ===================================================== */

        .market-terminal-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #1e3a8a 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .market-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .market-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .market-signal-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.85rem;
            margin-bottom: 0.85rem;
        }

        .market-signal-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .market-signal-value {
            color: #f9fafb;
            font-size: 1.25rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .market-signal-note {
            color: #cbd5e1;
            font-size: 0.78rem;
        }

        .market-detail-panel {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 1rem;
            margin-top: 0.8rem;
            margin-bottom: 1rem;
        }

        .market-detail-title {
            color: #f9fafb;
            font-size: 1.15rem;
            font-weight: 950;
            margin-bottom: 0.25rem;
        }

        .market-detail-subtitle {
            color: #94a3b8;
            font-size: 0.82rem;
            margin-bottom: 0.65rem;
        }

        .market-interpretation-box {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 0.85rem;
            margin-top: 0.8rem;
        }

        .market-interpretation-title {
            color: #f9fafb;
            font-weight: 900;
            font-size: 0.94rem;
            margin-bottom: 0.25rem;
        }

        .market-interpretation-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.45;
        }


        /* =====================================================
           PROFESSIONAL FINANCE / COMPANY ANALYSIS TERMINAL
           ===================================================== */

        .finance-terminal-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 52%, #134e4a 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .finance-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .finance-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .finance-company-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        .finance-company-title {
            color: #f9fafb;
            font-size: 1.25rem;
            font-weight: 950;
            margin-bottom: 0.25rem;
        }

        .finance-company-subtitle {
            color: #94a3b8;
            font-size: 0.84rem;
        }

        .finance-action-note {
            color: #94a3b8;
            font-size: 0.8rem;
            margin-bottom: 0.55rem;
        }

        .finance-insight-box {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 0.95rem;
            margin-top: 0.8rem;
            margin-bottom: 1rem;
        }

        .finance-insight-title {
            color: #f9fafb;
            font-size: 0.98rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .finance-insight-text {
            color: #cbd5e1;
            font-size: 0.86rem;
            line-height: 1.45;
        }


        /* =====================================================
           PROFESSIONAL RESEARCH COMMAND CENTER
           ===================================================== */

        .research-command-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #312e81 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .research-command-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .research-command-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .research-workflow-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .research-workflow-title {
            color: #f9fafb;
            font-size: 0.98rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .research-workflow-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.42;
        }

        .research-status-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.8rem;
        }

        .research-status-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .research-status-value {
            color: #f9fafb;
            font-size: 1.25rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .research-action-note {
            color: #94a3b8;
            font-size: 0.8rem;
            margin-bottom: 0.55rem;
        }


        /* =====================================================
           PROFESSIONAL VALUATION / DCF TERMINAL
           ===================================================== */

        .valuation-terminal-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 52%, #78350f 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .valuation-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .valuation-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .valuation-scenario-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .valuation-scenario-title {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .valuation-scenario-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.42;
        }

        .valuation-result-card {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        .valuation-result-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .valuation-result-value {
            color: #f9fafb;
            font-size: 1.35rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .valuation-result-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }

        .valuation-warning-box {
            background: #451a03;
            border: 1px solid #92400e;
            color: #fed7aa;
            border-radius: 14px;
            padding: 0.75rem 0.9rem;
            font-size: 0.84rem;
            margin-top: 0.6rem;
            margin-bottom: 1rem;
        }


        /* =====================================================
           PROFESSIONAL RISK TERMINAL
           ===================================================== */

        .risk-terminal-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #7f1d1d 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .risk-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .risk-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .risk-score-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .risk-score-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .risk-score-value {
            color: #f9fafb;
            font-size: 1.35rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .risk-score-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }

        .risk-warning-card {
            background: #451a03;
            border: 1px solid #92400e;
            color: #fed7aa;
            border-radius: 14px;
            padding: 0.85rem;
            margin-bottom: 0.85rem;
        }

        .risk-action-card {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .risk-action-title {
            color: #f9fafb;
            font-weight: 900;
            font-size: 0.96rem;
            margin-bottom: 0.25rem;
        }

        .risk-action-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.42;
        }


        /* =====================================================
           INVESTMENT OUTPUT CENTER
           ===================================================== */

        .output-center-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #164e63 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .output-center-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .output-center-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .output-summary-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .output-summary-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .output-summary-value {
            color: #f9fafb;
            font-size: 1.35rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .output-summary-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }

        .pack-builder-box {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        .pack-builder-title {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .pack-builder-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.45;
        }


        /* =====================================================
           GLOBAL ACTIVE COMPANY WORKFLOW
           ===================================================== */

        .active-company-bar {
            background: #020617;
            border-bottom: 1px solid #1f2937;
            padding: 0.55rem 1.1rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
        }

        .active-company-left {
            display: flex;
            flex-direction: column;
            gap: 0.1rem;
        }

        .active-company-label {
            color: #94a3b8;
            font-size: 0.7rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .active-company-value {
            color: #f9fafb;
            font-size: 0.95rem;
            font-weight: 900;
        }

        .active-company-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }

        .active-company-pill {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 999px;
            padding: 0.25rem 0.6rem;
            color: #cbd5e1;
            font-size: 0.75rem;
            font-weight: 750;
        }

        .workflow-shortcut-panel {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 1rem;
        }

        .workflow-shortcut-title {
            color: #f9fafb;
            font-size: 0.98rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .workflow-shortcut-text {
            color: #94a3b8;
            font-size: 0.84rem;
            margin-bottom: 0.6rem;
        }


        /* =====================================================
           TERMINAL HEALTH CHECK
           ===================================================== */

        .health-terminal-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #14532d 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .health-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .health-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .health-score-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .health-score-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .health-score-value {
            color: #f9fafb;
            font-size: 1.35rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .health-score-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }


        /* =====================================================
           INSTITUTIONAL SCREENER 2.0
           ===================================================== */

        .screener-terminal-hero {
            background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #1e40af 100%);
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(0,0,0,0.28);
        }

        .screener-terminal-title {
            color: #f9fafb;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: -0.035em;
            margin-bottom: 0.25rem;
        }

        .screener-terminal-text {
            color: #cbd5e1;
            font-size: 0.92rem;
            max-width: 980px;
            margin-bottom: 0;
        }

        .screener-score-card {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .screener-score-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .screener-score-value {
            color: #f9fafb;
            font-size: 1.35rem;
            font-weight: 950;
            margin-top: 0.15rem;
        }

        .screener-score-note {
            color: #cbd5e1;
            font-size: 0.8rem;
        }

        .screener-methodology-box {
            background: #020617;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 1rem;
        }

        .screener-methodology-title {
            color: #f9fafb;
            font-weight: 900;
            font-size: 0.96rem;
            margin-bottom: 0.25rem;
        }

        .screener-methodology-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.42;
        }


        .market-brief-fallback {
            background: #0f172a;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.85rem;
        }

        .market-brief-title {
            color: #f9fafb;
            font-size: 0.98rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .market-brief-text {
            color: #cbd5e1;
            font-size: 0.84rem;
            line-height: 1.45;
        }


        .external-news-card .live-news-headline {
            color: #f9fafb;
            font-size: 0.96rem;
            font-weight: 900;
            line-height: 1.34;
            margin-bottom: 0.25rem;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300)
def fetch_market_strip_data():
    rows = []
    for item in MARKET_TICKERS:
        label = item["label"]
        symbol = item["symbol"]
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", interval="1d")
            if history.empty or "Close" not in history.columns:
                rows.append({"label": label, "symbol": symbol, "value": "N/A", "change_pct": None})
                continue
            closes = history["Close"].dropna()
            value = float(closes.iloc[-1]) if not closes.empty else None
            if value is not None and len(closes) >= 2 and float(closes.iloc[-2]) != 0:
                previous = float(closes.iloc[-2])
                change_pct = ((value / previous) - 1) * 100
            else:
                change_pct = None
            rows.append({"label": label, "symbol": symbol, "value": value, "change_pct": change_pct})
        except Exception:
            rows.append({"label": label, "symbol": symbol, "value": "N/A", "change_pct": None})
    return rows


def format_market_value(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    return f"{value:.2f}"



def render_market_strip():
    """
    Render working market ticker strip.
    Each ticker is a real Streamlit button. Clicking it opens the ticker detail
    inside the Markets function.
    """
    market_rows = fetch_market_strip_data()

    category_map = {
        "S&P 500": "Equity Index",
        "Nasdaq": "Growth Index",
        "Dow": "Industrial Index",
        "FTSE 100": "UK Equity Index",
        "US 10Y": "Rates",
        "Crude Oil": "Commodity",
        "Gold": "Commodity",
        "USD/ZAR": "FX",
        "Bitcoin": "Crypto",
    }

    purpose_map = {
        "S&P 500": "Global equity risk appetite and broad US market direction.",
        "Nasdaq": "Growth, technology, and long-duration equity sentiment.",
        "Dow": "Large-cap US industrial and economic signal.",
        "FTSE 100": "UK and global defensive/large-cap equity signal.",
        "US 10Y": "Discount-rate pressure for equities, bonds, and valuation multiples.",
        "Crude Oil": "Inflation, energy cost, and commodity-cycle signal.",
        "Gold": "Safe-haven demand, risk sentiment, and real-rate signal.",
        "USD/ZAR": "South Africa and emerging-market FX risk signal.",
        "Bitcoin": "Crypto, liquidity, and speculative risk appetite signal.",
    }

    st.markdown(
        """
        <div class="market-strip-wrapper">
            <div class="market-strip-title">Live Market Monitor — Daily Updates</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not market_rows:
        st.info("No market ticker data available.")
        return

    cols = st.columns(len(market_rows))

    for idx, row in enumerate(market_rows):
        label = row["label"]
        symbol = row["symbol"]
        value = row["value"]
        change_pct = row["change_pct"]

        value_text = format_market_value(value)

        if change_pct is None:
            arrow = "•"
            change_text = "N/A"
        elif change_pct > 0:
            arrow = "▲"
            change_text = f"{change_pct:.2f}%"
        elif change_pct < 0:
            arrow = "▼"
            change_text = f"{abs(change_pct):.2f}%"
        else:
            arrow = "•"
            change_text = "0.00%"

        button_label = f"{label}\n{value_text} {arrow} {change_text}"

        with cols[idx]:
            if st.button(
                button_label,
                key=f"top_strip_{symbol}",
                use_container_width=True,
            ):
                st.session_state["selected_market_instrument"] = {
                    "label": label,
                    "symbol": symbol,
                    "category": category_map.get(label, "Market"),
                    "purpose": purpose_map.get(label, "Market context indicator."),
                }
                st.query_params["view"] = "Markets"
                st.rerun()




def render_terminal_header():
    """
    Render the Fordsworth terminal header.
    Navigation is handled by a Streamlit radio ribbon so it opens in the same terminal.
    """
    st.markdown(
        """
        <div class="terminal-topbar">
            <div class="terminal-topbar-left">
                <span>Fordsworth</span>
                <span>Equity Research</span>
                <span>Portfolio Intelligence</span>
            </div>
            <div class="terminal-topbar-right">
                <span>Local Terminal</span>
                <span>AI Research Stack</span>
            </div>
        </div>

        <div class="terminal-brand-bar">
            <div class="terminal-brand">Fordsworth</div>
            <div class="terminal-actions">
                <span>Markets</span>
                <span>Research</span>
                <span>Portfolio</span>
                <span>Valuation</span>
                <span>Risk</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_terminal_function_ribbon(default_view: str = "Home") -> str:
    """
    Real working terminal function ribbon.
    Clicking a function changes the terminal view in the same browser tab.
    """
    views = [
        "Home",
        "Markets",
        "Finance",
        "Portfolio",
        "Research",
        "Reports",
        "Valuation",
        "Risk",
    ]

    if default_view not in views:
        default_view = "Home"

    index = views.index(default_view)

    st.markdown('<div class="working-ribbon">', unsafe_allow_html=True)

    selected_view = st.radio(
        "Fordsworth Function Ribbon",
        views,
        horizontal=True,
        index=index,
        key="terminal_view_radio",
        label_visibility="collapsed",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    try:
        st.query_params["view"] = selected_view
    except Exception:
        pass

    return selected_view


def get_latest_report(report_type: str):
    reports = list_reports(report_type)
    return reports[0] if reports else None


def preview_report(report_path, max_chars: int = 850) -> str:
    if report_path is None:
        return "No report generated yet."
    text = read_report(report_path)
    return text if len(text) <= max_chars else text[:max_chars] + "\n\n..."


def collect_recent_reports(limit: int = 10):
    rows = []
    for agent_name, config in REPORT_CONFIG.items():
        try:
            reports = list_reports(config["report_type"])
        except Exception:
            reports = []
        for report_path in reports:
            rows.append({"Agent": agent_name, "File Name": report_path.name, "Modified": report_path.stat().st_mtime, "Path Object": report_path})
    return sorted(rows, key=lambda row: row["Modified"], reverse=True)[:limit]


def count_total_reports() -> int:
    total = 0
    for config in REPORT_CONFIG.values():
        try:
            total += len(list_reports(config["report_type"]))
        except Exception:
            pass
    return total


def make_dataframe_arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    clean_df = df.copy()
    for column in clean_df.columns:
        if clean_df[column].dtype == "object":
            clean_df[column] = clean_df[column].fillna("").astype(str)
    return clean_df



def safe_snapshot_value(snapshot: dict, key: str, default="N/A"):
    value = snapshot.get(key, default)
    if value is None or value == "":
        return default
    return value


def build_stock_quality_rows(snapshot: dict) -> pd.DataFrame:
    """
    Build a compact financial quality table from available yfinance snapshot fields.
    """
    rows = [
        {
            "Area": "Valuation",
            "Metric": "Forward P/E",
            "Value": format_number_or_na(snapshot.get("forward_pe")),
            "Interpretation": "Lower can indicate cheaper valuation, but must be compared to growth and quality.",
        },
        {
            "Area": "Valuation",
            "Metric": "Trailing P/E",
            "Value": format_number_or_na(snapshot.get("trailing_pe")),
            "Interpretation": "Shows price relative to historical earnings.",
        },
        {
            "Area": "Risk",
            "Metric": "Beta",
            "Value": format_number_or_na(snapshot.get("beta")),
            "Interpretation": "Higher beta usually means higher market sensitivity.",
        },
        {
            "Area": "Income",
            "Metric": "Dividend Yield",
            "Value": format_percent_or_na(snapshot.get("dividend_yield")),
            "Interpretation": "Useful for income and shareholder-return context.",
        },
        {
            "Area": "Scale",
            "Metric": "Market Cap",
            "Value": format_large_number(snapshot.get("market_cap")),
            "Interpretation": "Company size and liquidity context.",
        },
    ]

    return pd.DataFrame(rows)


def render_stock_action_buttons(ticker: str):
    """
    Institutional action shortcuts from the tear sheet.
    These shortcuts keep Stock Tear Sheet inside Markets / Finance instead of the top ribbon.
    """
    st.markdown("### Analyst Actions")

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        if st.button("Run Deep Research", use_container_width=True, key=f"tear_deep_{ticker}"):
            with st.spinner(f"Generating Deep Research memo for {ticker}..."):
                report = run_deep_digger(ticker)
            st.success("Deep Research memo generated.")
            with st.expander("Open generated memo", expanded=True):
                st.markdown(report)

    with a2:
        if st.button("Open Valuation", use_container_width=True, key=f"tear_dcf_{ticker}"):
            st.query_params["view"] = "Valuation"
            st.rerun()

    with a3:
        if st.button("Open Research Modules", use_container_width=True, key=f"tear_research_{ticker}"):
            st.query_params["view"] = "Research"
            st.rerun()

    with a4:
        if st.button("Open Risk", use_container_width=True, key=f"tear_risk_{ticker}"):
            st.query_params["view"] = "Risk"
            st.rerun()


def render_professional_stock_tear_sheet(ticker: str):
    """
    Professional single-stock tear sheet.
    Ordered like an institutional analyst page:
    snapshot -> market data -> valuation -> quality -> thesis -> news -> actions -> business summary.
    """
    ticker = ticker.upper().strip()

    if not ticker:
        st.info("Enter a ticker to open the professional tear sheet.")
        return

    snapshot = fetch_stock_snapshot(ticker)
    position = get_position_by_ticker(ticker)

    if snapshot.get("error"):
        st.error(f"Market data error: {snapshot.get('error')}")
        return

    company_name = snapshot.get("company_name", ticker)

    st.markdown(
        f"""
        <div class="tear-section-card">
            <div class="tear-section-title">{ticker} — {company_name}</div>
            <div class="tear-section-note">
                Professional stock tear sheet: company snapshot, market data, valuation, quality, thesis, news and research actions.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Company Snapshot
    st.markdown("### 1. Company Snapshot")

    snap_col1, snap_col2, snap_col3, snap_col4 = st.columns(4)

    with snap_col1:
        st.metric("Sector", safe_snapshot_value(snapshot, "sector"))

    with snap_col2:
        st.metric("Industry", safe_snapshot_value(snapshot, "industry"))

    with snap_col3:
        st.metric("Currency", safe_snapshot_value(snapshot, "currency"))

    with snap_col4:
        st.metric("Market Cap", format_large_number(snapshot.get("market_cap")))

    st.divider()

    # 2. Price & Market Data
    st.markdown("### 2. Price & Market Data")

    latest_close = snapshot.get("latest_close")
    change = snapshot.get("change")
    change_pct = snapshot.get("change_pct")

    price_col1, price_col2, price_col3, price_col4, price_col5 = st.columns(5)

    with price_col1:
        st.metric(
            "Latest Close",
            format_number_or_na(latest_close),
            f"{format_number_or_na(change)} / {format_number_or_na(change_pct)}%",
        )

    with price_col2:
        st.metric("52W High", format_number_or_na(snapshot.get("fifty_two_week_high")))

    with price_col3:
        st.metric("52W Low", format_number_or_na(snapshot.get("fifty_two_week_low")))

    with price_col4:
        st.metric("Beta", format_number_or_na(snapshot.get("beta")))

    with price_col5:
        st.metric("Dividend Yield", format_percent_or_na(snapshot.get("dividend_yield")))

    st.divider()

    # 3. Valuation
    st.markdown("### 3. Valuation Metrics")

    val_col1, val_col2, val_col3, val_col4 = st.columns(4)

    with val_col1:
        st.metric("Forward P/E", format_number_or_na(snapshot.get("forward_pe")))

    with val_col2:
        st.metric("Trailing P/E", format_number_or_na(snapshot.get("trailing_pe")))

    with val_col3:
        if position:
            valuation = position.get("valuation", {})
            st.metric("Stored Fair Value", valuation.get("fair_value", "N/A"))
        else:
            st.metric("Stored Fair Value", "N/A")

    with val_col4:
        if position:
            valuation = position.get("valuation", {})
            st.metric("Bull Case", valuation.get("bull_case", "N/A"))
        else:
            st.metric("Bull Case", "N/A")

    st.divider()

    # 4. Financial Quality
    st.markdown("### 4. Financial Quality")

    quality_df = build_stock_quality_rows(snapshot)
    quality_df = make_dataframe_arrow_safe(quality_df)
    st.dataframe(quality_df, use_container_width=True, hide_index=True)

    st.markdown(
        """
        <span class="tear-quality-pill">Valuation</span>
        <span class="tear-quality-pill">Risk</span>
        <span class="tear-quality-pill">Scale</span>
        <span class="tear-quality-pill">Income</span>
        <span class="tear-quality-pill">Quality Review Required</span>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # 5. Thesis and Monitoring
    st.markdown("### 5. Thesis & Monitoring")

    thesis_col, monitoring_col = st.columns([1.35, 1])

    with thesis_col:
        if not position:
            st.warning("This ticker is not yet in the portfolio thesis library.")
            st.write("Use Research → Analyst Modules to create an IC memo, moat audit or red flag scan.")
        else:
            thesis = position.get("investment_thesis", {})
            st.markdown("#### One-Line Thesis")
            st.write(thesis.get("one_line", "No thesis recorded."))

            st.markdown("#### Core Drivers")
            core_drivers = thesis.get("core_drivers", [])
            if core_drivers:
                for item in core_drivers:
                    st.write(f"- {item}")
            else:
                st.write("No core drivers recorded.")

            st.markdown("#### Kill Criteria")
            kill_criteria = thesis.get("kill_criteria", [])
            if kill_criteria:
                for item in kill_criteria:
                    st.write(f"- {item}")
            else:
                st.write("No kill criteria recorded.")

    with monitoring_col:
        if not position:
            st.info("No stored monitoring settings.")
        else:
            monitoring = position.get("monitoring", {})
            st.write(f"**News Priority:** {monitoring.get('overnight_news_priority', 'N/A')}")
            st.write(f"**Weekly Thesis Review:** {monitoring.get('weekly_thesis_review', 'N/A')}")
            st.write(f"**Event Calendar:** {monitoring.get('include_in_event_calendar', 'N/A')}")
            st.write(f"**Market Curator:** {monitoring.get('include_in_market_curator', 'N/A')}")

    st.divider()

    # 6. Recent News
    st.markdown("### 6. Recent News")

    try:
        news_context = position if position else {
            "ticker": ticker,
            "company_name": company_name,
        }

        articles = fetch_company_news(news_context, page_size=5)

        if not articles:
            st.info("No recent articles found.")
        else:
            for article in articles:
                title = article.get("title", "No title")
                source = article.get("source", "Unknown source")
                published_at = article.get("published_at", "Unknown date")
                description = article.get("description", "")
                url = article.get("url", "")

                with st.expander(f"{title} — {source}"):
                    st.write(f"**Published:** {published_at}")
                    st.write(description)
                    if url:
                        st.write(url)

    except Exception as exc:
        st.warning(f"Could not fetch recent news: {exc}")

    st.divider()

    # 7. Saved Research Mentions
    st.markdown("### 7. Saved Research Mentions")

    mention_col1, mention_col2 = st.columns(2)

    with mention_col1:
        st.markdown("#### Morning Analyst Mentions")
        morning_matches = search_reports_for_text("morning_briefs", ticker, limit=3)

        if not morning_matches:
            st.info("No Morning Analyst mentions found.")
        else:
            for match in morning_matches:
                with st.container(border=True):
                    st.markdown(f"**{match['file_name']}**")
                    st.markdown(match["preview"])

    with mention_col2:
        st.markdown("#### Deep Research Memos")
        deep_matches = search_reports_for_text("deep_research", ticker, limit=3)

        if not deep_matches:
            st.info("No Deep Research memos found.")
        else:
            for match in deep_matches:
                with st.container(border=True):
                    st.markdown(f"**{match['file_name']}**")
                    st.markdown(match["preview"])

    st.divider()

    # 8. Analyst Actions
    render_stock_action_buttons(ticker)

    st.divider()

    # 9. Business Summary
    st.markdown("### 8. Business Summary")
    business_summary = snapshot.get("business_summary", "N/A")

    if business_summary and business_summary != "N/A":
        st.write(business_summary)
    else:
        st.info("No business summary available from market data provider.")


def render_stock_tear_sheet(ticker: str):
    """
    Compatibility wrapper.
    The professional stock tear sheet is now the standard stock view.
    """
    render_professional_stock_tear_sheet(ticker)




def get_home_market_breadth():
    """
    Build a simple market breadth summary from the top-strip tickers.
    """
    market_rows = fetch_market_strip_data()

    positive = 0
    negative = 0
    flat = 0

    strongest_label = "N/A"
    strongest_change = None
    weakest_label = "N/A"
    weakest_change = None

    for row in market_rows:
        label = row.get("label", "N/A")
        change_pct = row.get("change_pct")

        if change_pct is None:
            flat += 1
            continue

        if change_pct > 0:
            positive += 1
        elif change_pct < 0:
            negative += 1
        else:
            flat += 1

        if strongest_change is None or change_pct > strongest_change:
            strongest_change = change_pct
            strongest_label = label

        if weakest_change is None or change_pct < weakest_change:
            weakest_change = change_pct
            weakest_label = label

    return {
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "strongest_label": strongest_label,
        "strongest_change": strongest_change,
        "weakest_label": weakest_label,
        "weakest_change": weakest_change,
    }


def format_home_change(value):
    if value is None:
        return "N/A"
    try:
        return f"{value:.2f}%"
    except Exception:
        return "N/A"




# ============================================================
# GLOBAL ACTIVE COMPANY WORKFLOW
# ============================================================

def set_active_company(ticker: str, company_name: str = ""):
    """
    Set the global active company/ticker across Finance, Research, Valuation, Risk and Reports.
    """
    ticker = (ticker or "").upper().strip()

    if not ticker:
        return

    st.session_state["active_company_ticker"] = ticker
    st.session_state["home_selected_ticker"] = ticker

    if company_name:
        st.session_state["active_company_name"] = company_name


def get_active_company_ticker(default: str = "NVDA") -> str:
    """
    Get active ticker shared across the terminal.
    """
    return (
        st.session_state.get("active_company_ticker")
        or st.session_state.get("home_selected_ticker")
        or default
    )


def get_active_company_name(ticker: str = "") -> str:
    """
    Get active company name, fetching snapshot when possible.
    """
    ticker = ticker or get_active_company_ticker()

    cached_name = st.session_state.get("active_company_name")

    if cached_name and st.session_state.get("active_company_ticker") == ticker:
        return cached_name

    try:
        snapshot = fetch_stock_snapshot(ticker)
        company_name = snapshot.get("company_name", ticker)
        st.session_state["active_company_name"] = company_name
        return company_name
    except Exception:
        return ticker


def render_active_company_bar():
    """
    Persistent active company bar under the terminal ribbon.
    """
    ticker = get_active_company_ticker()
    company_name = get_active_company_name(ticker)

    st.markdown(
        f"""
        <div class="active-company-bar">
            <div class="active-company-left">
                <div class="active-company-label">Active Company</div>
                <div class="active-company-value">{ticker} — {company_name}</div>
            </div>
            <div class="active-company-pill-row">
                <div class="active-company-pill">Finance</div>
                <div class="active-company-pill">Research</div>
                <div class="active-company-pill">Valuation</div>
                <div class="active-company-pill">Risk</div>
                <div class="active-company-pill">Reports</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_active_company_shortcuts(location_key: str):
    """
    Navigation shortcuts for the active company workflow.
    """
    ticker = get_active_company_ticker()
    company_name = get_active_company_name(ticker)

    st.markdown(
        f"""
        <div class="workflow-shortcut-panel">
            <div class="workflow-shortcut-title">Active Workflow: {ticker} — {company_name}</div>
            <div class="workflow-shortcut-text">
                Carry this company across Finance, Research, Valuation, Risk and Reports.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        if st.button("Finance", use_container_width=True, key=f"{location_key}_active_finance"):
            st.query_params["view"] = "Finance"
            st.rerun()

    with c2:
        if st.button("Research", use_container_width=True, key=f"{location_key}_active_research"):
            st.query_params["view"] = "Research"
            st.rerun()

    with c3:
        if st.button("Valuation", use_container_width=True, key=f"{location_key}_active_valuation"):
            st.query_params["view"] = "Valuation"
            st.rerun()

    with c4:
        if st.button("Risk", use_container_width=True, key=f"{location_key}_active_risk"):
            st.query_params["view"] = "Risk"
            st.rerun()

    with c5:
        if st.button("Reports", use_container_width=True, key=f"{location_key}_active_reports"):
            st.query_params["view"] = "Reports"
            st.rerun()


# ============================================================
# HOME SCREENER HELPERS
# ============================================================

HOME_SCREENER_UNIVERSE = [
    {"Ticker": "NVDA", "Company": "Nvidia", "Theme": "AI semiconductors"},
    {"Ticker": "MSFT", "Company": "Microsoft", "Theme": "Cloud and enterprise AI"},
    {"Ticker": "AAPL", "Company": "Apple", "Theme": "Consumer ecosystem"},
    {"Ticker": "GOOGL", "Company": "Alphabet", "Theme": "Search, cloud and AI"},
    {"Ticker": "AMZN", "Company": "Amazon", "Theme": "E-commerce and AWS"},
    {"Ticker": "META", "Company": "Meta", "Theme": "Digital ads and AI"},
    {"Ticker": "JPM", "Company": "JPMorgan", "Theme": "Financials and credit cycle"},
    {"Ticker": "XOM", "Company": "Exxon Mobil", "Theme": "Energy and oil beta"},
    {"Ticker": "UNH", "Company": "UnitedHealth", "Theme": "Healthcare defensive"},
    {"Ticker": "TSLA", "Company": "Tesla", "Theme": "EV and high-beta growth"},
]


def get_home_market_breadth():
    market_rows = fetch_market_strip_data()

    positive = 0
    negative = 0
    flat = 0
    strongest_label = "N/A"
    weakest_label = "N/A"
    strongest_change = None
    weakest_change = None

    for row in market_rows:
        label = row.get("label", "N/A")
        change_pct = row.get("change_pct")

        if change_pct is None:
            flat += 1
            continue

        if change_pct > 0:
            positive += 1
        elif change_pct < 0:
            negative += 1
        else:
            flat += 1

        if strongest_change is None or change_pct > strongest_change:
            strongest_change = change_pct
            strongest_label = label

        if weakest_change is None or change_pct < weakest_change:
            weakest_change = change_pct
            weakest_label = label

    return {
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "strongest_label": strongest_label,
        "strongest_change": strongest_change,
        "weakest_label": weakest_label,
        "weakest_change": weakest_change,
    }


def format_home_change(value):
    if value is None:
        return "N/A"
    try:
        return f"{value:.2f}%"
    except Exception:
        return "N/A"


def build_home_screener_dataframe():
    rows = []

    for item in HOME_SCREENER_UNIVERSE:
        ticker = item["Ticker"]

        try:
            snapshot = fetch_stock_snapshot(ticker)

            change_pct = snapshot.get("change_pct")
            forward_pe = snapshot.get("forward_pe")
            beta = snapshot.get("beta")
            market_cap = snapshot.get("market_cap")

            if change_pct is None:
                momentum_label = "N/A"
            elif change_pct > 1:
                momentum_label = "Strong Up"
            elif change_pct > 0:
                momentum_label = "Up"
            elif change_pct < -1:
                momentum_label = "Weak"
            elif change_pct < 0:
                momentum_label = "Down"
            else:
                momentum_label = "Flat"

            if forward_pe is None:
                valuation_label = "N/A"
            elif forward_pe < 18:
                valuation_label = "Value"
            elif forward_pe < 35:
                valuation_label = "Fair"
            else:
                valuation_label = "Premium"

            rows.append(
                {
                    "Ticker": ticker,
                    "Company": snapshot.get("company_name", item["Company"]),
                    "Theme": item["Theme"],
                    "Latest": format_number_or_na(snapshot.get("latest_close")),
                    "Daily %": "N/A" if change_pct is None else f"{change_pct:.2f}%",
                    "Market Cap": format_large_number(market_cap),
                    "Forward P/E": format_number_or_na(forward_pe),
                    "Beta": format_number_or_na(beta),
                    "Momentum": momentum_label,
                    "Valuation": valuation_label,
                }
            )

        except Exception:
            rows.append(
                {
                    "Ticker": ticker,
                    "Company": item["Company"],
                    "Theme": item["Theme"],
                    "Latest": "N/A",
                    "Daily %": "N/A",
                    "Market Cap": "N/A",
                    "Forward P/E": "N/A",
                    "Beta": "N/A",
                    "Momentum": "N/A",
                    "Valuation": "N/A",
                }
            )

    return pd.DataFrame(rows)


def render_home_screener():
    st.markdown("### Home Screener")
    st.caption("A quick screener-style view of major names and market themes.")

    screener_df = build_home_screener_dataframe()

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        search_text = st.text_input(
            "Search ticker/company/theme",
            placeholder="Example: NVDA, cloud, energy",
            key="home_screener_search",
        ).strip().lower()

    with col2:
        momentum_filter = st.selectbox(
            "Momentum",
            ["All", "Strong Up", "Up", "Flat", "Down", "Weak", "N/A"],
            key="home_screener_momentum",
        )

    with col3:
        valuation_filter = st.selectbox(
            "Valuation",
            ["All", "Value", "Fair", "Premium", "N/A"],
            key="home_screener_valuation",
        )

    filtered_df = screener_df.copy()

    if search_text:
        mask = (
            filtered_df["Ticker"].str.lower().str.contains(search_text, na=False)
            | filtered_df["Company"].str.lower().str.contains(search_text, na=False)
            | filtered_df["Theme"].str.lower().str.contains(search_text, na=False)
        )
        filtered_df = filtered_df[mask]

    if momentum_filter != "All":
        filtered_df = filtered_df[filtered_df["Momentum"] == momentum_filter]

    if valuation_filter != "All":
        filtered_df = filtered_df[filtered_df["Valuation"] == valuation_filter]

    filtered_df = make_dataframe_arrow_safe(filtered_df)
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    st.markdown("### Screener Actions")

    action_col1, action_col2, action_col3 = st.columns(3)

    selected_ticker = st.selectbox(
        "Select ticker for action",
        [row["Ticker"] for row in HOME_SCREENER_UNIVERSE],
        key="home_screener_selected_ticker",
    )

    with action_col1:
        if st.button("Open in Finance", use_container_width=True, key="home_screener_open_finance"):
            st.session_state["home_selected_ticker"] = selected_ticker
            st.query_params["view"] = "Finance"
            st.rerun()

    with action_col2:
        if st.button("Open Markets", use_container_width=True, key="home_screener_open_markets"):
            st.query_params["view"] = "Markets"
            st.rerun()

    with action_col3:
        if st.button("Open Research", use_container_width=True, key="home_screener_open_research"):
            st.session_state["home_selected_ticker"] = selected_ticker
            st.query_params["view"] = "Research"
            st.rerun()






# ============================================================
# HOME CONTINUOUS BUSINESS NEWS FEED
# ============================================================

BUSINESS_NEWS_SECTIONS = [
    {
        "section": "Top Stories",
        "tickers": ["SPY", "QQQ", "DIA", "NVDA", "MSFT", "JPM"],
        "description": "Market-moving business stories across equities, technology and finance.",
    },
    {
        "section": "Global Markets",
        "tickers": ["SPY", "QQQ", "DIA", "TLT", "HYG"],
        "description": "Equities, bonds, credit and risk appetite.",
    },
    {
        "section": "Technology & AI",
        "tickers": ["NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN"],
        "description": "AI, semiconductors, cloud, software and platform companies.",
    },
    {
        "section": "Finance & Banks",
        "tickers": ["JPM", "BAC", "GS", "MS", "XLF"],
        "description": "Banks, credit cycle, capital markets and financial conditions.",
    },
    {
        "section": "Energy & Commodities",
        "tickers": ["XOM", "CVX", "CL=F", "GC=F", "XLE"],
        "description": "Oil, gold, energy costs, inflation and commodity-sensitive equities.",
    },
    {
        "section": "Currencies, Rates & Credit",
        "tickers": ["USDZAR=X", "^TNX", "TLT", "HYG", "LQD"],
        "description": "FX, yields, bond duration and credit sentiment.",
    },
]



RSS_FEEDS_BY_SECTION = {
    "Top Stories": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.ft.com/rss/home",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    ],
    "Global Markets": [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.investing.com/rss/news_25.rss",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
    "Technology & AI": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.feedburner.com/TechCrunch/",
    ],
    "Finance & Banks": [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.investing.com/rss/news_25.rss",
    ],
    "Energy & Commodities": [
        "https://www.investing.com/rss/news_11.rss",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    ],
    "Currencies, Rates & Credit": [
        "https://www.investing.com/rss/news_1.rss",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
}


@st.cache_data(ttl=900)

def clean_html_summary(raw_text: str) -> str:
    """
    Clean RSS/HTML descriptions into readable news summaries.
    """
    text = str(raw_text or "")
    text = html.unescape(text)
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return clean_markdown_line(text)


def fetch_rss_items(feed_url: str, max_items: int = 10) -> list[dict]:
    """
    Fetch RSS/Atom feed items using Python standard library only.
    This avoids relying only on yfinance.news, which may return empty results.
    """
    items = []

    try:
        request = urllib.request.Request(
            feed_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FordsworthTerminal/1.0"
            },
        )

        with urllib.request.urlopen(request, timeout=8) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        # RSS format
        rss_items = root.findall(".//item")

        # Atom format fallback
        atom_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        if rss_items:
            for item in rss_items[:max_items]:
                title = item.findtext("title", default="No title")
                link = item.findtext("link", default="")
                description = item.findtext("description", default="")
                pub_date = item.findtext("pubDate", default="Recent")

                items.append(
                    {
                        "Title": html.unescape(clean_markdown_line(title)),
                        "Publisher": feed_url.replace("https://", "").replace("http://", "").split("/")[0],
                        "Published": html.unescape(pub_date),
                        "Summary": clean_html_summary(description),
                        "URL": link,
                    }
                )

        elif atom_items:
            for item in atom_items[:max_items]:
                title = item.findtext("{http://www.w3.org/2005/Atom}title", default="No title")
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                summary = item.findtext("{http://www.w3.org/2005/Atom}summary", default="")
                updated = item.findtext("{http://www.w3.org/2005/Atom}updated", default="Recent")

                items.append(
                    {
                        "Title": html.unescape(clean_markdown_line(title)),
                        "Publisher": feed_url.replace("https://", "").replace("http://", "").split("/")[0],
                        "Published": html.unescape(updated),
                        "Summary": clean_html_summary(summary),
                        "URL": link,
                    }
                )

    except Exception:
        return []

    return items



def get_newsapi_business_news(section_name: str, max_items: int = 12) -> list[dict]:
    """
    Optional reliable business-news feed using NewsAPI.
    Add NEWS_API_KEY to your .env or system environment.
    """
    api_key = os.getenv("NEWS_API_KEY", "")

    if not api_key:
        return []

    query_map = {
        "Top Stories": "business OR markets OR economy",
        "Global Markets": "stocks OR markets OR bonds",
        "Technology & AI": "technology OR artificial intelligence OR semiconductors",
        "Finance & Banks": "banks OR finance OR credit",
        "Energy & Commodities": "oil OR energy OR commodities",
        "Currencies, Rates & Credit": "currencies OR rates OR credit",
        "Company News": "company OR earnings",
    }

    query = query_map.get(section_name, "business OR markets")
    url = (
        "https://newsapi.org/v2/everything?"
        + urllib.parse.urlencode(
            {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_items,
                "apiKey": api_key,
            }
        )
    )

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "FordsworthTerminal/1.0"},
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))

        articles = payload.get("articles", [])
        items = []

        for article in articles[:max_items]:
            title = clean_markdown_line(article.get("title") or "")

            if not title:
                continue

            source = article.get("source", {}).get("name", "NewsAPI")
            published = article.get("publishedAt", "Recent")
            summary = clean_html_summary(article.get("description") or article.get("content") or "")
            link = article.get("url", "")

            items.append(
                {
                    "Section": section_name,
                    "Title": title,
                    "Publisher": source,
                    "Published": published,
                    "Summary": summary,
                    "URL": link,
                }
            )

        return items

    except Exception:
        return []


def get_fallback_business_news(section_name: str, max_items: int = 12) -> list[dict]:
    """
    Fetch business news from public RSS feeds as fallback/primary source.
    """
    feeds = RSS_FEEDS_BY_SECTION.get(section_name, RSS_FEEDS_BY_SECTION.get("Top Stories", []))
    results = []

    for feed_url in feeds:
        results.extend(fetch_rss_items(feed_url, max_items=max_items))

    seen = set()
    deduped = []

    for item in results:
        title_key = item.get("Title", "").strip().lower()

        if not title_key or title_key in seen:
            continue

        seen.add(title_key)
        deduped.append(item)

    return deduped[:max_items]


def get_static_business_news(section_name: str) -> list[dict]:
    """
    Do not generate fake placeholder headlines.
    Return empty list so the UI can show a clean live-feed status message.
    """
    return []


def get_business_news_items(section_name: str, tickers: list[str], limit_per_ticker: int = 2) -> list[dict]:
    """
    Get real business news for a section.
    1. Try optional NewsAPI if NEWS_API_KEY is configured.
    2. Try public RSS feeds.
    3. Fall back to yfinance ticker news.
    4. Return an empty list if no real news is available.
    """
    newsapi_items = get_newsapi_business_news(section_name, max_items=12)

    if newsapi_items:
        return newsapi_items

    rss_items = get_fallback_business_news(section_name, max_items=12)

    if rss_items:
        return rss_items

    items = []

    for ticker_symbol in tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            news_items = getattr(ticker, "news", []) or []

            for item in news_items[:limit_per_ticker]:
                title = clean_markdown_line(item.get("title") or "No title")

                if not title or title == "No title":
                    continue

                publisher = item.get("publisher") or item.get("source") or "Market source"
                link = item.get("link") or item.get("url") or ""
                provider_publish_time = item.get("providerPublishTime")
                summary = clean_html_summary(item.get("summary") or item.get("description") or item.get("content") or "")

                if provider_publish_time:
                    try:
                        published = pd.to_datetime(provider_publish_time, unit="s").strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        published = "Recent"
                else:
                    published = "Recent"

                items.append(
                    {
                        "Section": section_name,
                        "Title": title,
                        "Publisher": publisher,
                        "Published": published,
                        "Summary": summary,
                        "URL": link,
                    }
                )

        except Exception:
            continue

    seen = set()
    deduped = []

    for item in items:
        key = item.get("Title", "").strip().lower()

        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped



def render_clean_market_brief_fallback(section_key: str = "market"):
    """
    Professional Home fallback when live headlines are not returned.
    It does not pretend to be live news. It shows a market-context brief based on available market signals.
    """
    try:
        positive_count, negative_count, flat_count = get_home_market_signal_summary()
    except Exception:
        positive_count, negative_count, flat_count = 0, 0, 0

    if positive_count > negative_count:
        tone = "risk-on"
        interpretation = "More monitored instruments are trading higher than lower."
    elif negative_count > positive_count:
        tone = "risk-off"
        interpretation = "More monitored instruments are trading lower than higher."
    else:
        tone = "mixed"
        interpretation = "Market signals are balanced or inconclusive."

    st.markdown(
        f"""
        <div class="market-brief-fallback">
            <div class="market-brief-title">Market Brief</div>
            <div class="market-brief-text">
                Current monitored market tone is <strong>{tone}</strong>. {interpretation}
                Open the Markets tab for detailed index, futures, rates, currency, commodity and sector signals.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_live_news_items(items: list[dict], max_items: int = 8, section_key: str = "general"):
    """
    Render Home news as Bloomberg-style news cards:
    headline, source/time, readable summary and source button.
    """
    if not items:
        if "render_clean_market_brief_fallback" in globals():
            render_clean_market_brief_fallback(section_key)
        else:
            st.info("No news available at the moment.")
        return

    st.markdown(
        '<div class="external-news-note">Click the source button to open the full article.</div>',
        unsafe_allow_html=True,
    )

    for idx, item in enumerate(items[:max_items]):
        title = clean_html_summary(item.get("Title", "No title"))
        publisher = clean_html_summary(item.get("Publisher", "Market source"))
        published = clean_html_summary(item.get("Published", "Recent"))
        summary = clean_html_summary(item.get("Summary", ""))
        url = item.get("URL", "")

        if not summary:
            summary = (
                "Summary is not provided by this news feed. Open the original source for the full article, "
                "or configure a dedicated news API for richer story summaries."
            )

        st.markdown(
            f"""
            <div class="external-news-card">
                <div class="live-news-headline">{title}</div>
                <div class="external-news-meta">{publisher} · {published}</div>
                <div class="external-news-summary">{summary[:520]}{"..." if len(summary) > 520 else ""}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if url:
            st.link_button("Open full article", url, use_container_width=True)
        else:
            st.button(
                "Source unavailable",
                key=f"{section_key}_{idx}_no_source_news",
                use_container_width=True,
                disabled=True,
            )


def get_home_market_signal_summary():
    """
    Build a small summary of top-strip market signal counts.
    """
    market_rows = fetch_market_strip_data()

    positive = 0
    negative = 0
    flat = 0

    for row in market_rows:
        change_pct = row.get("change_pct")
        if change_pct is None:
            flat += 1
        elif change_pct > 0:
            positive += 1
        elif change_pct < 0:
            negative += 1
        else:
            flat += 1

    return positive, negative, flat


def render_home_business_news_feed():
    """
    Bloomberg-style Home page:
    continuous business news sections, no visible tickers, no click-required tabs.
    """
    st.subheader("Home")
    st.caption("Daily live business news and market context.")

    st.markdown(
        """
        <div class="home-news-terminal">
            <div class="home-news-terminal-title">Daily Business News</div>
            <p class="home-news-terminal-text">
                Live business news sections update directly on the Home page. Click any headline to open the full story from the original source.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_story_items = []
    for section in BUSINESS_NEWS_SECTIONS:
        top_story_items.extend(
            get_business_news_items(
                section_name=section["section"],
                tickers=section["tickers"],
                limit_per_ticker=1,
            )
        )

    if top_story_items:
        first_story = top_story_items[0]
        st.markdown(
            f"""
            <div class="breaking-strip">
                TOP STORY: {first_story.get("Title", "Business news update")}
            </div>
            """,
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.45, 1])

    with left:
        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Top Business News</div>
                <div class="live-news-section-subtitle">Market-moving stories across global business, technology, finance and commodities.</div>
            """,
            unsafe_allow_html=True,
        )
        render_live_news_items(top_story_items, max_items=12, section_key="top_business_news")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Technology & AI</div>
                <div class="live-news-section-subtitle">AI, semiconductors, cloud, software and mega-cap technology stories.</div>
            """,
            unsafe_allow_html=True,
        )
        tech_section = next(item for item in BUSINESS_NEWS_SECTIONS if item["section"] == "Technology & AI")
        tech_items = get_business_news_items(tech_section["section"], tech_section["tickers"], limit_per_ticker=2)
        render_live_news_items(tech_items, max_items=8, section_key="technology_ai")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Finance & Banks</div>
                <div class="live-news-section-subtitle">Banks, credit, capital markets, rates sensitivity and financial conditions.</div>
            """,
            unsafe_allow_html=True,
        )
        finance_section = next(item for item in BUSINESS_NEWS_SECTIONS if item["section"] == "Finance & Banks")
        finance_items = get_business_news_items(finance_section["section"], finance_section["tickers"], limit_per_ticker=2)
        render_live_news_items(finance_items, max_items=8, section_key="finance_banks")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Global Markets</div>
                <div class="live-news-section-subtitle">Equities, bonds, credit and global risk appetite.</div>
            """,
            unsafe_allow_html=True,
        )
        global_section = next(item for item in BUSINESS_NEWS_SECTIONS if item["section"] == "Global Markets")
        global_items = get_business_news_items(global_section["section"], global_section["tickers"], limit_per_ticker=2)
        render_live_news_items(global_items, max_items=6, section_key="global_markets")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Energy & Commodities</div>
                <div class="live-news-section-subtitle">Oil, gold, energy costs, inflation and commodities.</div>
            """,
            unsafe_allow_html=True,
        )
        energy_section = next(item for item in BUSINESS_NEWS_SECTIONS if item["section"] == "Energy & Commodities")
        energy_items = get_business_news_items(energy_section["section"], energy_section["tickers"], limit_per_ticker=2)
        render_live_news_items(energy_items, max_items=6, section_key="energy_commodities")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Currencies, Rates & Credit</div>
                <div class="live-news-section-subtitle">FX, yields, bond duration and credit sentiment.</div>
            """,
            unsafe_allow_html=True,
        )
        rates_section = next(item for item in BUSINESS_NEWS_SECTIONS if item["section"] == "Currencies, Rates & Credit")
        rates_items = get_business_news_items(rates_section["section"], rates_section["tickers"], limit_per_ticker=2)
        render_live_news_items(rates_items, max_items=6, section_key="rates_credit")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="live-news-section">
                <div class="live-news-section-title">Latest Research Feed</div>
                <div class="live-news-section-subtitle">Recently generated Fordsworth research outputs.</div>
            """,
            unsafe_allow_html=True,
        )

        recent_reports = collect_recent_reports(limit=5)

        if not recent_reports:
            st.info("No research reports generated yet.")
        else:
            for row in recent_reports:
                st.markdown(
                    f"""
                    <div class="live-news-item">
                        <div class="live-news-headline">{row["File Name"]}</div>
                        <div class="live-news-meta">{row["Agent"]} · {pd.to_datetime(row["Modified"], unit="s").strftime("%Y-%m-%d %H:%M")}</div>
                        <div class="live-news-summary">Saved research output available in Reports.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)


def render_home_view():
    """
    Home page: continuous live business-news feed.
    """
    render_home_business_news_feed()

# ============================================================
# MARKET INTELLIGENCE BOARD
# ============================================================

STOCK_UNIVERSE = [
    {"label": "Apple", "symbol": "AAPL", "category": "Mega-cap Technology", "purpose": "Consumer technology and ecosystem signal"},
    {"label": "Microsoft", "symbol": "MSFT", "category": "Mega-cap Technology", "purpose": "Cloud, enterprise software and AI signal"},
    {"label": "Nvidia", "symbol": "NVDA", "category": "AI Semiconductors", "purpose": "AI infrastructure and semiconductor cycle signal"},
    {"label": "Amazon", "symbol": "AMZN", "category": "Mega-cap Consumer/Cloud", "purpose": "E-commerce and AWS signal"},
    {"label": "Alphabet", "symbol": "GOOGL", "category": "Mega-cap Internet", "purpose": "Search, ads, cloud and AI signal"},
    {"label": "Meta", "symbol": "META", "category": "Mega-cap Internet", "purpose": "Digital ads and AI infrastructure signal"},
    {"label": "Tesla", "symbol": "TSLA", "category": "EV/Growth", "purpose": "EV, autonomy and high-beta growth sentiment"},
    {"label": "JPMorgan", "symbol": "JPM", "category": "Financials", "purpose": "Banking and credit-cycle signal"},
    {"label": "Exxon Mobil", "symbol": "XOM", "category": "Energy", "purpose": "Oil major and energy-price transmission"},
    {"label": "UnitedHealth", "symbol": "UNH", "category": "Healthcare", "purpose": "Defensive healthcare and policy risk signal"},
]

FUTURES_UNIVERSE = [
    {"label": "S&P 500 Futures", "symbol": "ES=F", "category": "Equity Futures", "purpose": "US broad-market futures direction"},
    {"label": "Nasdaq Futures", "symbol": "NQ=F", "category": "Equity Futures", "purpose": "Growth/technology futures direction"},
    {"label": "Dow Futures", "symbol": "YM=F", "category": "Equity Futures", "purpose": "US blue-chip futures direction"},
    {"label": "Russell 2000 Futures", "symbol": "RTY=F", "category": "Equity Futures", "purpose": "US small-cap risk appetite"},
    {"label": "Crude Oil Futures", "symbol": "CL=F", "category": "Commodity Futures", "purpose": "Energy and inflation impulse"},
    {"label": "Gold Futures", "symbol": "GC=F", "category": "Commodity Futures", "purpose": "Real rates and risk sentiment"},
    {"label": "Silver Futures", "symbol": "SI=F", "category": "Commodity Futures", "purpose": "Precious/industrial metals signal"},
    {"label": "Copper Futures", "symbol": "HG=F", "category": "Commodity Futures", "purpose": "Global growth and industrial demand signal"},
]

RATES_BONDS_UNIVERSE = [
    {"label": "US 10Y Yield", "symbol": "^TNX", "category": "Rates", "purpose": "Discount-rate and valuation pressure"},
    {"label": "US 5Y Yield", "symbol": "^FVX", "category": "Rates", "purpose": "Intermediate-rate expectations"},
    {"label": "US 30Y Yield", "symbol": "^TYX", "category": "Rates", "purpose": "Long-duration rate pressure"},
    {"label": "20+ Year Treasury ETF", "symbol": "TLT", "category": "Bonds ETF", "purpose": "Long-duration bond price sensitivity"},
    {"label": "7-10 Year Treasury ETF", "symbol": "IEF", "category": "Bonds ETF", "purpose": "Intermediate-duration bond proxy"},
    {"label": "Investment Grade Credit", "symbol": "LQD", "category": "Credit ETF", "purpose": "Investment-grade credit spread proxy"},
    {"label": "High Yield Credit", "symbol": "HYG", "category": "Credit ETF", "purpose": "High-yield credit and risk appetite proxy"},
]

CURRENCY_UNIVERSE = [
    {"label": "EUR/USD", "symbol": "EURUSD=X", "category": "FX", "purpose": "Dollar/euro global FX signal"},
    {"label": "GBP/USD", "symbol": "GBPUSD=X", "category": "FX", "purpose": "UK currency and dollar signal"},
    {"label": "USD/JPY", "symbol": "JPY=X", "category": "FX", "purpose": "Yen and carry-trade signal"},
    {"label": "USD/CHF", "symbol": "CHF=X", "category": "FX", "purpose": "Safe-haven FX signal"},
    {"label": "USD/CAD", "symbol": "CAD=X", "category": "FX", "purpose": "Oil-linked developed-market FX signal"},
    {"label": "AUD/USD", "symbol": "AUDUSD=X", "category": "FX", "purpose": "China/commodities risk signal"},
    {"label": "USD/ZAR", "symbol": "USDZAR=X", "category": "FX", "purpose": "South Africa and EM currency signal"},
]

SECTOR_UNIVERSE = [
    {"label": "Technology", "symbol": "XLK", "category": "Sector ETF", "purpose": "Technology sector performance"},
    {"label": "Financials", "symbol": "XLF", "category": "Sector ETF", "purpose": "Banks, insurers and financial cyclicality"},
    {"label": "Energy", "symbol": "XLE", "category": "Sector ETF", "purpose": "Energy producers and oil beta"},
    {"label": "Healthcare", "symbol": "XLV", "category": "Sector ETF", "purpose": "Healthcare defensiveness and policy risk"},
    {"label": "Consumer Discretionary", "symbol": "XLY", "category": "Sector ETF", "purpose": "Consumer cyclicality and spending"},
    {"label": "Consumer Staples", "symbol": "XLP", "category": "Sector ETF", "purpose": "Defensive consumer exposure"},
    {"label": "Industrials", "symbol": "XLI", "category": "Sector ETF", "purpose": "Industrial economy and capex cycle"},
    {"label": "Utilities", "symbol": "XLU", "category": "Sector ETF", "purpose": "Defensive/rate-sensitive equities"},
    {"label": "Materials", "symbol": "XLB", "category": "Sector ETF", "purpose": "Commodities and industrial inputs"},
    {"label": "Real Estate", "symbol": "XLRE", "category": "Sector ETF", "purpose": "Rate-sensitive property exposure"},
]


@st.cache_data(ttl=300)
def fetch_instrument_snapshot(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1mo", interval="1d")

        if history.empty or "Close" not in history.columns:
            return {
                "symbol": symbol,
                "latest": "N/A",
                "change_pct": None,
                "one_month_change_pct": None,
                "high_1m": "N/A",
                "low_1m": "N/A",
                "history": pd.DataFrame(),
            }

        closes = history["Close"].dropna()
        latest = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
        first = float(closes.iloc[0]) if len(closes) >= 1 else None

        change_pct = ((latest / previous) - 1) * 100 if previous and previous != 0 else None
        one_month_change_pct = ((latest / first) - 1) * 100 if first and first != 0 else None

        return {
            "symbol": symbol,
            "latest": latest,
            "change_pct": change_pct,
            "one_month_change_pct": one_month_change_pct,
            "high_1m": float(history["High"].max()) if "High" in history.columns else "N/A",
            "low_1m": float(history["Low"].min()) if "Low" in history.columns else "N/A",
            "history": history.reset_index(),
        }
    except Exception as exc:
        return {
            "symbol": symbol,
            "latest": "N/A",
            "change_pct": None,
            "one_month_change_pct": None,
            "high_1m": "N/A",
            "low_1m": "N/A",
            "history": pd.DataFrame(),
            "error": str(exc),
        }


def build_instrument_table(instruments: list[dict]) -> pd.DataFrame:
    rows = []

    for item in instruments:
        snap = fetch_instrument_snapshot(item["symbol"])

        rows.append(
            {
                "Name": item["label"],
                "Symbol": item["symbol"],
                "Category": item["category"],
                "Latest": format_market_value(snap.get("latest")),
                "1D Change %": "N/A" if snap.get("change_pct") is None else f"{snap.get('change_pct'):.2f}%",
                "1M Change %": "N/A" if snap.get("one_month_change_pct") is None else f"{snap.get('one_month_change_pct'):.2f}%",
                "1M High": format_market_value(snap.get("high_1m")),
                "1M Low": format_market_value(snap.get("low_1m")),
                "Purpose": item["purpose"],
            }
        )

    return pd.DataFrame(rows)


def get_top_and_underperformers(instruments: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []

    for item in instruments:
        snap = fetch_instrument_snapshot(item["symbol"])
        change_pct = snap.get("change_pct")

        if change_pct is None:
            continue

        rows.append(
            {
                "Name": item["label"],
                "Symbol": item["symbol"],
                "Category": item["category"],
                "Latest": format_market_value(snap.get("latest")),
                "1D Change %": change_pct,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    top = df.sort_values("1D Change %", ascending=False).head(5).copy()
    under = df.sort_values("1D Change %", ascending=True).head(5).copy()

    top["1D Change %"] = top["1D Change %"].map(lambda x: f"{x:.2f}%")
    under["1D Change %"] = under["1D Change %"].map(lambda x: f"{x:.2f}%")

    return top, under


def render_instrument_buttons(instruments: list[dict], key_prefix: str):
    cols = st.columns(4)

    for idx, item in enumerate(instruments):
        with cols[idx % 4]:
            if st.button(
                f"{item['label']} ({item['symbol']})",
                key=f"{key_prefix}_{item['symbol']}",
                use_container_width=True,
            ):
                st.session_state["selected_market_instrument"] = item


def render_instrument_detail(default_instrument: dict | None = None):
    selected = st.session_state.get("selected_market_instrument") or default_instrument

    if not selected:
        st.info("Click any sub-ticker above to view its detail.")
        return

    snap = fetch_instrument_snapshot(selected["symbol"])

    st.markdown(f"### {selected['label']} — {selected['symbol']}")
    st.caption(f"{selected['category']} | {selected['purpose']}")

    if "render_daily_update_box" in globals():
        render_daily_update_box(
            label=selected["label"],
            category=selected["category"],
            latest=snap.get("latest"),
            change_pct=snap.get("change_pct"),
            purpose=selected["purpose"],
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Latest", format_market_value(snap.get("latest")))

    with c2:
        st.metric("1D Change", "N/A" if snap.get("change_pct") is None else f"{snap.get('change_pct'):.2f}%")

    with c3:
        st.metric("1M Change", "N/A" if snap.get("one_month_change_pct") is None else f"{snap.get('one_month_change_pct'):.2f}%")

    with c4:
        st.metric("1M Range", f"{format_market_value(snap.get('low_1m'))} / {format_market_value(snap.get('high_1m'))}")

    history = snap.get("history")

    if isinstance(history, pd.DataFrame) and not history.empty and "Close" in history.columns:
        if "Date" in history.columns:
            chart_df = history[["Date", "Close"]].copy()
            chart_df["Date"] = pd.to_datetime(chart_df["Date"]).dt.date
            chart_df = chart_df.set_index("Date")
        elif "Datetime" in history.columns:
            chart_df = history[["Datetime", "Close"]].copy()
            chart_df["Datetime"] = pd.to_datetime(chart_df["Datetime"]).dt.date
            chart_df = chart_df.set_index("Datetime")
        else:
            chart_df = history[["Close"]].copy()

        st.markdown("### 1-Month Price Chart")
        st.line_chart(chart_df)

    st.markdown("### Interpretation")
    st.write(f"**What it tells you:** {selected['purpose']}")
    st.write("Use this movement as a market-context signal. It is not a trading recommendation.")


def render_market_intelligence_board():
    st.markdown("### Market Intelligence Board")
    st.caption("Stocks, top/underperformers, futures, rates, bonds, currencies, sectors and news.")

    market_section = st.radio(
        "Market section",
        ["Stocks", "Top & Underperformers", "Futures", "Rates & Bonds", "Currencies", "Sectors", "News"],
        horizontal=True,
        key="market_intelligence_section",
    )

    st.divider()

    if market_section == "Stocks":
        st.markdown("### Stocks")
        df = build_instrument_table(STOCK_UNIVERSE)
        df = make_dataframe_arrow_safe(df)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("### Click a stock")
        render_instrument_buttons(STOCK_UNIVERSE, "stock_btn")
        render_instrument_detail(STOCK_UNIVERSE[0])

    elif market_section == "Top & Underperformers":
        st.markdown("### Top Performers and Underperformers")
        top, under = get_top_and_underperformers(STOCK_UNIVERSE)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Top Performers")
            if top.empty:
                st.info("No performance data available.")
            else:
                top = make_dataframe_arrow_safe(top)
                st.dataframe(top, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("#### Underperformers")
            if under.empty:
                st.info("No performance data available.")
            else:
                under = make_dataframe_arrow_safe(under)
                st.dataframe(under, use_container_width=True, hide_index=True)

        st.markdown("### Click a stock")
        render_instrument_buttons(STOCK_UNIVERSE, "performer_btn")
        render_instrument_detail(STOCK_UNIVERSE[0])

    elif market_section == "Futures":
        st.markdown("### Futures")
        df = build_instrument_table(FUTURES_UNIVERSE)
        df = make_dataframe_arrow_safe(df)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("### Click a futures contract")
        render_instrument_buttons(FUTURES_UNIVERSE, "futures_btn")
        render_instrument_detail(FUTURES_UNIVERSE[0])

    elif market_section == "Rates & Bonds":
        st.markdown("### Rates & Bonds")
        df = build_instrument_table(RATES_BONDS_UNIVERSE)
        df = make_dataframe_arrow_safe(df)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("### Click a rate or bond instrument")
        render_instrument_buttons(RATES_BONDS_UNIVERSE, "rates_btn")
        render_instrument_detail(RATES_BONDS_UNIVERSE[0])

    elif market_section == "Currencies":
        st.markdown("### Currencies")
        df = build_instrument_table(CURRENCY_UNIVERSE)
        df = make_dataframe_arrow_safe(df)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("### Click a currency pair")
        render_instrument_buttons(CURRENCY_UNIVERSE, "currency_btn")
        render_instrument_detail(CURRENCY_UNIVERSE[0])

    elif market_section == "Sectors":
        st.markdown("### Sectors")
        df = build_instrument_table(SECTOR_UNIVERSE)
        df = make_dataframe_arrow_safe(df)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("### Click a sector")
        render_instrument_buttons(SECTOR_UNIVERSE, "sector_btn")
        render_instrument_detail(SECTOR_UNIVERSE[0])

    elif market_section == "News":
        st.markdown("### Latest News and Research Signals")
        recent_reports = collect_recent_reports(limit=8)

        if not recent_reports:
            st.info("No saved research reports yet.")
        else:
            news_df = pd.DataFrame(
                [
                    {
                        "Source": row["Agent"],
                        "Report": row["File Name"],
                        "Modified": pd.to_datetime(row["Modified"], unit="s").strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for row in recent_reports
                ]
            )
            news_df = make_dataframe_arrow_safe(news_df)
            st.dataframe(news_df, use_container_width=True, hide_index=True)



# ============================================================
# PROFESSIONAL MARKET INTELLIGENCE TERMINAL
# ============================================================

MARKET_TERMINAL_SECTIONS = {
    "Market Overview": [
        {"label": "S&P 500", "symbol": "^GSPC", "category": "US Equity Index", "purpose": "Broad US equity risk appetite and global benchmark sentiment."},
        {"label": "Nasdaq", "symbol": "^IXIC", "category": "US Growth Index", "purpose": "Growth, technology and long-duration equity sentiment."},
        {"label": "Dow", "symbol": "^DJI", "category": "US Blue-Chip Index", "purpose": "Large-cap industrial and economic signal."},
        {"label": "Russell 2000", "symbol": "^RUT", "category": "US Small Caps", "purpose": "Domestic cyclicality and small-cap risk appetite."},
        {"label": "VIX", "symbol": "^VIX", "category": "Volatility", "purpose": "Equity-market fear, hedging demand and risk regime indicator."},
    ],
    "Equity Movers": [
        {"label": "Nvidia", "symbol": "NVDA", "category": "AI Semiconductors", "purpose": "AI infrastructure and semiconductor cycle signal."},
        {"label": "Microsoft", "symbol": "MSFT", "category": "Cloud / Software", "purpose": "Enterprise software, cloud and AI monetisation signal."},
        {"label": "Apple", "symbol": "AAPL", "category": "Consumer Technology", "purpose": "Consumer ecosystem and mega-cap quality signal."},
        {"label": "Amazon", "symbol": "AMZN", "category": "E-commerce / Cloud", "purpose": "Consumer demand and cloud infrastructure signal."},
        {"label": "JPMorgan", "symbol": "JPM", "category": "Banking", "purpose": "Credit cycle, banking and financial conditions signal."},
        {"label": "Exxon Mobil", "symbol": "XOM", "category": "Energy", "purpose": "Energy equity and commodity transmission signal."},
    ],
    "Futures": [
        {"label": "S&P 500 Futures", "symbol": "ES=F", "category": "Equity Futures", "purpose": "Near-term US broad-market direction."},
        {"label": "Nasdaq Futures", "symbol": "NQ=F", "category": "Equity Futures", "purpose": "Near-term growth and technology risk appetite."},
        {"label": "Dow Futures", "symbol": "YM=F", "category": "Equity Futures", "purpose": "Near-term blue-chip market direction."},
        {"label": "Crude Oil Futures", "symbol": "CL=F", "category": "Commodity Futures", "purpose": "Energy cost, inflation and commodity-cycle signal."},
        {"label": "Gold Futures", "symbol": "GC=F", "category": "Commodity Futures", "purpose": "Safe-haven demand, real rates and risk sentiment."},
    ],
    "Rates & Bonds": [
        {"label": "US 10Y Yield", "symbol": "^TNX", "category": "Rates", "purpose": "Discount-rate pressure for equities, bonds and valuation multiples."},
        {"label": "US 30Y Yield", "symbol": "^TYX", "category": "Rates", "purpose": "Long-duration rate pressure and inflation expectations."},
        {"label": "Long Treasury ETF", "symbol": "TLT", "category": "Bond ETF", "purpose": "Long-duration Treasury price sensitivity."},
        {"label": "Investment Grade Credit", "symbol": "LQD", "category": "Credit ETF", "purpose": "Investment-grade credit risk and spread proxy."},
        {"label": "High Yield Credit", "symbol": "HYG", "category": "Credit ETF", "purpose": "High-yield credit risk appetite and stress signal."},
    ],
    "Currencies": [
        {"label": "EUR/USD", "symbol": "EURUSD=X", "category": "FX", "purpose": "Dollar/euro global currency signal."},
        {"label": "GBP/USD", "symbol": "GBPUSD=X", "category": "FX", "purpose": "UK currency and dollar-risk signal."},
        {"label": "USD/JPY", "symbol": "JPY=X", "category": "FX", "purpose": "Yen, carry trade and rate-differential signal."},
        {"label": "USD/ZAR", "symbol": "USDZAR=X", "category": "FX", "purpose": "South Africa and emerging-market FX risk signal."},
        {"label": "AUD/USD", "symbol": "AUDUSD=X", "category": "FX", "purpose": "China, commodities and risk appetite signal."},
    ],
    "Commodities": [
        {"label": "Crude Oil", "symbol": "CL=F", "category": "Energy", "purpose": "Inflation, energy input costs and commodity risk."},
        {"label": "Gold", "symbol": "GC=F", "category": "Precious Metals", "purpose": "Safe-haven demand, real rates and macro uncertainty."},
        {"label": "Silver", "symbol": "SI=F", "category": "Precious / Industrial Metal", "purpose": "Industrial demand and precious-metal sentiment."},
        {"label": "Copper", "symbol": "HG=F", "category": "Industrial Metal", "purpose": "Global growth and industrial activity signal."},
    ],
    "Sectors": [
        {"label": "Technology", "symbol": "XLK", "category": "Sector ETF", "purpose": "Technology sector leadership and growth risk appetite."},
        {"label": "Financials", "symbol": "XLF", "category": "Sector ETF", "purpose": "Banks, insurers and financial-cycle signal."},
        {"label": "Energy", "symbol": "XLE", "category": "Sector ETF", "purpose": "Energy sector and oil-price equity beta."},
        {"label": "Healthcare", "symbol": "XLV", "category": "Sector ETF", "purpose": "Defensive healthcare and policy-risk signal."},
        {"label": "Consumer Discretionary", "symbol": "XLY", "category": "Sector ETF", "purpose": "Consumer cyclicality and spending signal."},
        {"label": "Consumer Staples", "symbol": "XLP", "category": "Sector ETF", "purpose": "Defensive consumer exposure."},
    ],
}


@st.cache_data(ttl=300)
def fetch_market_terminal_snapshot(symbol: str) -> dict:
    """
    Fetch a 1-month market snapshot using yfinance.
    """
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1mo", interval="1d")

        if history.empty or "Close" not in history.columns:
            return {
                "latest": None,
                "change_pct": None,
                "one_month_change_pct": None,
                "high_1m": None,
                "low_1m": None,
                "history": pd.DataFrame(),
                "error": "No price history available.",
            }

        closes = history["Close"].dropna()

        latest = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
        first = float(closes.iloc[0]) if len(closes) >= 1 else None

        change_pct = ((latest / previous) - 1) * 100 if previous and previous != 0 else None
        one_month_change_pct = ((latest / first) - 1) * 100 if first and first != 0 else None

        return {
            "latest": latest,
            "change_pct": change_pct,
            "one_month_change_pct": one_month_change_pct,
            "high_1m": float(history["High"].max()) if "High" in history.columns else None,
            "low_1m": float(history["Low"].min()) if "Low" in history.columns else None,
            "history": history.reset_index(),
            "error": None,
        }

    except Exception as exc:
        return {
            "latest": None,
            "change_pct": None,
            "one_month_change_pct": None,
            "high_1m": None,
            "low_1m": None,
            "history": pd.DataFrame(),
            "error": str(exc),
        }


def format_market_terminal_number(value):
    if value is None:
        return "N/A"
    try:
        if abs(float(value)) >= 1000:
            return f"{float(value):,.2f}"
        return f"{float(value):.2f}"
    except Exception:
        return "N/A"


def format_market_terminal_pct(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "N/A"


def build_market_terminal_table(instruments: list[dict]) -> pd.DataFrame:
    rows = []

    for item in instruments:
        snap = fetch_market_terminal_snapshot(item["symbol"])

        rows.append(
            {
                "Name": item["label"],
                "Symbol": item["symbol"],
                "Category": item["category"],
                "Latest": format_market_terminal_number(snap.get("latest")),
                "1D Change": format_market_terminal_pct(snap.get("change_pct")),
                "1M Change": format_market_terminal_pct(snap.get("one_month_change_pct")),
                "1M High": format_market_terminal_number(snap.get("high_1m")),
                "1M Low": format_market_terminal_number(snap.get("low_1m")),
                "Why It Matters": item["purpose"],
            }
        )

    return pd.DataFrame(rows)


def get_market_terminal_breadth(instruments: list[dict]) -> dict:
    positive = 0
    negative = 0
    flat = 0
    strongest = None
    weakest = None

    for item in instruments:
        snap = fetch_market_terminal_snapshot(item["symbol"])
        change_pct = snap.get("change_pct")

        if change_pct is None:
            flat += 1
            continue

        if change_pct > 0:
            positive += 1
        elif change_pct < 0:
            negative += 1
        else:
            flat += 1

        row = {
            "label": item["label"],
            "change_pct": change_pct,
        }

        if strongest is None or change_pct > strongest["change_pct"]:
            strongest = row

        if weakest is None or change_pct < weakest["change_pct"]:
            weakest = row

    return {
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "strongest": strongest,
        "weakest": weakest,
    }


def render_market_terminal_detail(item: dict):
    """
    Render detail panel for one selected instrument.
    """
    if item.get("symbol", "").isalpha() and len(item.get("symbol", "")) <= 5:
        set_active_company(item["symbol"], item.get("label", ""))

    snap = fetch_market_terminal_snapshot(item["symbol"])

    st.markdown(
        f"""
        <div class="market-detail-panel">
            <div class="market-detail-title">{item['label']} — {item['symbol']}</div>
            <div class="market-detail-subtitle">{item['category']} · {item['purpose']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Latest", format_market_terminal_number(snap.get("latest")))

    with c2:
        st.metric("1D Change", format_market_terminal_pct(snap.get("change_pct")))

    with c3:
        st.metric("1M Change", format_market_terminal_pct(snap.get("one_month_change_pct")))

    with c4:
        st.metric(
            "1M Range",
            f"{format_market_terminal_number(snap.get('low_1m'))} / {format_market_terminal_number(snap.get('high_1m'))}",
        )

    history = snap.get("history")

    if isinstance(history, pd.DataFrame) and not history.empty and "Close" in history.columns:
        if "Date" in history.columns:
            chart_df = history[["Date", "Close"]].copy()
            chart_df["Date"] = pd.to_datetime(chart_df["Date"]).dt.date
            chart_df = chart_df.set_index("Date")
        elif "Datetime" in history.columns:
            chart_df = history[["Datetime", "Close"]].copy()
            chart_df["Datetime"] = pd.to_datetime(chart_df["Datetime"]).dt.date
            chart_df = chart_df.set_index("Datetime")
        else:
            chart_df = history[["Close"]].copy()

        st.line_chart(chart_df, use_container_width=True)
    else:
        st.info("No chart data available for this instrument.")

    st.markdown(
        f"""
        <div class="market-interpretation-box">
            <div class="market-interpretation-title">Interpretation</div>
            <div class="market-interpretation-text">
                {item['purpose']} Use this as a market-context signal. Check whether the move affects sector leadership,
                valuation multiples, rates, currencies, credit conditions or portfolio risk appetite.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Suggested Analyst Action")
    change_pct = snap.get("change_pct")

    if change_pct is None:
        st.write("- Data unavailable. Cross-check the instrument from another source.")
    elif change_pct > 1.0:
        st.write("- Positive daily move. Check whether this supports risk-on positioning or sector leadership.")
    elif change_pct < -1.0:
        st.write("- Negative daily move. Check whether this indicates risk-off pressure, macro stress or sector weakness.")
    else:
        st.write("- Moderate daily move. Treat as context and confirm with related instruments.")


def render_market_terminal_news():
    """
    Market news panel using the same public feed helpers if available.
    """
    st.markdown("### Market News")

    if "get_business_news_items" in globals():
        items = get_business_news_items(
            "Global Markets",
            ["SPY", "QQQ", "DIA", "TLT", "HYG"],
            limit_per_ticker=2,
        )

        if "render_live_news_items" in globals():
            render_live_news_items(items, max_items=10, section_key="markets_news")
        else:
            for item in items[:10]:
                st.write(f"**{item.get('Title', 'No title')}**")
                st.caption(f"{item.get('Publisher', 'Market source')} · {item.get('Published', 'Recent')}")
                st.write(item.get("Summary", ""))
    else:
        st.info("News helpers are not available in this build.")


def render_professional_market_terminal():
    """
    Professional Markets function.
    """
    render_active_company_shortcuts("markets_terminal")

    st.markdown(
        """
        <div class="market-terminal-hero">
            <div class="market-terminal-title">Market Intelligence Terminal</div>
            <p class="market-terminal-text">
                Monitor equities, futures, rates, bonds, currencies, commodities, sectors and market news.
                Use the tables for screening and click an instrument to open chart, interpretation and analyst action.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section = st.radio(
        "Market section",
        list(MARKET_TERMINAL_SECTIONS.keys()) + ["Market News"],
        horizontal=True,
        key="professional_market_section",
    )

    if section == "Market News":
        render_market_terminal_news()
        return

    instruments = MARKET_TERMINAL_SECTIONS[section]
    breadth = get_market_terminal_breadth(instruments)

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.markdown(
            f"""
            <div class="market-signal-card">
                <div class="market-signal-label">Positive</div>
                <div class="market-signal-value">{breadth['positive']}</div>
                <div class="market-signal-note">Instruments higher today.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s2:
        st.markdown(
            f"""
            <div class="market-signal-card">
                <div class="market-signal-label">Negative</div>
                <div class="market-signal-value">{breadth['negative']}</div>
                <div class="market-signal-note">Instruments lower today.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s3:
        strongest = breadth.get("strongest")
        strongest_text = "N/A" if not strongest else f"{strongest['label']} {format_market_terminal_pct(strongest['change_pct'])}"
        st.markdown(
            f"""
            <div class="market-signal-card">
                <div class="market-signal-label">Strongest</div>
                <div class="market-signal-value">{strongest_text}</div>
                <div class="market-signal-note">Best daily signal in section.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s4:
        weakest = breadth.get("weakest")
        weakest_text = "N/A" if not weakest else f"{weakest['label']} {format_market_terminal_pct(weakest['change_pct'])}"
        st.markdown(
            f"""
            <div class="market-signal-card">
                <div class="market-signal-label">Weakest</div>
                <div class="market-signal-value">{weakest_text}</div>
                <div class="market-signal-note">Weakest daily signal in section.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(f"### {section}")

    table_df = build_market_terminal_table(instruments)
    table_df = make_dataframe_arrow_safe(table_df)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    st.markdown("### Open Instrument")

    options = [f"{item['label']} ({item['symbol']})" for item in instruments]
    selected_label = st.selectbox(
        "Select instrument",
        options,
        key=f"market_terminal_select_{section}",
    )

    selected_idx = options.index(selected_label)
    selected_item = instruments[selected_idx]

    render_market_terminal_detail(selected_item)


def render_overview():
    """
    Markets page: professional market intelligence terminal.
    """
    st.subheader("Markets")
    st.caption("Market intelligence, live signals, charts, interpretation and analyst actions.")

    render_professional_market_terminal()



def render_stock_tear_sheet_view():
    st.subheader("Stock Tear Sheet")
    tear_left, tear_right = st.columns([1.1, 2.9])
    with tear_left:
        tear_sheet_ticker = st.text_input("Ticker", placeholder="Enter ticker, e.g. AAPL", key="tear_sheet_ticker")
        if st.button("Open Stock Tear Sheet", use_container_width=True):
            if not tear_sheet_ticker.strip():
                st.warning("Enter a ticker first.")
            else:
                st.session_state["active_tear_sheet_ticker"] = tear_sheet_ticker.upper().strip()
    with tear_right:
        st.markdown("""
            <div class="tear-sheet-card">
                <div class="tear-sheet-title">Single-stock analysis view</div>
                <p class="tear-sheet-text">Enter a ticker to view market data, valuation snapshot, stored thesis, kill criteria, recent news, saved research mentions, and Deep Digger access.</p>
            </div>
        """, unsafe_allow_html=True)
    if st.session_state.get("active_tear_sheet_ticker"):
        st.markdown(f"### Open Tear Sheet: {st.session_state['active_tear_sheet_ticker']}")
        render_stock_tear_sheet(st.session_state["active_tear_sheet_ticker"])



# ============================================================
# PROFESSIONAL VALUATION / DCF TERMINAL
# ============================================================

def get_valuation_default_ticker():
    """
    Default ticker for Valuation.
    """
    return get_active_company_ticker("NVDA")


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def calculate_dcf_scenario(
    current_revenue: float,
    revenue_growth: float,
    ebit_margin: float,
    tax_rate: float,
    reinvestment_rate: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    forecast_years: int = 5,
) -> dict:
    """
    Simplified professional DCF engine.
    Revenue grows annually. FCF = EBIT after tax less reinvestment.
    Terminal value uses Gordon Growth.
    """
    revenue = current_revenue
    present_value_fcf = 0.0
    forecast_rows = []

    for year in range(1, forecast_years + 1):
        revenue = revenue * (1 + revenue_growth)
        ebit = revenue * ebit_margin
        nopat = ebit * (1 - tax_rate)
        reinvestment = revenue * reinvestment_rate
        fcf = max(nopat - reinvestment, 0)
        discount_factor = (1 + wacc) ** year
        pv_fcf = fcf / discount_factor
        present_value_fcf += pv_fcf

        forecast_rows.append(
            {
                "Year": year,
                "Revenue": revenue,
                "EBIT": ebit,
                "NOPAT": nopat,
                "Reinvestment": reinvestment,
                "Free Cash Flow": fcf,
                "PV FCF": pv_fcf,
            }
        )

    final_fcf = forecast_rows[-1]["Free Cash Flow"] if forecast_rows else 0

    if wacc <= terminal_growth:
        terminal_value = 0
        pv_terminal_value = 0
    else:
        terminal_value = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal_value = terminal_value / ((1 + wacc) ** forecast_years)

    enterprise_value = present_value_fcf + pv_terminal_value
    equity_value = enterprise_value - net_debt

    if shares_outstanding > 0:
        fair_value_per_share = equity_value / shares_outstanding
    else:
        fair_value_per_share = 0

    return {
        "forecast_rows": forecast_rows,
        "present_value_fcf": present_value_fcf,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": fair_value_per_share,
    }


def build_dcf_report(
    ticker: str,
    company_name: str,
    current_price: float,
    assumptions: dict,
    scenario_results: dict,
) -> str:
    """
    Build markdown valuation report.
    """
    report = f"# Valuation Report — {ticker}\n\n"
    report += f"**Company:** {company_name}\n\n"
    report += f"**Current Price:** {format_number_or_na(current_price)}\n\n"

    report += "## Key Assumptions\n\n"
    report += f"- Current Revenue: {assumptions['current_revenue']:,.2f}\n"
    report += f"- Net Debt: {assumptions['net_debt']:,.2f}\n"
    report += f"- Shares Outstanding: {assumptions['shares_outstanding']:,.2f}\n"
    report += f"- Tax Rate: {assumptions['tax_rate']:.2%}\n"
    report += f"- Reinvestment Rate: {assumptions['reinvestment_rate']:.2%}\n"
    report += f"- Terminal Growth: {assumptions['terminal_growth']:.2%}\n"
    report += f"- Forecast Years: {assumptions['forecast_years']}\n\n"

    report += "## Scenario Output\n\n"
    report += "| Scenario | Revenue Growth | EBIT Margin | WACC | Fair Value | Upside / Downside |\n"
    report += "|---|---:|---:|---:|---:|---:|\n"

    for scenario_name, result in scenario_results.items():
        fair_value = result["fair_value_per_share"]
        upside = ((fair_value / current_price) - 1) * 100 if current_price else 0
        scenario_assumptions = result["assumptions"]
        report += (
            f"| {scenario_name} | {scenario_assumptions['revenue_growth']:.2%} | "
            f"{scenario_assumptions['ebit_margin']:.2%} | {scenario_assumptions['wacc']:.2%} | "
            f"{fair_value:,.2f} | {upside:.2f}% |\n"
        )

    report += "\n## Analyst Interpretation\n\n"
    report += "- Compare the base-case fair value to the current market price.\n"
    report += "- Use the bear case to understand downside risk.\n"
    report += "- Use the bull case to understand upside optionality.\n"
    report += "- Validate revenue growth, margins and WACC using company filings and market data.\n\n"
    report += "## Important Note\n\n"
    report += "This is a simplified DCF model for research workflow purposes. It should be reviewed and validated before investment use.\n"

    return report


def render_valuation_summary_cards(current_price: float, scenario_results: dict):
    """
    Display scenario valuation result cards.
    """
    cols = st.columns(3)

    for col, scenario_name in zip(cols, ["Bear", "Base", "Bull"]):
        result = scenario_results.get(scenario_name, {})
        fair_value = result.get("fair_value_per_share", 0)
        upside = ((fair_value / current_price) - 1) * 100 if current_price else 0

        with col:
            st.markdown(
                f"""
                <div class="valuation-result-card">
                    <div class="valuation-result-label">{scenario_name} Case</div>
                    <div class="valuation-result-value">{fair_value:,.2f}</div>
                    <div class="valuation-result-note">Upside / downside: {upside:.2f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_valuation_terminal():
    """
    Professional Valuation / DCF terminal.
    """
    st.markdown(
        """
        <div class="valuation-terminal-hero">
            <div class="valuation-terminal-title">Valuation Terminal</div>
            <p class="valuation-terminal-text">
                Build a simplified bear/base/bull DCF, review fair value per share, upside/downside,
                forecast free cash flow, sensitivity and save a valuation report.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.1, 1])

    with col1:
        ticker = st.text_input(
            "Ticker",
            value=get_valuation_default_ticker(),
            placeholder="Example: AAPL, MSFT, NVDA",
            key="valuation_terminal_ticker",
        ).upper().strip()

    with col2:
        if st.button("Load from Finance Selection", use_container_width=True, key="valuation_load_finance_selection"):
            st.session_state["home_selected_ticker"] = get_valuation_default_ticker()
            st.rerun()

    if not ticker:
        st.info("Enter a ticker to begin valuation.")
        return

    st.session_state["home_selected_ticker"] = ticker

    snapshot = fetch_stock_snapshot(ticker)

    if snapshot.get("error"):
        st.error(f"Could not load company data: {snapshot.get('error')}")
        return

    company_name = snapshot.get("company_name", ticker)
    set_active_company(ticker, company_name)
    current_price = safe_float(snapshot.get("latest_close"), 0)
    market_cap = safe_float(snapshot.get("market_cap"), 0)
    shares_from_market_cap = market_cap / current_price if current_price > 0 else 0

    st.markdown(f"### {ticker} — {company_name}")

    p1, p2, p3, p4 = st.columns(4)

    with p1:
        st.metric("Current Price", format_number_or_na(current_price))

    with p2:
        st.metric("Market Cap", format_large_number(market_cap))

    with p3:
        st.metric("Forward P/E", format_number_or_na(snapshot.get("forward_pe")))

    with p4:
        st.metric("Beta", format_number_or_na(snapshot.get("beta")))

    st.markdown(
        """
        <div class="valuation-warning-box">
            This DCF is a simplified analyst workflow model. Use it to frame scenarios, not as a final investment valuation without review.
        </div>
        """,
        unsafe_allow_html=True,
    )

    assumptions_tab, output_tab, forecast_tab, sensitivity_tab, report_tab = st.tabs(
        [
            "Assumptions",
            "Scenario Output",
            "Forecast",
            "Sensitivity",
            "Save Report",
        ]
    )

    with assumptions_tab:
        st.markdown("### Core Inputs")

        c1, c2, c3 = st.columns(3)

        with c1:
            current_revenue = st.number_input(
                "Current Revenue",
                value=float(max(market_cap * 0.35, 1_000_000_000)),
                step=100_000_000.0,
                key="valuation_current_revenue",
            )

            net_debt = st.number_input(
                "Net Debt",
                value=0.0,
                step=100_000_000.0,
                key="valuation_net_debt",
            )

        with c2:
            shares_outstanding = st.number_input(
                "Shares Outstanding",
                value=float(max(shares_from_market_cap, 1_000_000_000)),
                step=100_000_000.0,
                key="valuation_shares_outstanding",
            )

            tax_rate = st.number_input(
                "Tax Rate",
                value=21.0,
                step=1.0,
                key="valuation_tax_rate",
            ) / 100

        with c3:
            reinvestment_rate = st.number_input(
                "Reinvestment Rate (% of revenue)",
                value=5.0,
                step=0.5,
                key="valuation_reinvestment_rate",
            ) / 100

            terminal_growth = st.number_input(
                "Terminal Growth",
                value=2.5,
                step=0.25,
                key="valuation_terminal_growth",
            ) / 100

        forecast_years = st.slider(
            "Forecast Years",
            min_value=3,
            max_value=10,
            value=5,
            key="valuation_forecast_years",
        )

        st.markdown("### Scenario Assumptions")

        bear_col, base_col, bull_col = st.columns(3)

        with bear_col:
            st.markdown("#### Bear")
            bear_growth = st.number_input("Bear Revenue Growth", value=3.0, step=0.5, key="bear_growth") / 100
            bear_margin = st.number_input("Bear EBIT Margin", value=18.0, step=0.5, key="bear_margin") / 100
            bear_wacc = st.number_input("Bear WACC", value=11.0, step=0.25, key="bear_wacc") / 100

        with base_col:
            st.markdown("#### Base")
            base_growth = st.number_input("Base Revenue Growth", value=7.0, step=0.5, key="base_growth") / 100
            base_margin = st.number_input("Base EBIT Margin", value=25.0, step=0.5, key="base_margin") / 100
            base_wacc = st.number_input("Base WACC", value=9.0, step=0.25, key="base_wacc") / 100

        with bull_col:
            st.markdown("#### Bull")
            bull_growth = st.number_input("Bull Revenue Growth", value=11.0, step=0.5, key="bull_growth") / 100
            bull_margin = st.number_input("Bull EBIT Margin", value=30.0, step=0.5, key="bull_margin") / 100
            bull_wacc = st.number_input("Bull WACC", value=8.0, step=0.25, key="bull_wacc") / 100

    # Values persist through tabs because Streamlit executes all at once.
    assumptions = {
        "current_revenue": safe_float(st.session_state.get("valuation_current_revenue"), max(market_cap * 0.35, 1_000_000_000)),
        "net_debt": safe_float(st.session_state.get("valuation_net_debt"), 0),
        "shares_outstanding": safe_float(st.session_state.get("valuation_shares_outstanding"), max(shares_from_market_cap, 1_000_000_000)),
        "tax_rate": safe_float(st.session_state.get("valuation_tax_rate"), 21.0) / 100,
        "reinvestment_rate": safe_float(st.session_state.get("valuation_reinvestment_rate"), 5.0) / 100,
        "terminal_growth": safe_float(st.session_state.get("valuation_terminal_growth"), 2.5) / 100,
        "forecast_years": int(st.session_state.get("valuation_forecast_years", 5)),
    }

    scenario_inputs = {
        "Bear": {
            "revenue_growth": safe_float(st.session_state.get("bear_growth"), 3.0) / 100,
            "ebit_margin": safe_float(st.session_state.get("bear_margin"), 18.0) / 100,
            "wacc": safe_float(st.session_state.get("bear_wacc"), 11.0) / 100,
        },
        "Base": {
            "revenue_growth": safe_float(st.session_state.get("base_growth"), 7.0) / 100,
            "ebit_margin": safe_float(st.session_state.get("base_margin"), 25.0) / 100,
            "wacc": safe_float(st.session_state.get("base_wacc"), 9.0) / 100,
        },
        "Bull": {
            "revenue_growth": safe_float(st.session_state.get("bull_growth"), 11.0) / 100,
            "ebit_margin": safe_float(st.session_state.get("bull_margin"), 30.0) / 100,
            "wacc": safe_float(st.session_state.get("bull_wacc"), 8.0) / 100,
        },
    }

    scenario_results = {}

    for scenario_name, scenario in scenario_inputs.items():
        result = calculate_dcf_scenario(
            current_revenue=assumptions["current_revenue"],
            revenue_growth=scenario["revenue_growth"],
            ebit_margin=scenario["ebit_margin"],
            tax_rate=assumptions["tax_rate"],
            reinvestment_rate=assumptions["reinvestment_rate"],
            wacc=scenario["wacc"],
            terminal_growth=assumptions["terminal_growth"],
            net_debt=assumptions["net_debt"],
            shares_outstanding=assumptions["shares_outstanding"],
            forecast_years=assumptions["forecast_years"],
        )
        result["assumptions"] = scenario
        scenario_results[scenario_name] = result

    with output_tab:
        st.markdown("### Scenario Output")
        render_valuation_summary_cards(current_price, scenario_results)

        output_rows = []

        for scenario_name, result in scenario_results.items():
            fair_value = result["fair_value_per_share"]
            upside = ((fair_value / current_price) - 1) * 100 if current_price else 0
            scenario = result["assumptions"]

            output_rows.append(
                {
                    "Scenario": scenario_name,
                    "Revenue Growth": f"{scenario['revenue_growth']:.2%}",
                    "EBIT Margin": f"{scenario['ebit_margin']:.2%}",
                    "WACC": f"{scenario['wacc']:.2%}",
                    "Enterprise Value": format_large_number(result["enterprise_value"]),
                    "Equity Value": format_large_number(result["equity_value"]),
                    "Fair Value / Share": f"{fair_value:,.2f}",
                    "Upside / Downside": f"{upside:.2f}%",
                }
            )

        output_df = pd.DataFrame(output_rows)
        output_df = make_dataframe_arrow_safe(output_df)
        st.dataframe(output_df, use_container_width=True, hide_index=True)

    with forecast_tab:
        st.markdown("### Base Case Forecast")

        base_forecast_df = pd.DataFrame(scenario_results["Base"]["forecast_rows"])
        for col in ["Revenue", "EBIT", "NOPAT", "Reinvestment", "Free Cash Flow", "PV FCF"]:
            if col in base_forecast_df.columns:
                base_forecast_df[col] = base_forecast_df[col].map(lambda x: f"{x:,.2f}")

        base_forecast_df = make_dataframe_arrow_safe(base_forecast_df)
        st.dataframe(base_forecast_df, use_container_width=True, hide_index=True)

    with sensitivity_tab:
        st.markdown("### Base Case Sensitivity")

        wacc_values = [scenario_inputs["Base"]["wacc"] - 0.01, scenario_inputs["Base"]["wacc"], scenario_inputs["Base"]["wacc"] + 0.01]
        growth_values = [assumptions["terminal_growth"] - 0.005, assumptions["terminal_growth"], assumptions["terminal_growth"] + 0.005]

        sensitivity_rows = []

        for wacc in wacc_values:
            row = {"WACC": f"{wacc:.2%}"}
            for growth in growth_values:
                result = calculate_dcf_scenario(
                    current_revenue=assumptions["current_revenue"],
                    revenue_growth=scenario_inputs["Base"]["revenue_growth"],
                    ebit_margin=scenario_inputs["Base"]["ebit_margin"],
                    tax_rate=assumptions["tax_rate"],
                    reinvestment_rate=assumptions["reinvestment_rate"],
                    wacc=wacc,
                    terminal_growth=growth,
                    net_debt=assumptions["net_debt"],
                    shares_outstanding=assumptions["shares_outstanding"],
                    forecast_years=assumptions["forecast_years"],
                )
                row[f"g {growth:.2%}"] = f"{result['fair_value_per_share']:,.2f}"
            sensitivity_rows.append(row)

        sensitivity_df = pd.DataFrame(sensitivity_rows)
        sensitivity_df = make_dataframe_arrow_safe(sensitivity_df)
        st.dataframe(sensitivity_df, use_container_width=True, hide_index=True)

    with report_tab:
        st.markdown("### Save Valuation Report")

        report = build_dcf_report(
            ticker=ticker,
            company_name=company_name,
            current_price=current_price,
            assumptions=assumptions,
            scenario_results=scenario_results,
        )

        with st.expander("Preview valuation report", expanded=False):
            st.markdown(report)

        if st.button("Save Valuation Report", use_container_width=True, key="save_valuation_terminal_report"):
            saved_path = save_markdown_report(
                report_type="valuation_reports",
                title=f"Valuation Report {ticker}",
                content=report,
            )
            st.success(f"Valuation report saved: {saved_path.name}")

        if st.button("Open Reports / Export Center", use_container_width=True, key="valuation_open_reports"):
            st.query_params["view"] = "Reports"
            st.rerun()


def render_valuation_lab_view():
    """
    Valuation page: professional DCF/scenario terminal.
    """
    st.subheader("Valuation")
    st.caption("Bear/base/bull DCF, fair value per share, sensitivity and valuation report output.")

    render_valuation_terminal()


# ============================================================
# RESEARCH ANALYST MODULES
# ============================================================

def save_module_output(module_name: str, ticker: str, content: str):
    safe_ticker = ticker.upper().strip() if ticker else "GENERAL"
    return save_markdown_report(
        report_type="deep_research",
        title=f"{module_name} {safe_ticker}",
        content=content,
    )


def render_institutional_screener_module():
    st.markdown("#### Institutional Screener")
    st.caption("Screen a ticker universe using market data, valuation ratios and analyst judgement.")

    tickers_text = st.text_area(
        "Ticker universe",
        value="AAPL, MSFT, NVDA, GOOGL, AMZN, META, JPM, XOM",
        height=90,
        key="module_screener_tickers",
    )

    screen_style = st.selectbox(
        "Screen style",
        ["Quality Growth", "Value", "Compounders", "High Momentum", "Defensive"],
        key="module_screener_style",
    )

    if st.button("Run Institutional Screener", use_container_width=True, key="run_institutional_screener"):
        tickers = [
            item.strip().upper()
            for item in tickers_text.replace("\n", ",").split(",")
            if item.strip()
        ]

        report = f"# Institutional Screener\n\n**Screen style:** {screen_style}\n\n"

        rows = []

        for ticker in tickers:
            try:
                snapshot = fetch_stock_snapshot(ticker)
                rows.append(
                    {
                        "Ticker": ticker,
                        "Company": snapshot.get("company_name", ticker),
                        "Sector": snapshot.get("sector", "N/A"),
                        "Market Cap": format_large_number(snapshot.get("market_cap")),
                        "Forward P/E": format_number_or_na(snapshot.get("forward_pe")),
                        "Beta": format_number_or_na(snapshot.get("beta")),
                        "Latest Close": format_number_or_na(snapshot.get("latest_close")),
                    }
                )

                report += f"## {ticker} — {snapshot.get('company_name', ticker)}\n"
                report += f"- Sector: {snapshot.get('sector', 'N/A')}\n"
                report += f"- Market cap: {format_large_number(snapshot.get('market_cap'))}\n"
                report += f"- Forward P/E: {format_number_or_na(snapshot.get('forward_pe'))}\n"
                report += f"- Beta: {format_number_or_na(snapshot.get('beta'))}\n"
                report += "- Next action: Run Moat Audit, Red Flag Scanner and Valuation.\n\n"

            except Exception:
                rows.append(
                    {
                        "Ticker": ticker,
                        "Company": ticker,
                        "Sector": "N/A",
                        "Market Cap": "N/A",
                        "Forward P/E": "N/A",
                        "Beta": "N/A",
                        "Latest Close": "N/A",
                    }
                )

        if rows:
            df = pd.DataFrame(rows)
            df = make_dataframe_arrow_safe(df)
            st.dataframe(df, use_container_width=True, hide_index=True)

        saved_path = save_module_output("Institutional Screener", "Universe", report)
        st.success(f"Screener saved: {saved_path.name}")
        st.markdown(report)


def render_red_flag_module():
    st.markdown("#### Red Flag Scanner")
    st.caption("First-pass governance, valuation, leverage, margin, cash flow and risk review.")

    ticker = st.text_input("Ticker", key="module_red_flag_ticker").upper().strip()
    notes = st.text_area("Analyst notes / known concerns", height=120, key="module_red_flag_notes")

    if st.button("Run Red Flag Scanner", use_container_width=True, key="run_red_flag_scanner"):
        if not ticker:
            st.warning("Enter a ticker first.")
            return

        snapshot = fetch_stock_snapshot(ticker)

        report = f"""# Red Flag Scanner — {ticker}

**Company:** {snapshot.get('company_name', ticker)}

## Checklist

| Area | Question | Status |
|---|---|---|
| Valuation | Is valuation stretched relative to growth? | Review required |
| Leverage | Is debt/refinancing risk material? | Review required |
| Margins | Are margins deteriorating or abnormally high? | Review required |
| Cash Flow | Are earnings converting into cash? | Review required |
| Governance | Any governance, accounting or related-party concerns? | Review required |
| Competition | Is the moat weakening? | Review required |
| Regulation | Any litigation or regulatory exposure? | Review required |

## Analyst Notes

{notes if notes.strip() else "No analyst notes supplied."}

## Output

This is a first-pass red flag scan. Validate with filings, transcripts and reliable market data.
"""

        saved_path = save_module_output("Red Flag Scanner", ticker, report)
        st.success(f"Red flag report saved: {saved_path.name}")
        st.markdown(report)


def render_earnings_decode_module():
    st.markdown("#### Earnings Call Decode")
    st.caption("Paste an earnings transcript or notes and extract key topics, tone and follow-up questions.")

    ticker = st.text_input("Ticker", key="module_earnings_ticker").upper().strip()
    transcript = st.text_area("Paste transcript / call notes", height=260, key="module_earnings_transcript")

    if st.button("Decode Earnings Call", use_container_width=True, key="run_earnings_decode"):
        if not ticker:
            st.warning("Enter a ticker first.")
            return

        lower_text = transcript.lower()
        keywords = {
            "growth": "Growth / demand",
            "margin": "Margins",
            "guidance": "Guidance",
            "cash flow": "Cash flow",
            "competition": "Competition",
            "pricing": "Pricing power",
            "ai": "AI / technology investment",
            "debt": "Debt / balance sheet",
        }

        found = [label for key, label in keywords.items() if key in lower_text]

        report = f"# Earnings Call Decode — {ticker}\n\n"
        report += "## Key Topics Detected\n\n"

        if found:
            for item in found:
                report += f"- {item}\n"
        else:
            report += "- No tracked keywords detected. Review transcript manually.\n"

        report += "\n## Transcript / Notes Extract\n\n"
        report += transcript[:4000] if transcript.strip() else "No transcript supplied."
        report += "\n\n## Analyst Follow-Up\n\n"
        report += "- Compare tone to prior quarter.\n"
        report += "- Identify guidance changes.\n"
        report += "- Check whether narrative matches financials.\n"
        report += "- Feed conclusions into Thesis Tracker.\n"

        saved_path = save_module_output("Earnings Call Decode", ticker, report)
        st.success(f"Earnings decode saved: {saved_path.name}")
        st.markdown(report)


def render_moat_audit_module():
    st.markdown("#### Moat Audit")
    st.caption("Assess brand, switching costs, network effects, cost advantage, intangibles and distribution.")

    ticker = st.text_input("Ticker", key="module_moat_ticker").upper().strip()
    notes = st.text_area("Moat evidence / notes", height=120, key="module_moat_notes")

    if st.button("Run Moat Audit", use_container_width=True, key="run_moat_audit"):
        if not ticker:
            st.warning("Enter a ticker first.")
            return

        snapshot = fetch_stock_snapshot(ticker)

        report = f"""# Moat Audit — {ticker}

**Company:** {snapshot.get('company_name', ticker)}
**Sector:** {snapshot.get('sector', 'N/A')}
**Industry:** {snapshot.get('industry', 'N/A')}

## Moat Dimensions

| Moat Source | Assessment Focus |
|---|---|
| Brand | Pricing power, loyalty, premium positioning |
| Switching Costs | Lock-in, replacement difficulty, workflow integration |
| Network Effects | Does scale improve the product value? |
| Cost Advantage | Scale, procurement, technology or distribution advantage |
| Intangible Assets | Patents, licences, data, proprietary models |
| Distribution | Channel access and customer reach |

## Analyst Notes

{notes if notes.strip() else "No analyst notes supplied."}

## Preliminary View

Final moat rating should be based on margins, retention, competitive intensity and durability of returns.
"""

        saved_path = save_module_output("Moat Audit", ticker, report)
        st.success(f"Moat audit saved: {saved_path.name}")
        st.markdown(report)


def render_bull_bear_module():
    st.markdown("#### Bull vs Bear Pressure Test")
    st.caption("Stress-test the investment thesis before capital allocation.")

    ticker = st.text_input("Ticker", key="module_bull_bear_ticker").upper().strip()
    thesis = st.text_area("Base thesis", height=140, key="module_bull_bear_thesis")

    if st.button("Run Bull vs Bear Test", use_container_width=True, key="run_bull_bear"):
        if not ticker:
            st.warning("Enter a ticker first.")
            return

        snapshot = fetch_stock_snapshot(ticker)

        report = f"""# Bull vs Bear Pressure Test — {ticker}

**Company:** {snapshot.get('company_name', ticker)}

## Base Thesis

{thesis if thesis.strip() else "No base thesis supplied."}

## Bull Case

- Revenue growth remains stronger than expected.
- Margins expand or remain resilient.
- Market multiple remains supportive.
- Competitive position improves.
- Catalysts accelerate investor recognition.

## Bear Case

- Growth slows or disappoints expectations.
- Margins compress due to competition, costs or pricing pressure.
- Valuation multiple contracts.
- Regulation, execution risk or balance-sheet risk increases.
- Thesis drivers fail to materialise.

## Key Questions

- What evidence proves the bull case?
- What evidence invalidates the thesis?
- What valuation downside exists if the bear case is right?
- What position size is justified by the risk/reward?
"""

        saved_path = save_module_output("Bull Bear Test", ticker, report)
        st.success(f"Bull vs bear report saved: {saved_path.name}")
        st.markdown(report)


def render_position_sizing_module():
    st.markdown("#### Position Sizing Decision")
    st.caption("Turn conviction, upside/downside and liquidity into a position-size recommendation.")

    ticker = st.text_input("Ticker", key="module_sizing_ticker").upper().strip()

    c1, c2 = st.columns(2)

    with c1:
        conviction = st.selectbox("Conviction", ["Low", "Medium", "High"], key="module_sizing_conviction")
        liquidity = st.selectbox("Liquidity", ["Low", "Medium", "High"], key="module_sizing_liquidity")

    with c2:
        upside = st.number_input("Estimated upside %", value=25.0, step=1.0, key="module_sizing_upside")
        downside = st.number_input("Estimated downside %", value=12.0, step=1.0, key="module_sizing_downside")

    current_weight = st.number_input(
        "Current / proposed portfolio weight %",
        value=3.0,
        step=0.5,
        key="module_sizing_weight",
    )

    if st.button("Generate Position Sizing Decision", use_container_width=True, key="run_position_sizing"):
        if not ticker:
            st.warning("Enter a ticker first.")
            return

        reward_risk = None
        if downside > 0:
            reward_risk = upside / downside

        if reward_risk is None:
            sizing_view = "Cannot calculate reward/risk because downside is zero or missing."
        elif reward_risk >= 3 and conviction == "High":
            sizing_view = "Candidate for larger position, subject to liquidity and risk limits."
        elif reward_risk >= 2:
            sizing_view = "Candidate for medium position."
        elif reward_risk >= 1:
            sizing_view = "Small or watchlist position only."
        else:
            sizing_view = "Avoid or keep very small until risk/reward improves."

        report = f"""# Position Sizing Decision — {ticker}

- Conviction: {conviction}
- Liquidity: {liquidity}
- Estimated upside: {upside:.1f}%
- Estimated downside: {downside:.1f}%
- Current/proposed weight: {current_weight:.1f}%
- Reward/risk: {'N/A' if reward_risk is None else f'{reward_risk:.2f}x'}

## Sizing View

{sizing_view}

## Risk Controls

- Confirm thesis validity before increasing position.
- Set kill criteria before trade approval.
- Review sector concentration and correlation with existing holdings.
- Reassess after earnings, guidance changes or valuation moves.
"""

        saved_path = save_module_output("Position Sizing", ticker, report)
        st.success(f"Position sizing report saved: {saved_path.name}")
        st.markdown(report)


def render_ic_memo_module():
    st.markdown("#### Investment Committee Memo")
    st.caption("Generate a structured IC memo from thesis, valuation and risks.")

    ticker = st.text_input("Ticker", key="module_ic_ticker").upper().strip()
    recommendation = st.selectbox(
        "Recommendation",
        ["Buy", "Add", "Hold", "Reduce", "Avoid", "Watchlist"],
        key="module_ic_recommendation",
    )
    thesis = st.text_area("Investment thesis", height=120, key="module_ic_thesis")
    valuation = st.text_area("Valuation summary", height=100, key="module_ic_valuation")
    risks = st.text_area("Key risks", height=100, key="module_ic_risks")

    if st.button("Generate IC Memo", use_container_width=True, key="run_ic_memo"):
        if not ticker:
            st.warning("Enter a ticker first.")
            return

        report = f"""# Investment Committee Memo — {ticker}

**Recommendation:** {recommendation}

## 1. Investment Thesis

{thesis if thesis.strip() else "No thesis supplied."}

## 2. Valuation

{valuation if valuation.strip() else "No valuation summary supplied."}

## 3. Key Risks

{risks if risks.strip() else "No risk summary supplied."}

## 4. Decision Framework

- Is the upside/downside attractive?
- Is the thesis supported by evidence?
- Are risks understood and sized appropriately?
- Are kill criteria defined?
- Is the proposed position size justified?

## 5. Required Follow-Up

- Run Red Flag Scanner.
- Run Moat Audit.
- Run Bull vs Bear Pressure Test.
- Confirm valuation output in Valuation.
"""

        saved_path = save_module_output("IC Memo", ticker, report)
        st.success(f"IC memo saved: {saved_path.name}")
        st.markdown(report)


def render_research_pack_module():
    st.markdown("#### Export Research Pack")
    st.caption("Combine recent saved research outputs into one markdown research pack.")

    if st.button("Build Research Pack", use_container_width=True, key="run_research_pack"):
        recent_reports = collect_recent_reports(limit=10)

        report = "# Fordsworth Research Pack\n\n"

        if not recent_reports:
            report += "No recent reports available.\n"
        else:
            for row in recent_reports:
                report += f"## {row['Agent']} — {row['File Name']}\n\n"
                try:
                    report += preview_report(row["Path Object"], max_chars=1500)
                except Exception:
                    report += "Could not read report preview."
                report += "\n\n---\n\n"

        saved_path = save_markdown_report(
            report_type="deep_research",
            title="Fordsworth Research Pack",
            content=report,
        )
        st.success(f"Research pack saved: {saved_path.name}")
        st.markdown(report)


def render_missing_analyst_modules():
    """
    Professional analyst module center.
    Modules are grouped by institutional workflow category to avoid scattered tools.
    """
    st.subheader("Analyst Modules")
    st.caption("Structured institutional analyst workflows inside Research.")

    category_tabs = st.tabs(
        [
            "Screening",
            "Risk Review",
            "Earnings & Moat",
            "Thesis Testing",
            "Portfolio Decision",
            "IC & Export",
        ]
    )

    with category_tabs[0]:
        st.markdown("### Screening")
        st.write("Use this first when reviewing a universe of stocks or narrowing a watchlist.")
        render_institutional_screener_module()

    with category_tabs[1]:
        st.markdown("### Risk Review")
        st.write("Use this before adding, increasing or defending a position.")
        render_red_flag_module()

    with category_tabs[2]:
        st.markdown("### Earnings & Moat")
        st.write("Decode company updates and test whether the business has durable competitive advantages.")

        sub_col1, sub_col2 = st.columns(2)

        with sub_col1:
            with st.container(border=True):
                render_earnings_decode_module()

        with sub_col2:
            with st.container(border=True):
                render_moat_audit_module()

    with category_tabs[3]:
        st.markdown("### Thesis Testing")
        st.write("Pressure-test the thesis before capital allocation or investment committee review.")
        render_bull_bear_module()

    with category_tabs[4]:
        st.markdown("### Portfolio Decision")
        st.write("Translate conviction, upside/downside and liquidity into a position-size recommendation.")
        render_position_sizing_module()

    with category_tabs[5]:
        st.markdown("### IC & Export")
        st.write("Prepare investment committee material and export a combined research pack.")

        ic_tab, pack_tab = st.tabs(["IC Memo", "Research Pack"])

        with ic_tab:
            render_ic_memo_module()

        with pack_tab:
            render_research_pack_module()



# ============================================================
# PROFESSIONAL RESEARCH COMMAND CENTER
# ============================================================

def get_research_target_ticker():
    """
    Default target ticker for research workflows.
    """
    return get_active_company_ticker("NVDA")



# ============================================================
# INSTITUTIONAL SCREENER 2.0
# ============================================================

INSTITUTIONAL_SCREENER_UNIVERSE = [
    {"Ticker": "NVDA", "Company": "Nvidia", "Sector": "Technology", "Theme": "AI semiconductors"},
    {"Ticker": "MSFT", "Company": "Microsoft", "Sector": "Technology", "Theme": "Cloud and enterprise AI"},
    {"Ticker": "AAPL", "Company": "Apple", "Sector": "Technology", "Theme": "Consumer ecosystem"},
    {"Ticker": "GOOGL", "Company": "Alphabet", "Sector": "Communication Services", "Theme": "Search, cloud and AI"},
    {"Ticker": "AMZN", "Company": "Amazon", "Sector": "Consumer Discretionary", "Theme": "E-commerce and AWS"},
    {"Ticker": "META", "Company": "Meta Platforms", "Sector": "Communication Services", "Theme": "Digital ads and AI"},
    {"Ticker": "JPM", "Company": "JPMorgan", "Sector": "Financials", "Theme": "Banking and credit cycle"},
    {"Ticker": "BAC", "Company": "Bank of America", "Sector": "Financials", "Theme": "Banking and rates"},
    {"Ticker": "GS", "Company": "Goldman Sachs", "Sector": "Financials", "Theme": "Capital markets"},
    {"Ticker": "XOM", "Company": "Exxon Mobil", "Sector": "Energy", "Theme": "Oil and energy beta"},
    {"Ticker": "CVX", "Company": "Chevron", "Sector": "Energy", "Theme": "Integrated energy"},
    {"Ticker": "UNH", "Company": "UnitedHealth", "Sector": "Healthcare", "Theme": "Managed care"},
    {"Ticker": "LLY", "Company": "Eli Lilly", "Sector": "Healthcare", "Theme": "Pharma growth"},
    {"Ticker": "TSLA", "Company": "Tesla", "Sector": "Consumer Discretionary", "Theme": "EV and autonomy"},
    {"Ticker": "COST", "Company": "Costco", "Sector": "Consumer Staples", "Theme": "Quality compounder"},
    {"Ticker": "WMT", "Company": "Walmart", "Sector": "Consumer Staples", "Theme": "Defensive retail"},
    {"Ticker": "HD", "Company": "Home Depot", "Sector": "Consumer Discretionary", "Theme": "Housing and consumer"},
    {"Ticker": "CAT", "Company": "Caterpillar", "Sector": "Industrials", "Theme": "Industrial cycle"},
    {"Ticker": "GE", "Company": "GE Aerospace", "Sector": "Industrials", "Theme": "Aerospace"},
    {"Ticker": "NEE", "Company": "NextEra Energy", "Sector": "Utilities", "Theme": "Utilities and renewables"},
]


@st.cache_data(ttl=900)
def fetch_screener_snapshot(ticker: str) -> dict:
    """
    Fetch stock data for screener.
    """
    try:
        snapshot = fetch_stock_snapshot(ticker)
        history = yf.Ticker(ticker).history(period="3mo", interval="1d")

        one_month_momentum = None
        three_month_momentum = None

        if not history.empty and "Close" in history.columns:
            closes = history["Close"].dropna()
            latest = float(closes.iloc[-1]) if len(closes) else None

            if latest and len(closes) >= 22:
                one_month_momentum = ((latest / float(closes.iloc[-22])) - 1) * 100

            if latest and len(closes) >= 60:
                three_month_momentum = ((latest / float(closes.iloc[0])) - 1) * 100

        snapshot["one_month_momentum"] = one_month_momentum
        snapshot["three_month_momentum"] = three_month_momentum
        return snapshot

    except Exception as exc:
        return {"error": str(exc)}


def score_valuation(forward_pe):
    """
    Lower P/E generally scores better, but zero/missing is neutral-low.
    """
    pe = safe_float(forward_pe, 0)

    if pe <= 0:
        return 45
    if pe < 15:
        return 90
    if pe < 25:
        return 75
    if pe < 40:
        return 55
    if pe < 60:
        return 35
    return 20


def score_momentum(one_month_momentum, three_month_momentum):
    one = safe_float(one_month_momentum, 0)
    three = safe_float(three_month_momentum, 0)

    score = 50

    if one > 5:
        score += 20
    elif one > 0:
        score += 10
    elif one < -10:
        score -= 20
    elif one < 0:
        score -= 10

    if three > 12:
        score += 20
    elif three > 0:
        score += 10
    elif three < -15:
        score -= 20
    elif three < 0:
        score -= 10

    return max(min(score, 100), 0)


def score_risk(beta):
    b = safe_float(beta, 1)

    if b <= 0:
        return 50
    if b < 0.8:
        return 85
    if b < 1.2:
        return 70
    if b < 1.6:
        return 50
    if b < 2.0:
        return 35
    return 20


def score_quality(market_cap, dividend_yield, beta):
    cap = safe_float(market_cap, 0)
    dy = safe_float(dividend_yield, 0)
    b = safe_float(beta, 1)

    score = 45

    if cap > 200_000_000_000:
        score += 25
    elif cap > 50_000_000_000:
        score += 15
    elif cap > 10_000_000_000:
        score += 8

    if dy and dy > 0:
        score += 8

    if b < 1.2:
        score += 12

    return max(min(score, 100), 0)


def classify_screener_rating(total_score):
    if total_score >= 80:
        return "Strong Candidate"
    if total_score >= 65:
        return "Review"
    if total_score >= 50:
        return "Watchlist"
    return "Avoid / Low Priority"


def build_institutional_screener_dataframe(universe: list[dict]) -> pd.DataFrame:
    rows = []

    for item in universe:
        ticker = item["Ticker"]
        snap = fetch_screener_snapshot(ticker)

        latest = snap.get("latest_close")
        market_cap = snap.get("market_cap")
        forward_pe = snap.get("forward_pe")
        beta = snap.get("beta")
        dividend_yield = snap.get("dividend_yield")
        one_month = snap.get("one_month_momentum")
        three_month = snap.get("three_month_momentum")

        valuation_score = score_valuation(forward_pe)
        momentum_score = score_momentum(one_month, three_month)
        risk_score = score_risk(beta)
        quality_score = score_quality(market_cap, dividend_yield, beta)

        total_score = (
            valuation_score * 0.25
            + momentum_score * 0.25
            + quality_score * 0.30
            + risk_score * 0.20
        )

        rows.append(
            {
                "Ticker": ticker,
                "Company": snap.get("company_name", item["Company"]),
                "Sector": snap.get("sector", item["Sector"]) or item["Sector"],
                "Theme": item["Theme"],
                "Latest": latest,
                "Market Cap Raw": market_cap,
                "Market Cap": format_large_number(market_cap),
                "Forward P/E": forward_pe,
                "Beta": beta,
                "Dividend Yield": dividend_yield,
                "1M Momentum": one_month,
                "3M Momentum": three_month,
                "Valuation Score": valuation_score,
                "Momentum Score": momentum_score,
                "Quality Score": quality_score,
                "Risk Score": risk_score,
                "Total Score": round(total_score, 1),
                "Rating": classify_screener_rating(total_score),
            }
        )

    return pd.DataFrame(rows)


def render_institutional_screener_2():
    """
    Institutional Screener 2.0 with professional filters, scoring and actions.
    """
    st.markdown(
        """
        <div class="screener-terminal-hero">
            <div class="screener-terminal-title">Institutional Screener 2.0</div>
            <p class="screener-terminal-text">
                Screen a professional equity universe using valuation, momentum, quality and risk scores.
                Use the output to select a company for Finance, Research, Valuation or Reports.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = build_institutional_screener_dataframe(INSTITUTIONAL_SCREENER_UNIVERSE)

    st.markdown(
        """
        <div class="screener-methodology-box">
            <div class="screener-methodology-title">Scoring methodology</div>
            <div class="screener-methodology-text">
                Total Score = 25% Valuation + 25% Momentum + 30% Quality + 20% Risk.
                This is a screening framework, not a final investment recommendation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        sector_filter = st.selectbox(
            "Sector",
            ["All"] + sorted(df["Sector"].dropna().unique().tolist()),
            key="screener2_sector_filter",
        )

    with c2:
        rating_filter = st.selectbox(
            "Rating",
            ["All", "Strong Candidate", "Review", "Watchlist", "Avoid / Low Priority"],
            key="screener2_rating_filter",
        )

    with c3:
        min_score = st.slider(
            "Minimum score",
            min_value=0,
            max_value=100,
            value=50,
            key="screener2_min_score",
        )

    with c4:
        max_forward_pe = st.number_input(
            "Max Forward P/E",
            value=80.0,
            step=5.0,
            key="screener2_max_pe",
        )

    search = st.text_input(
        "Search ticker, company or theme",
        placeholder="Example: AI, bank, energy, AAPL",
        key="screener2_search",
    ).strip().lower()

    filtered = df.copy()

    if sector_filter != "All":
        filtered = filtered[filtered["Sector"] == sector_filter]

    if rating_filter != "All":
        filtered = filtered[filtered["Rating"] == rating_filter]

    filtered = filtered[filtered["Total Score"] >= min_score]

    filtered = filtered[
        filtered["Forward P/E"].fillna(9999).apply(lambda x: safe_float(x, 9999)) <= max_forward_pe
    ]

    if search:
        filtered = filtered[
            filtered["Ticker"].str.lower().str.contains(search, na=False)
            | filtered["Company"].str.lower().str.contains(search, na=False)
            | filtered["Theme"].str.lower().str.contains(search, na=False)
        ]

    filtered = filtered.sort_values("Total Score", ascending=False)

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.markdown(
            f"""
            <div class="screener-score-card">
                <div class="screener-score-label">Universe</div>
                <div class="screener-score-value">{len(df)}</div>
                <div class="screener-score-note">Stocks screened.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s2:
        st.markdown(
            f"""
            <div class="screener-score-card">
                <div class="screener-score-label">Filtered</div>
                <div class="screener-score-value">{len(filtered)}</div>
                <div class="screener-score-note">Stocks matching filters.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s3:
        top_name = filtered.iloc[0]["Ticker"] if not filtered.empty else "N/A"
        st.markdown(
            f"""
            <div class="screener-score-card">
                <div class="screener-score-label">Top Candidate</div>
                <div class="screener-score-value">{top_name}</div>
                <div class="screener-score-note">Highest filtered score.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s4:
        avg_score = filtered["Total Score"].mean() if not filtered.empty else 0
        st.markdown(
            f"""
            <div class="screener-score-card">
                <div class="screener-score-label">Average Score</div>
                <div class="screener-score-value">{avg_score:.1f}</div>
                <div class="screener-score-note">Filtered universe.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    display_cols = [
        "Ticker",
        "Company",
        "Sector",
        "Theme",
        "Market Cap",
        "Forward P/E",
        "Beta",
        "1M Momentum",
        "3M Momentum",
        "Valuation Score",
        "Momentum Score",
        "Quality Score",
        "Risk Score",
        "Total Score",
        "Rating",
    ]

    display_df = filtered[display_cols].copy()

    for col in ["Forward P/E", "Beta", "1M Momentum", "3M Momentum"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda x: "N/A" if pd.isna(x) else f"{safe_float(x):,.2f}")

    display_df = make_dataframe_arrow_safe(display_df)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("### Screener Actions")

    if filtered.empty:
        st.info("No companies match the current filters.")
        return

    selected_ticker = st.selectbox(
        "Select company",
        filtered["Ticker"].tolist(),
        key="screener2_selected_ticker",
    )

    selected_company = filtered.loc[filtered["Ticker"] == selected_ticker, "Company"].iloc[0]
    set_active_company(selected_ticker, selected_company)

    a1, a2, a3, a4, a5 = st.columns(5)

    with a1:
        if st.button("Open Finance", use_container_width=True, key="screener2_open_finance"):
            st.query_params["view"] = "Finance"
            st.rerun()

    with a2:
        if st.button("Open Research", use_container_width=True, key="screener2_open_research"):
            st.query_params["view"] = "Research"
            st.rerun()

    with a3:
        if st.button("Open Valuation", use_container_width=True, key="screener2_open_valuation"):
            st.query_params["view"] = "Valuation"
            st.rerun()

    with a4:
        if st.button("Open Risk", use_container_width=True, key="screener2_open_risk"):
            st.query_params["view"] = "Risk"
            st.rerun()

    with a5:
        if st.button("Build Pack", use_container_width=True, key="screener2_open_reports"):
            st.query_params["view"] = "Reports"
            st.rerun()


def render_research_command_overview():
    """
    Research overview with workflow status and recommended sequence.
    """
    render_active_company_shortcuts("research_overview")

    st.markdown(
        """
        <div class="research-command-hero">
            <div class="research-command-title">Research Command Center</div>
            <p class="research-command-text">
                Generate market briefings, company research, risk reviews, thesis tests, IC memos and exportable research packs.
                Use this function after Home, Markets and Finance to turn information into analyst output.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    latest_reports = collect_recent_reports(limit=50)

    try:
        total_reports = count_total_reports()
    except Exception:
        total_reports = len(latest_reports)

    research_types = {
        "Briefings": ["Morning Analyst", "Market Curator", "Event Calendar"],
        "Company Research": ["Deep Research", "Earnings", "Moat"],
        "Risk Review": ["Red Flag", "Risk"],
        "IC / Export": ["IC", "Research Pack", "Valuation"],
    }

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="research-status-card">
                <div class="research-status-label">Saved Reports</div>
                <div class="research-status-value">{total_reports}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="research-status-card">
                <div class="research-status-label">Target Ticker</div>
                <div class="research-status-value">{get_research_target_ticker()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="research-status-card">
                <div class="research-status-label">Workflows</div>
                <div class="research-status-value">6</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="research-status-card">
                <div class="research-status-label">Automation</div>
                <div class="research-status-value">{'On' if bool(st.session_state.get('portfolio_scheduler') and st.session_state.get('portfolio_scheduler').running) else 'Off'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Recommended Analyst Workflow")

    workflow_rows = [
        {"Step": "1", "Workflow": "Daily Briefing", "Output": "Morning Analyst + Market Curator + Event Calendar", "Purpose": "Understand market context and upcoming catalysts."},
        {"Step": "2", "Workflow": "Company Research", "Output": "Deep Research + Earnings Decode + Moat Audit", "Purpose": "Understand the company, business quality and recent updates."},
        {"Step": "3", "Workflow": "Risk & Red Flags", "Output": "Red Flag Scanner", "Purpose": "Identify valuation, leverage, governance, margin and cash-flow concerns."},
        {"Step": "4", "Workflow": "Thesis Testing", "Output": "Bull vs Bear + Position Sizing", "Purpose": "Pressure-test risk/reward and position size."},
        {"Step": "5", "Workflow": "IC Memo", "Output": "Investment Committee Memo", "Purpose": "Prepare decision material."},
        {"Step": "6", "Workflow": "Research Pack", "Output": "Combined research pack", "Purpose": "Archive and export complete analysis."},
    ]

    workflow_df = pd.DataFrame(workflow_rows)
    workflow_df = make_dataframe_arrow_safe(workflow_df)
    st.dataframe(workflow_df, use_container_width=True, hide_index=True)

    st.markdown("### Recent Research Activity")

    recent_reports = collect_recent_reports(limit=8)

    if not recent_reports:
        st.info("No research reports generated yet.")
    else:
        feed_df = pd.DataFrame(
            [
                {
                    "Source": row["Agent"],
                    "Report": row["File Name"],
                    "Modified": pd.to_datetime(row["Modified"], unit="s").strftime("%Y-%m-%d %H:%M:%S"),
                }
                for row in recent_reports
            ]
        )
        feed_df = make_dataframe_arrow_safe(feed_df)
        st.dataframe(feed_df, use_container_width=True, hide_index=True)


def render_daily_briefing_workflow():
    """
    Daily briefing workflow: Morning Analyst, Market Curator and Event Calendar.
    """
    st.markdown("### Daily Briefing")
    st.caption("Run market and portfolio briefing workflows.")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Run Morning Analyst", use_container_width=True, key="command_morning_analyst"):
            with st.spinner("Generating Morning Analyst briefing..."):
                report = run_morning_analyst()
            st.success("Morning Analyst report generated.")
            with st.expander("Open report", expanded=True):
                st.markdown(report)

    with c2:
        if st.button("Run Market Curator", use_container_width=True, key="command_market_curator"):
            with st.spinner("Generating Market Curator report..."):
                report = run_market_curator()
            st.success("Market Curator report generated.")
            with st.expander("Open report", expanded=True):
                st.markdown(report)

    with c3:
        if st.button("Run Event Calendar", use_container_width=True, key="command_event_calendar"):
            with st.spinner("Generating Event Calendar..."):
                report = run_event_calendar()
            st.success("Event Calendar report generated.")
            with st.expander("Open report", expanded=True):
                st.markdown(report)

    st.divider()

    st.markdown("### Briefing Purpose")
    st.write("- Start here every morning.")
    st.write("- Use this before opening Markets or Finance.")
    st.write("- Use Market Curator to reduce news noise.")
    st.write("- Use Event Calendar to identify catalysts.")


def render_company_research_workflow():
    """
    Company research workflow: target ticker, deep research, earnings decode and moat audit.
    """
    st.markdown("### Company Research")
    st.caption("Generate company-specific research outputs.")

    ticker = st.text_input(
        "Target ticker",
        value=get_research_target_ticker(),
        placeholder="Example: AAPL, MSFT, NVDA",
        key="research_company_target_ticker",
    ).upper().strip()

    if ticker:
        set_active_company(ticker)

    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("#### Deep Research")

        if st.button("Run Deep Research Memo", use_container_width=True, key="command_deep_research"):
            if not ticker:
                st.warning("Enter a ticker first.")
            else:
                with st.spinner(f"Generating Deep Research memo for {ticker}..."):
                    report = run_deep_digger(ticker)
                st.success("Deep Research memo generated.")
                with st.expander("Open memo", expanded=True):
                    st.markdown(report)

    with c2:
        st.markdown("#### Company Analysis Shortcuts")

        if st.button("Open Finance", use_container_width=True, key="command_open_finance"):
            st.session_state["home_selected_ticker"] = ticker
            st.query_params["view"] = "Finance"
            st.rerun()

        if st.button("Open Valuation", use_container_width=True, key="command_open_valuation"):
            st.session_state["home_selected_ticker"] = ticker
            st.query_params["view"] = "Valuation"
            st.rerun()

    st.divider()

    research_subtabs = st.tabs(["Earnings Decode", "Moat Audit"])

    with research_subtabs[0]:
        render_earnings_decode_module()

    with research_subtabs[1]:
        render_moat_audit_module()


def render_risk_red_flags_workflow():
    """
    Risk and red flags workflow.
    """
    st.markdown("### Risk & Red Flags")
    st.caption("Identify company-specific risks before investment decision.")

    render_red_flag_module()

    st.divider()

    st.markdown("### Risk Review Checklist")

    checklist_df = pd.DataFrame(
        [
            {"Area": "Valuation", "Question": "Is the multiple stretched relative to growth and quality?"},
            {"Area": "Leverage", "Question": "Is debt, refinancing or interest cost a material risk?"},
            {"Area": "Margins", "Question": "Are margins deteriorating or unusually elevated?"},
            {"Area": "Cash Flow", "Question": "Are earnings converting into cash?"},
            {"Area": "Governance", "Question": "Any accounting, governance or related-party concerns?"},
            {"Area": "Competition", "Question": "Is the company losing competitive advantage?"},
        ]
    )
    checklist_df = make_dataframe_arrow_safe(checklist_df)
    st.dataframe(checklist_df, use_container_width=True, hide_index=True)


def render_thesis_testing_workflow():
    """
    Bull vs bear and position sizing.
    """
    st.markdown("### Thesis Testing")
    st.caption("Pressure-test the investment thesis and position size.")

    thesis_tab, sizing_tab = st.tabs(["Bull vs Bear", "Position Sizing"])

    with thesis_tab:
        render_bull_bear_module()

    with sizing_tab:
        render_position_sizing_module()


def render_ic_memo_workflow():
    """
    IC memo workflow.
    """
    st.markdown("### IC Memo")
    st.caption("Generate investment committee material from thesis, valuation and risks.")
    render_ic_memo_module()


def render_research_pack_workflow():
    """
    Research pack workflow and automation.
    """
    st.markdown("### Research Pack")
    st.caption("Combine saved outputs into a research pack.")

    render_research_pack_module()

    st.divider()

    st.markdown("### Research Automation")

    scheduler = st.session_state.get("portfolio_scheduler")
    scheduler_running = bool(scheduler and scheduler.running)
    jobs = get_scheduler_jobs()

    a1, a2 = st.columns(2)

    with a1:
        st.metric("Automation Status", "Running" if scheduler_running else "Stopped")

    with a2:
        st.metric("Scheduled Jobs", len(jobs))

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Start Automation", use_container_width=True, key="command_start_automation"):
            get_or_start_scheduler()
            st.success("Research automation started.")

    with c2:
        if st.button("Stop Automation", use_container_width=True, key="command_stop_automation"):
            stop_scheduler()
            st.warning("Research automation stopped.")

    if jobs:
        job_rows = []

        for job in jobs:
            job_rows.append(
                {
                    "Job ID": job.id,
                    "Next Run": str(job.next_run_time),
                    "Trigger": str(job.trigger),
                }
            )

        jobs_df = pd.DataFrame(job_rows)
        jobs_df = make_dataframe_arrow_safe(jobs_df)
        st.dataframe(jobs_df, use_container_width=True, hide_index=True)


def render_agents_view():
    """
    Research page: professional Research Command Center.
    """
    st.subheader("Research")
    st.caption("Daily briefing, institutional screener, company research, red flags, thesis testing, IC memo and research pack.")

    research_tabs = st.tabs(
        [
            "Overview",
            "Institutional Screener",
            "Daily Briefing",
            "Company Research",
            "Risk & Red Flags",
            "Thesis Testing",
            "IC Memo",
            "Research Pack",
        ]
    )

    with research_tabs[0]:
        render_research_command_overview()

    with research_tabs[1]:
        render_institutional_screener_2()

    with research_tabs[2]:
        render_daily_briefing_workflow()

    with research_tabs[3]:
        render_company_research_workflow()

    with research_tabs[4]:
        render_risk_red_flags_workflow()

    with research_tabs[5]:
        render_thesis_testing_workflow()

    with research_tabs[6]:
        render_ic_memo_workflow()

    with research_tabs[7]:
        render_research_pack_workflow()




# ============================================================
# INVESTMENT OUTPUT CENTER FALLBACK HELPERS
# ============================================================

INVESTMENT_OUTPUT_SOURCES = {
    "Morning Briefings": "morning_briefs",
    "Market Curator": "market_curator",
    "Thesis Reviews": "thesis_reviews",
    "Event Calendars": "weekly_calendars",
    "Deep Research / Analyst Modules": "deep_research",
    "Valuation Reports": "valuation_reports",
}


def get_report_count_safe(report_type: str) -> int:
    try:
        return len(list_reports(report_type))
    except Exception:
        return 0


def get_latest_report_safe(report_type: str):
    try:
        return get_latest_report(report_type)
    except Exception:
        try:
            reports = list_reports(report_type)
            return reports[0] if reports else None
        except Exception:
            return None


def read_report_safe(path_obj):
    if not path_obj:
        return ""
    try:
        return read_report(path_obj)
    except Exception:
        try:
            return Path(path_obj).read_text(encoding="utf-8")
        except Exception:
            return ""


def collect_output_center_summary():
    rows = []
    for label, report_type in INVESTMENT_OUTPUT_SOURCES.items():
        latest = get_latest_report_safe(report_type)
        count = get_report_count_safe(report_type)
        if latest:
            try:
                modified = pd.to_datetime(latest.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S")
                latest_file = latest.name
            except Exception:
                modified = "N/A"
                latest_file = str(latest)
        else:
            modified = "N/A"
            latest_file = "No report"
        rows.append({"Output Type": label, "Reports": count, "Latest File": latest_file, "Modified": modified})
    return pd.DataFrame(rows)


def build_latest_outputs_table():
    rows = []
    for label, report_type in INVESTMENT_OUTPUT_SOURCES.items():
        latest = get_latest_report_safe(report_type)
        if latest:
            try:
                modified = pd.to_datetime(latest.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S")
                file_name = latest.name
            except Exception:
                modified = "N/A"
                file_name = str(latest)
            rows.append({"Output Type": label, "File": file_name, "Modified": modified, "Path Object": latest})
    return rows


def render_output_center_overview():
    st.markdown("### Investment Output Center")
    st.caption("Review saved outputs, archives, investment packs and export readiness.")
    summary_df = collect_output_center_summary()
    total_outputs = int(summary_df["Reports"].sum()) if not summary_df.empty else 0
    valuation_count = get_report_count_safe("valuation_reports")
    research_count = get_report_count_safe("deep_research")
    latest_sources = len(build_latest_outputs_table())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Saved Outputs", total_outputs)
    with c2:
        st.metric("Research Outputs", research_count)
    with c3:
        st.metric("Valuation Outputs", valuation_count)
    with c4:
        st.metric("Latest Sources", latest_sources)
    st.markdown("### Output Inventory")
    summary_df = make_dataframe_arrow_safe(summary_df)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


def render_latest_outputs_center():
    st.markdown("### Latest Research Outputs")
    rows = build_latest_outputs_table()
    if not rows:
        st.info("No saved outputs found yet. Generate outputs from Research, Valuation or Risk first.")
        return
    display_df = pd.DataFrame([{"Output Type": r["Output Type"], "File": r["File"], "Modified": r["Modified"]} for r in rows])
    display_df = make_dataframe_arrow_safe(display_df)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    selected_file = st.selectbox("Open latest output", [r["File"] for r in rows], key="latest_output_open_select_fallback")
    selected_row = next(r for r in rows if r["File"] == selected_file)
    with st.expander("Open selected output", expanded=True):
        st.markdown(read_report_safe(selected_row["Path Object"]) or "Could not read selected output.")


def render_report_archive_center():
    st.markdown("### Report Archive")
    archive_type = st.selectbox("Archive type", list(INVESTMENT_OUTPUT_SOURCES.keys()), key="archive_type_select_fallback")
    report_type = INVESTMENT_OUTPUT_SOURCES[archive_type]
    try:
        reports = list_reports(report_type)
    except Exception:
        reports = []
    if not reports:
        st.info("No reports found for this archive type.")
        return
    archive_rows = []
    for p in reports[:50]:
        try:
            modified = pd.to_datetime(p.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S")
            name = p.name
        except Exception:
            modified = "N/A"
            name = str(p)
        archive_rows.append({"File": name, "Modified": modified, "Path Object": p})
    archive_df = pd.DataFrame([{"File": r["File"], "Modified": r["Modified"]} for r in archive_rows])
    archive_df = make_dataframe_arrow_safe(archive_df)
    st.dataframe(archive_df, use_container_width=True, hide_index=True)
    selected = st.selectbox("Open archived report", [r["File"] for r in archive_rows], key="archive_open_report_select_fallback")
    selected_row = next(r for r in archive_rows if r["File"] == selected)
    with st.expander("Open archived report", expanded=False):
        st.markdown(read_report_safe(selected_row["Path Object"]))


def build_investment_pack_content(selected_report_types: list[str], pack_title: str, ticker: str = "") -> str:
    report = f"# {pack_title}\n\n"
    if ticker:
        report += f"**Target ticker / company:** {ticker}\n\n"
    report += "## Pack Contents\n\n"
    for label, report_type in INVESTMENT_OUTPUT_SOURCES.items():
        if report_type in selected_report_types:
            report += f"- {label}\n"
    report += "\n---\n\n"
    included_any = False
    for label, report_type in INVESTMENT_OUTPUT_SOURCES.items():
        if report_type not in selected_report_types:
            continue
        latest = get_latest_report_safe(report_type)
        content = read_report_safe(latest)
        report += f"# {label}\n\n"
        if latest is None or not content:
            report += "No saved output available for this section.\n\n"
        else:
            included_any = True
            try:
                report += f"**Source file:** {latest.name}\n\n"
            except Exception:
                report += f"**Source file:** {latest}\n\n"
            report += content + "\n\n---\n\n"
    if not included_any:
        report += "No saved reports were available. Generate Research, Valuation or Risk outputs first.\n"
    report += "\n# Analyst Final Checklist\n\n- Confirm the investment thesis is clear.\n- Confirm risks are documented.\n- Confirm valuation assumptions are reasonable.\n- Confirm position size aligns with conviction.\n"
    return report


def render_investment_pack_builder():
    st.markdown("### Build Investment Pack")
    st.caption("Combine latest saved outputs into one investment pack.")
    ticker = st.text_input("Target ticker / company", value=st.session_state.get("active_company_ticker", st.session_state.get("home_selected_ticker", "NVDA")), key="pack_builder_ticker_fallback").upper().strip()
    selected_labels = st.multiselect("Select sections to include", list(INVESTMENT_OUTPUT_SOURCES.keys()), default=["Deep Research / Analyst Modules", "Valuation Reports"], key="pack_builder_sections_fallback")
    selected_report_types = [INVESTMENT_OUTPUT_SOURCES[label] for label in selected_labels]
    pack_title = st.text_input("Pack title", value=f"Investment Pack {ticker}" if ticker else "Investment Pack", key="pack_builder_title_fallback")
    pack_content = build_investment_pack_content(selected_report_types, pack_title, ticker)
    with st.expander("Preview investment pack", expanded=False):
        st.markdown(pack_content)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Save Investment Pack", use_container_width=True, key="save_investment_pack_fallback"):
            saved_path = save_markdown_report(report_type="deep_research", title=pack_title, content=pack_content)
            st.success(f"Investment pack saved: {Path(saved_path).name}")
    with c2:
        if st.button("Export Pack to Word", use_container_width=True, key="export_pack_word_fallback"):
            export_dir = Path("exports"); export_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", pack_title).strip("_")
            word_path = export_dir / f"{safe_name}.docx"
            try:
                export_markdown_to_word_file(pack_content, pack_title, word_path)
                render_file_download(word_path, "Download Word Investment Pack", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as exc:
                st.error(f"Word export failed: {exc}")
    with c3:
        if st.button("Export Pack to PDF", use_container_width=True, key="export_pack_pdf_fallback"):
            export_dir = Path("exports"); export_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", pack_title).strip("_")
            pdf_path = export_dir / f"{safe_name}.pdf"
            try:
                export_markdown_to_simple_pdf_file(pack_content, pack_title, pdf_path)
                render_file_download(pdf_path, "Download PDF Investment Pack", "application/pdf")
            except Exception as exc:
                st.error(f"PDF export failed: {exc}")


def render_reports_view():
    """
    Reports page: Investment Output Center.
    """
    st.subheader("Reports")
    st.caption("Latest outputs, archives, investment pack builder and Word/PDF export center.")

    reports_tabs = st.tabs(
        [
            "Overview",
            "Health Check",
            "Latest Outputs",
            "Report Archive",
            "Investment Pack",
            "Export Center",
            "Stock Tear Sheet Export",
        ]
    )

    with reports_tabs[0]:
        render_output_center_overview()

    with reports_tabs[1]:
        render_terminal_health_check()

    with reports_tabs[2]:
        render_latest_outputs_center()

    with reports_tabs[3]:
        render_report_archive_center()

    with reports_tabs[4]:
        render_investment_pack_builder()

    with reports_tabs[5]:
        render_export_center()

    with reports_tabs[6]:
        render_stock_tear_sheet_export()



def render_portfolio_view():
    st.subheader("Portfolio Thesis Library")
    if not positions:
        st.info("No portfolio YAML files found. Add positions in Portfolio Editor.")
        return
    table_rows = []
    for position in positions:
        thesis = position.get("investment_thesis", {})
        valuation = position.get("valuation", {})
        monitoring = position.get("monitoring", {})
        table_rows.append({"Ticker": position.get("ticker"), "Company": position.get("company_name"), "Sector": position.get("sector"), "Status": position.get("position_status"), "Weight %": position.get("portfolio_weight"), "Fair Value": valuation.get("fair_value"), "Priority": monitoring.get("overnight_news_priority"), "Drivers": len(thesis.get("core_drivers", [])), "Kill Criteria": len(thesis.get("kill_criteria", []))})
    portfolio_df = pd.DataFrame(table_rows)
    if "Weight %" in portfolio_df.columns:
        portfolio_df["Weight %"] = pd.to_numeric(portfolio_df["Weight %"], errors="coerce").fillna(0)
        portfolio_df = portfolio_df.sort_values("Weight %", ascending=False)
    st.dataframe(make_dataframe_arrow_safe(portfolio_df), use_container_width=True, hide_index=True)



# ============================================================
# PROFESSIONAL RISK TERMINAL
# ============================================================

def get_portfolio_positions_safe():
    """
    Build a safe list of positions from the portfolio service/data available in the app.
    Falls back to a sample-style portfolio if no positions are available.
    """
    positions = []

    try:
        raw_positions = portfolio_summary().get("positions", [])
        if raw_positions:
            positions = raw_positions
    except Exception:
        positions = []

    if not positions:
        try:
            if "portfolio" in globals() and isinstance(portfolio, dict):
                positions = portfolio.get("positions", [])
        except Exception:
            positions = []

    # Last fallback so Risk page is never empty.
    if not positions:
        positions = [
            {
                "ticker": "NVDA",
                "company_name": "Nvidia",
                "weight": 6.0,
                "sector": "Technology",
                "investment_thesis": {
                    "one_line": "AI infrastructure leader with strong growth optionality.",
                    "core_drivers": ["AI demand", "GPU leadership", "data center growth"],
                    "kill_criteria": ["AI demand slows materially", "margins compress sharply"],
                },
                "valuation": {"fair_value": 950, "bear_case": 650, "bull_case": 1200},
            },
            {
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "weight": 5.5,
                "sector": "Technology",
                "investment_thesis": {
                    "one_line": "Enterprise software and cloud leader with AI monetisation optionality.",
                    "core_drivers": ["Azure growth", "AI monetisation", "enterprise moat"],
                    "kill_criteria": ["Azure growth decelerates", "AI capex returns disappoint"],
                },
                "valuation": {"fair_value": 480, "bear_case": 360, "bull_case": 600},
            },
            {
                "ticker": "AAPL",
                "company_name": "Apple",
                "weight": 4.5,
                "sector": "Technology",
                "investment_thesis": {
                    "one_line": "High-quality consumer ecosystem with services growth.",
                    "core_drivers": ["services growth", "ecosystem retention"],
                    "kill_criteria": ["iPhone cycle weakens materially"],
                },
                "valuation": {"fair_value": 210, "bear_case": 160, "bull_case": 260},
            },
            {
                "ticker": "JPM",
                "company_name": "JPMorgan",
                "weight": 3.5,
                "sector": "Financials",
                "investment_thesis": {
                    "one_line": "High-quality bank with scale and through-cycle resilience.",
                    "core_drivers": ["credit discipline", "scale", "capital markets"],
                    "kill_criteria": ["credit losses increase materially"],
                },
                "valuation": {"fair_value": 230, "bear_case": 175, "bull_case": 280},
            },
        ]

    return positions


def normalise_position_row(position: dict) -> dict:
    ticker = position.get("ticker") or position.get("Ticker") or position.get("symbol") or "N/A"
    company = position.get("company_name") or position.get("Company") or ticker
    sector = position.get("sector") or position.get("Sector") or "Unclassified"
    weight = safe_float(position.get("weight") or position.get("Weight %") or position.get("portfolio_weight"), 0)

    thesis = position.get("investment_thesis", {}) or {}
    valuation = position.get("valuation", {}) or {}

    core_drivers = thesis.get("core_drivers", []) or []
    kill_criteria = thesis.get("kill_criteria", []) or []

    thesis_score = 0
    if thesis.get("one_line"):
        thesis_score += 35
    if core_drivers:
        thesis_score += min(len(core_drivers) * 15, 35)
    if kill_criteria:
        thesis_score += min(len(kill_criteria) * 15, 30)

    thesis_score = min(thesis_score, 100)

    fair_value = safe_float(valuation.get("fair_value"), 0)
    bear_case = safe_float(valuation.get("bear_case"), 0)
    bull_case = safe_float(valuation.get("bull_case"), 0)

    return {
        "Ticker": str(ticker).upper(),
        "Company": company,
        "Sector": sector,
        "Weight %": weight,
        "Thesis Score": thesis_score,
        "Core Drivers": len(core_drivers),
        "Kill Criteria": len(kill_criteria),
        "Fair Value": fair_value,
        "Bear Case": bear_case,
        "Bull Case": bull_case,
    }


def build_risk_position_dataframe() -> pd.DataFrame:
    positions = get_portfolio_positions_safe()
    rows = [normalise_position_row(position) for position in positions]
    return pd.DataFrame(rows)


def calculate_portfolio_risk_summary(risk_df: pd.DataFrame) -> dict:
    if risk_df.empty:
        return {
            "total_positions": 0,
            "total_weight": 0,
            "largest_weight": 0,
            "largest_position": "N/A",
            "largest_sector": "N/A",
            "largest_sector_weight": 0,
            "average_thesis_score": 0,
            "positions_missing_kill": 0,
        }

    total_weight = risk_df["Weight %"].sum()
    largest_idx = risk_df["Weight %"].idxmax()
    largest_position = risk_df.loc[largest_idx, "Ticker"]
    largest_weight = risk_df.loc[largest_idx, "Weight %"]

    sector_df = risk_df.groupby("Sector", as_index=False)["Weight %"].sum().sort_values("Weight %", ascending=False)
    largest_sector = sector_df.iloc[0]["Sector"] if not sector_df.empty else "N/A"
    largest_sector_weight = sector_df.iloc[0]["Weight %"] if not sector_df.empty else 0

    avg_thesis = risk_df["Thesis Score"].mean()
    positions_missing_kill = int((risk_df["Kill Criteria"] == 0).sum())

    return {
        "total_positions": len(risk_df),
        "total_weight": total_weight,
        "largest_weight": largest_weight,
        "largest_position": largest_position,
        "largest_sector": largest_sector,
        "largest_sector_weight": largest_sector_weight,
        "average_thesis_score": avg_thesis,
        "positions_missing_kill": positions_missing_kill,
    }


def classify_concentration_risk(weight: float) -> str:
    if weight >= 10:
        return "High"
    if weight >= 5:
        return "Medium"
    return "Low"


def build_risk_action_plan(risk_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in risk_df.iterrows():
        actions = []

        if row["Weight %"] >= 10:
            actions.append("Review concentration and position cap.")
        elif row["Weight %"] >= 5:
            actions.append("Monitor position size versus conviction.")

        if row["Thesis Score"] < 60:
            actions.append("Strengthen thesis documentation.")

        if row["Kill Criteria"] == 0:
            actions.append("Define kill criteria.")

        if row["Bear Case"] and row["Fair Value"] and row["Bear Case"] < row["Fair Value"] * 0.75:
            actions.append("Review downside protection.")

        if not actions:
            actions.append("No immediate action. Continue monitoring.")

        rows.append(
            {
                "Ticker": row["Ticker"],
                "Risk Level": classify_concentration_risk(row["Weight %"]),
                "Primary Action": " ".join(actions),
            }
        )

    return pd.DataFrame(rows)


def build_risk_report_markdown(risk_df: pd.DataFrame, summary: dict, action_df: pd.DataFrame) -> str:
    report = "# Portfolio Risk Report\n\n"

    report += "## Risk Summary\n\n"
    report += f"- Total positions: {summary['total_positions']}\n"
    report += f"- Total weight: {summary['total_weight']:.2f}%\n"
    report += f"- Largest position: {summary['largest_position']} ({summary['largest_weight']:.2f}%)\n"
    report += f"- Largest sector: {summary['largest_sector']} ({summary['largest_sector_weight']:.2f}%)\n"
    report += f"- Average thesis score: {summary['average_thesis_score']:.2f}\n"
    report += f"- Positions missing kill criteria: {summary['positions_missing_kill']}\n\n"

    report += "## Position Risk Table\n\n"
    report += "| Ticker | Sector | Weight % | Thesis Score | Kill Criteria |\n"
    report += "|---|---|---:|---:|---:|\n"
    for _, row in risk_df.iterrows():
        report += f"| {row['Ticker']} | {row['Sector']} | {row['Weight %']:.2f}% | {row['Thesis Score']:.0f} | {row['Kill Criteria']} |\n"

    report += "\n## Risk Action Plan\n\n"
    report += "| Ticker | Risk Level | Primary Action |\n"
    report += "|---|---|---|\n"
    for _, row in action_df.iterrows():
        report += f"| {row['Ticker']} | {row['Risk Level']} | {row['Primary Action']} |\n"

    report += "\n## Analyst Notes\n\n"
    report += "- Review concentration and sector exposure before increasing positions.\n"
    report += "- Ensure each holding has clear thesis, core drivers and kill criteria.\n"
    report += "- Use valuation downside and bear-case outcomes to assess position sizing discipline.\n"

    return report


def render_professional_risk_terminal():
    """
    Professional portfolio risk terminal.
    """
    render_active_company_shortcuts("risk_terminal")

    st.markdown(
        """
        <div class="risk-terminal-hero">
            <div class="risk-terminal-title">Portfolio Risk Terminal</div>
            <p class="risk-terminal-text">
                Review concentration, sector exposure, thesis completeness, valuation downside,
                kill criteria and risk actions for the portfolio.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    risk_df = build_risk_position_dataframe()
    summary = calculate_portfolio_risk_summary(risk_df)
    action_df = build_risk_action_plan(risk_df)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="risk-score-card">
                <div class="risk-score-label">Positions</div>
                <div class="risk-score-value">{summary['total_positions']}</div>
                <div class="risk-score-note">Number of holdings tracked.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="risk-score-card">
                <div class="risk-score-label">Largest Position</div>
                <div class="risk-score-value">{summary['largest_position']}</div>
                <div class="risk-score-note">{summary['largest_weight']:.2f}% portfolio weight.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="risk-score-card">
                <div class="risk-score-label">Largest Sector</div>
                <div class="risk-score-value">{summary['largest_sector']}</div>
                <div class="risk-score-note">{summary['largest_sector_weight']:.2f}% sector weight.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="risk-score-card">
                <div class="risk-score-label">Avg Thesis Score</div>
                <div class="risk-score-value">{summary['average_thesis_score']:.0f}</div>
                <div class="risk-score-note">Documentation completeness score.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if summary["positions_missing_kill"] > 0:
        st.markdown(
            f"""
            <div class="risk-warning-card">
                {summary['positions_missing_kill']} position(s) have no kill criteria. Define exit triggers before increasing exposure.
            </div>
            """,
            unsafe_allow_html=True,
        )

    tab_overview, tab_concentration, tab_sector, tab_thesis, tab_actions, tab_report = st.tabs(
        [
            "Overview",
            "Concentration",
            "Sector Exposure",
            "Thesis Quality",
            "Action Plan",
            "Save Report",
        ]
    )

    with tab_overview:
        st.markdown("### Position Risk Overview")
        overview_df = risk_df.copy()
        overview_df["Concentration Risk"] = overview_df["Weight %"].map(classify_concentration_risk)
        overview_df = make_dataframe_arrow_safe(overview_df)
        st.dataframe(overview_df, use_container_width=True, hide_index=True)

    with tab_concentration:
        st.markdown("### Concentration Risk")

        concentration_df = risk_df[["Ticker", "Company", "Weight %"]].sort_values("Weight %", ascending=False)
        concentration_df["Risk Level"] = concentration_df["Weight %"].map(classify_concentration_risk)
        concentration_df = make_dataframe_arrow_safe(concentration_df)
        st.dataframe(concentration_df, use_container_width=True, hide_index=True)

        if not risk_df.empty:
            chart_df = risk_df.set_index("Ticker")[["Weight %"]]
            st.bar_chart(chart_df, use_container_width=True)

    with tab_sector:
        st.markdown("### Sector Exposure")

        sector_df = risk_df.groupby("Sector", as_index=False)["Weight %"].sum().sort_values("Weight %", ascending=False)
        sector_df = make_dataframe_arrow_safe(sector_df)
        st.dataframe(sector_df, use_container_width=True, hide_index=True)

        if not sector_df.empty:
            st.bar_chart(sector_df.set_index("Sector"), use_container_width=True)

    with tab_thesis:
        st.markdown("### Thesis Completeness")

        thesis_df = risk_df[["Ticker", "Company", "Thesis Score", "Core Drivers", "Kill Criteria"]].copy()
        thesis_df["Review Needed"] = thesis_df["Thesis Score"].map(lambda x: "Yes" if x < 60 else "No")
        thesis_df = make_dataframe_arrow_safe(thesis_df)
        st.dataframe(thesis_df, use_container_width=True, hide_index=True)

        st.markdown("### What to improve")
        st.write("- Every holding should have a one-line thesis.")
        st.write("- Every holding should have clear core drivers.")
        st.write("- Every holding should have kill criteria.")
        st.write("- Low thesis scores should trigger a research review.")

    with tab_actions:
        st.markdown("### Risk Action Plan")

        action_df_safe = make_dataframe_arrow_safe(action_df)
        st.dataframe(action_df_safe, use_container_width=True, hide_index=True)

        st.markdown("### Suggested Risk Workflow")
        st.write("- Review largest positions first.")
        st.write("- Check sector concentration second.")
        st.write("- Fix missing kill criteria.")
        st.write("- Use Research → Red Flag Scanner for any position with medium or high risk.")
        st.write("- Use Valuation to test downside scenarios.")

    with tab_report:
        st.markdown("### Save Risk Report")

        report = build_risk_report_markdown(risk_df, summary, action_df)

        with st.expander("Preview risk report", expanded=False):
            st.markdown(report)

        if st.button("Save Risk Report", use_container_width=True, key="save_risk_terminal_report"):
            saved_path = save_markdown_report(
                report_type="deep_research",
                title="Portfolio Risk Report",
                content=report,
            )
            st.success(f"Risk report saved: {saved_path.name}")

        if st.button("Open Reports / Export Center", use_container_width=True, key="risk_open_reports"):
            st.query_params["view"] = "Reports"
            st.rerun()


def render_risk_view():
    """
    Risk page: professional portfolio risk terminal.
    """
    st.subheader("Risk")
    st.caption("Portfolio concentration, thesis quality, sector exposure, kill criteria and risk action plan.")

    render_professional_risk_terminal()





def format_number_or_na(value):
    try:
        if value is None:
            return "N/A"
        return f"{float(value):,.2f}"
    except Exception:
        return "N/A"


def format_percent_or_na(value):
    try:
        if value is None:
            return "N/A"
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "N/A"


def format_large_number(value):
    try:
        if value is None:
            return "N/A"

        value = float(value)

        if abs(value) >= 1_000_000_000_000:
            return f"{value / 1_000_000_000_000:.2f}T"
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"

        return f"{value:,.2f}"
    except Exception:
        return "N/A"


def build_company_metrics_dataframe(snapshot: dict) -> pd.DataFrame:
    """
    Build a compact company metrics table for Finance.
    This helper is required by render_finance_company_terminal().
    """
    rows = [
        {
            "Category": "Market Data",
            "Metric": "Latest Close",
            "Value": format_number_or_na(snapshot.get("latest_close")),
            "Comment": "Most recent close from the market data provider.",
        },
        {
            "Category": "Market Data",
            "Metric": "Daily Change",
            "Value": f"{format_number_or_na(snapshot.get('change'))} / {format_number_or_na(snapshot.get('change_pct'))}%",
            "Comment": "Daily price move.",
        },
        {
            "Category": "Scale",
            "Metric": "Market Cap",
            "Value": format_large_number(snapshot.get("market_cap")),
            "Comment": "Company size and liquidity context.",
        },
        {
            "Category": "Valuation",
            "Metric": "Forward P/E",
            "Value": format_number_or_na(snapshot.get("forward_pe")),
            "Comment": "Forward earnings valuation multiple.",
        },
        {
            "Category": "Valuation",
            "Metric": "Trailing P/E",
            "Value": format_number_or_na(snapshot.get("trailing_pe")),
            "Comment": "Historical earnings valuation multiple.",
        },
        {
            "Category": "Risk",
            "Metric": "Beta",
            "Value": format_number_or_na(snapshot.get("beta")),
            "Comment": "Sensitivity to broad market movement.",
        },
        {
            "Category": "Income",
            "Metric": "Dividend Yield",
            "Value": format_percent_or_na(snapshot.get("dividend_yield")),
            "Comment": "Shareholder income component.",
        },
        {
            "Category": "Range",
            "Metric": "52W High",
            "Value": format_number_or_na(snapshot.get("fifty_two_week_high")),
            "Comment": "Upper bound of one-year trading range.",
        },
        {
            "Category": "Range",
            "Metric": "52W Low",
            "Value": format_number_or_na(snapshot.get("fifty_two_week_low")),
            "Comment": "Lower bound of one-year trading range.",
        },
    ]

    return pd.DataFrame(rows)


def render_company_news_panel(ticker: str, company_name: str):
    """
    Company-specific news panel for the selected ticker.
    This avoids showing broad/general business news inside Finance.
    """
    st.markdown("### Company News")
    st.caption(f"News specifically related to {company_name} ({ticker}).")

    news_items = fetch_company_specific_news_items(ticker, company_name, max_items=8)

    if not news_items:
        st.info(
            f"No company-specific news found for {company_name} ({ticker}) from the current feeds. "
            "Try refreshing later or use Research → Deep Research for a broader company memo."
        )
        return

    for idx, item in enumerate(news_items):
        title = item.get("Title", "No title")
        publisher = item.get("Publisher", "Market source")
        published = item.get("Published", "Recent")
        summary = item.get("Summary", "")
        url = item.get("URL", "")

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"{publisher} · {published}")

            if summary:
                st.write(summary[:420] + ("..." if len(summary) > 420 else ""))

            if url:
                st.link_button("Open Source", url, use_container_width=True)


def render_finance_research_actions(ticker: str):
    """
    Action buttons from Finance to other terminal workflows.
    """
    st.markdown("### Research Actions")
    st.markdown('<div class="finance-action-note">Use these actions to move from company analysis into research, valuation, risk and export.</div>', unsafe_allow_html=True)

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        if st.button("Run Deep Research", use_container_width=True, key=f"finance_deep_{ticker}"):
            with st.spinner(f"Generating Deep Research memo for {ticker}..."):
                report = run_deep_digger(ticker)
            st.success("Deep Research memo generated.")
            with st.expander("Open generated memo", expanded=True):
                st.markdown(report)

    with a2:
        if st.button("Open Research Modules", use_container_width=True, key=f"finance_research_{ticker}"):
            st.session_state["home_selected_ticker"] = ticker
            st.query_params["view"] = "Research"
            st.rerun()

    with a3:
        if st.button("Open Valuation", use_container_width=True, key=f"finance_valuation_{ticker}"):
            st.session_state["home_selected_ticker"] = ticker
            st.query_params["view"] = "Valuation"
            st.rerun()

    with a4:
        if st.button("Open Reports", use_container_width=True, key=f"finance_reports_{ticker}"):
            st.session_state["home_selected_ticker"] = ticker
            st.query_params["view"] = "Reports"
            st.rerun()




# ============================================================
# GLOBAL COMPANY UNIVERSE CONSTANTS
# ============================================================

POPULAR_COMPANY_TICKERS = [
    "NVDA",
    "MSFT",
    "AAPL",
    "GOOGL",
    "AMZN",
    "META",
    "JPM",
    "BAC",
    "GS",
    "XOM",
    "CVX",
    "UNH",
    "LLY",
    "TSLA",
    "COST",
    "WMT",
    "HD",
    "CAT",
    "GE",
    "NEE",
]


def get_finance_default_ticker():
    """
    Compatibility helper for Finance.
    Uses the global active company ticker when available.
    """
    return get_active_company_ticker("NVDA")


def render_finance_company_terminal():
    """
    Professional Finance function: company analysis and stock tear sheet.
    """
    st.markdown(
        """
        <div class="finance-terminal-hero">
            <div class="finance-terminal-title">Company Analysis Terminal</div>
            <p class="finance-terminal-text">
                Search a company, review market data, valuation metrics, financial quality, business summary,
                company news and research actions from one Finance workspace.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.1, 1])

    with col1:
        ticker_input = st.text_input(
            "Ticker",
            value=get_finance_default_ticker(),
            placeholder="Example: NVDA, MSFT, AAPL, JPM",
            key="finance_terminal_ticker_input",
        ).upper().strip()

    with col2:
        quick_ticker = st.selectbox(
            "Quick select",
            POPULAR_COMPANY_TICKERS,
            index=POPULAR_COMPANY_TICKERS.index(get_finance_default_ticker()) if get_finance_default_ticker() in POPULAR_COMPANY_TICKERS else 0,
            key="finance_terminal_quick_select",
        )

        if st.button("Load Quick Select", use_container_width=True, key="finance_load_quick"):
            st.session_state["home_selected_ticker"] = quick_ticker
            st.rerun()

    ticker = ticker_input or quick_ticker

    if not ticker:
        st.info("Enter a ticker to open company analysis.")
        return

    snapshot = fetch_stock_snapshot(ticker)

    if snapshot.get("error"):
        st.error(f"Could not load company data: {snapshot.get('error')}")
        return

    company_name = snapshot.get("company_name", ticker)
    set_active_company(ticker, company_name)
    sector = snapshot.get("sector", "N/A")
    industry = snapshot.get("industry", "N/A")

    st.markdown(
        f"""
        <div class="finance-company-card">
            <div class="finance-company-title">{ticker} — {company_name}</div>
            <div class="finance-company-subtitle">{sector} · {industry}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_snapshot, tab_metrics, tab_news, tab_summary, tab_actions = st.tabs(
        [
            "Snapshot",
            "Metrics",
            "Company News",
            "Business Summary",
            "Actions",
        ]
    )

    with tab_snapshot:
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric("Latest Close", format_number_or_na(snapshot.get("latest_close")))

        with c2:
            st.metric("Daily Change", f"{format_number_or_na(snapshot.get('change_pct'))}%")

        with c3:
            st.metric("Market Cap", format_large_number(snapshot.get("market_cap")))

        with c4:
            st.metric("Currency", snapshot.get("currency", "N/A"))

        st.divider()

        r1, r2, r3, r4 = st.columns(4)

        with r1:
            st.metric("Forward P/E", format_number_or_na(snapshot.get("forward_pe")))

        with r2:
            st.metric("Trailing P/E", format_number_or_na(snapshot.get("trailing_pe")))

        with r3:
            st.metric("Beta", format_number_or_na(snapshot.get("beta")))

        with r4:
            st.metric("Dividend Yield", format_percent_or_na(snapshot.get("dividend_yield")))

        st.markdown(
            f"""
            <div class="finance-insight-box">
                <div class="finance-insight-title">Analyst Interpretation</div>
                <div class="finance-insight-text">
                    Review valuation multiples, beta and market-cap scale before moving into Research or Valuation.
                    If daily price movement is material, check Company News and run a Red Flag Scanner or Deep Research memo.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_metrics:
        metrics_df = build_company_metrics_dataframe(snapshot)
        metrics_df = make_dataframe_arrow_safe(metrics_df)
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    with tab_news:
        render_company_news_panel(ticker, company_name)

    with tab_summary:
        st.markdown("### Business Summary")
        business_summary = snapshot.get("business_summary", "")

        if business_summary:
            st.write(business_summary)
        else:
            st.info("No business summary available from the current market data provider.")

        st.divider()

        st.markdown("### Company Context")
        context_df = pd.DataFrame(
            [
                {"Field": "Company", "Value": company_name},
                {"Field": "Ticker", "Value": ticker},
                {"Field": "Sector", "Value": sector},
                {"Field": "Industry", "Value": industry},
                {"Field": "Currency", "Value": snapshot.get("currency", "N/A")},
            ]
        )
        context_df = make_dataframe_arrow_safe(context_df)
        st.dataframe(context_df, use_container_width=True, hide_index=True)

    with tab_actions:
        render_finance_research_actions(ticker)


def render_finance_view():
    """
    Finance page: professional company-analysis terminal.
    """
    st.subheader("Finance")
    st.caption("Company analysis, financial metrics, company news and research actions.")

    render_finance_company_terminal()



def render_economics_view():
    """
    Economics page: macro indicators and their portfolio relevance.
    """
    st.subheader("Economics")
    st.caption("Macro context, rates, FX, commodities, and portfolio transmission channels.")

    market_data = fetch_market_strip_data()

    macro_map = {
        "US 10Y": {
            "Category": "Rates",
            "Why it matters": "Higher yields usually pressure growth valuations and long-duration cash flows.",
            "Portfolio use": "Check WACC, discount-rate sensitivity, and valuation multiples.",
        },
        "USD/ZAR": {
            "Category": "FX",
            "Why it matters": "Signals emerging-market currency pressure and South African macro risk.",
            "Portfolio use": "Monitor local-currency and EM-sensitive exposures.",
        },
        "Crude Oil": {
            "Category": "Commodities",
            "Why it matters": "Oil affects inflation, transport costs, energy producers, and consumer margins.",
            "Portfolio use": "Review inflation-sensitive and energy-linked holdings.",
        },
        "Gold": {
            "Category": "Commodities",
            "Why it matters": "Gold reflects risk sentiment, real-rate expectations, and safe-haven demand.",
            "Portfolio use": "Use as a risk-sentiment input.",
        },
        "S&P 500": {
            "Category": "Equities",
            "Why it matters": "Broad global risk appetite and US equity direction.",
            "Portfolio use": "Baseline global market direction.",
        },
        "Nasdaq": {
            "Category": "Equities",
            "Why it matters": "Growth, technology, and long-duration equity sentiment.",
            "Portfolio use": "Monitor tech and growth-stock sensitivity.",
        },
        "FTSE 100": {
            "Category": "Equities",
            "Why it matters": "UK/global large-cap and commodities exposure.",
            "Portfolio use": "Compare regional risk appetite.",
        },
        "Bitcoin": {
            "Category": "Crypto/Liquidity",
            "Why it matters": "Speculative liquidity and risk-on/risk-off sentiment.",
            "Portfolio use": "Optional sentiment indicator.",
        },
    }

    rows = []
    for row in market_data:
        label = row.get("label")
        meta = macro_map.get(label, {})
        rows.append(
            {
                "Indicator": label,
                "Latest": format_market_value(row.get("value")),
                "Change %": "N/A" if row.get("change_pct") is None else f"{row.get('change_pct'):.2f}%",
                "Category": meta.get("Category", "Market"),
                "Why it matters": meta.get("Why it matters", "Macro indicator"),
                "Portfolio use": meta.get("Portfolio use", "Portfolio context"),
            }
        )

    df = pd.DataFrame(rows)
    df = make_dataframe_arrow_safe(df)

    st.markdown("### Macro Terminal")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    left, right = st.columns(2)

    with left:
        st.markdown("### Macro Risk Checklist")
        st.write("- Did yields move enough to affect valuation assumptions?")
        st.write("- Did FX moves affect EM or South Africa exposure?")
        st.write("- Did oil/gold signal inflation or risk-off pressure?")
        st.write("- Are growth stocks reacting differently from broad equities?")

    with right:
        st.markdown("### Future Economic Data to Add")
        st.write("- CPI / inflation prints")
        st.write("- Central-bank policy rates")
        st.write("- GDP / PMI calendar")
        st.write("- Earnings and macro event calendar")
        st.write("- Country-specific risk terminals")

def render_industries_view():
    """
    Industries page: sector exposure, concentration, and industry review.
    """
    st.subheader("Industries")
    st.caption("Sector exposure, portfolio concentration, and industry-level monitoring.")

    if not positions:
        st.info("No portfolio positions found.")
        return

    rows = []

    for position in positions:
        thesis = position.get("investment_thesis", {})
        monitoring = position.get("monitoring", {})
        rows.append(
            {
                "Ticker": position.get("ticker"),
                "Company": position.get("company_name"),
                "Sector": position.get("sector", "Unknown"),
                "Weight %": position.get("portfolio_weight", 0),
                "Status": position.get("position_status", "Unknown"),
                "News Priority": monitoring.get("overnight_news_priority", "normal"),
                "Core Drivers": len(thesis.get("core_drivers", [])),
                "Kill Criteria": len(thesis.get("kill_criteria", [])),
            }
        )

    df = pd.DataFrame(rows)
    df["Weight %"] = pd.to_numeric(df["Weight %"], errors="coerce").fillna(0)

    sector_df = (
        df.groupby("Sector", as_index=False)
        .agg(
            **{
                "Weight %": ("Weight %", "sum"),
                "Positions": ("Ticker", "count"),
                "Avg Kill Criteria": ("Kill Criteria", "mean"),
            }
        )
        .sort_values("Weight %", ascending=False)
    )

    top_sector = sector_df.iloc[0] if not sector_df.empty else None

    m1, m2, m3 = st.columns(3)

    with m1:
        st.metric("Sectors", len(sector_df))
    with m2:
        st.metric("Largest Sector", "N/A" if top_sector is None else str(top_sector["Sector"]))
    with m3:
        st.metric("Largest Sector Weight", "N/A" if top_sector is None else f"{top_sector['Weight %']:.1f}%")

    st.divider()

    col1, col2 = st.columns([1.25, 1])

    with col1:
        st.markdown("### Sector Exposure")
        sector_display = make_dataframe_arrow_safe(sector_df)
        st.dataframe(sector_display, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### Sector Weight Chart")
        st.bar_chart(sector_df.set_index("Sector")[["Weight %"]])

    st.divider()

    st.markdown("### Positions by Sector")
    df = df.sort_values(["Sector", "Weight %"], ascending=[True, False])
    df = make_dataframe_arrow_safe(df)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### Industry Review Notes")
    st.write("- Identify over-concentration by sector.")
    st.write("- Check whether high-priority news names cluster in one sector.")
    st.write("- Review sector-specific kill criteria.")
    st.write("- Use Deep Digger for sector leaders or positions with weak thesis files.")

def render_technology_view():
    """
    Technology page: quick tech watchlist and focused tear sheet.
    """
    st.subheader("Technology")
    st.caption("Technology, AI, cloud, software, semiconductors, and growth-stock workspace.")

    default_tech = ["NVDA", "MSFT", "AAPL", "AMD", "ASML", "META", "GOOGL", "AMZN"]

    rows = []

    for ticker_symbol in default_tech:
        try:
            snap = fetch_stock_snapshot(ticker_symbol)
            rows.append(
                {
                    "Ticker": ticker_symbol,
                    "Company": snap.get("company_name", ticker_symbol),
                    "Latest Close": format_number_or_na(snap.get("latest_close")),
                    "Change %": format_number_or_na(snap.get("change_pct")),
                    "Market Cap": format_large_number(snap.get("market_cap")),
                    "Forward P/E": format_number_or_na(snap.get("forward_pe")),
                    "Beta": format_number_or_na(snap.get("beta")),
                    "Theme": {
                        "NVDA": "AI semiconductors",
                        "MSFT": "Cloud and enterprise AI",
                        "AAPL": "Consumer hardware and ecosystem",
                        "AMD": "AI/CPU/GPU competition",
                        "ASML": "Semiconductor equipment",
                        "META": "Digital ads and AI infrastructure",
                        "GOOGL": "Search, cloud, and AI",
                        "AMZN": "E-commerce, AWS, and AI",
                    }.get(ticker_symbol, "Technology"),
                }
            )
        except Exception:
            rows.append(
                {
                    "Ticker": ticker_symbol,
                    "Company": ticker_symbol,
                    "Latest Close": "N/A",
                    "Change %": "N/A",
                    "Market Cap": "N/A",
                    "Forward P/E": "N/A",
                    "Beta": "N/A",
                    "Theme": "Technology",
                }
            )

    tech_df = pd.DataFrame(rows)
    tech_df = make_dataframe_arrow_safe(tech_df)

    st.markdown("### Technology Watchlist")
    st.dataframe(tech_df, use_container_width=True, hide_index=True)

    st.divider()

    tech_ticker = st.text_input(
        "Open technology tear sheet",
        placeholder="Example: NVDA, MSFT, AAPL, AMD, ASML",
        key="technology_ticker",
    ).upper().strip()

    if tech_ticker:
        render_stock_tear_sheet(tech_ticker)
    else:
        st.info("Enter a technology ticker to open a focused tear sheet.")

    st.divider()

    st.markdown("### Technology Review Checklist")
    st.write("- Revenue growth durability")
    st.write("- Gross/EBIT margin sustainability")
    st.write("- AI/cloud/semiconductor exposure")
    st.write("- Valuation multiple sensitivity to rates")
    st.write("- Competitive moat and platform risk")

def render_scheduler_view():
    st.subheader("Scheduler Controls")
    scheduler = st.session_state.get("portfolio_scheduler")
    scheduler_running = bool(scheduler and scheduler.running)
    jobs = get_scheduler_jobs()
    sched_col1, sched_col2, sched_col3, sched_col4 = st.columns(4)
    with sched_col1:
        st.metric("Scheduler", "Running" if scheduler_running else "Stopped")
    with sched_col2:
        st.metric("Scheduled Jobs", len(jobs))
    with sched_col3:
        if st.button("Start Scheduler", use_container_width=True):
            get_or_start_scheduler()
            st.success("Scheduler started.")
    with sched_col4:
        if st.button("Stop Scheduler", use_container_width=True):
            stop_scheduler()
            st.warning("Scheduler stopped.")
    if jobs:
        jobs_df = pd.DataFrame([{"Job ID": job.id, "Next Run": str(job.next_run_time), "Trigger": str(job.trigger)} for job in jobs])
        st.dataframe(make_dataframe_arrow_safe(jobs_df), use_container_width=True, hide_index=True)
    else:
        st.info("Scheduler is not running.")



def get_selected_terminal_view() -> str:
    """
    Read active view from query parameters so the top black nav works as real navigation.
    """
    valid_views = [
        "Home",
        "Markets",
        "Finance",
        "Portfolio",
        "Research",
        "Reports",
        "Valuation",
        "Risk",
    ]

    try:
        selected = st.query_params.get("view", "Home")
    except Exception:
        selected = "Home"

    if isinstance(selected, list):
        selected = selected[0] if selected else "Markets"

    if selected not in valid_views:
        selected = "Home"

    return selected




# ============================================================
# TERMINAL LAYOUT
# ============================================================

inject_custom_css()

terminal_view = get_selected_terminal_view()

render_terminal_header()
terminal_view = render_terminal_function_ribbon(terminal_view)
render_market_strip()

st.markdown('<div class="content-container">', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="terminal-page-title">{terminal_view}</div>
    <div class="terminal-page-subtitle">Institutional research terminal.</div>
    """,
    unsafe_allow_html=True,
)

if terminal_view == "Home":
    render_home_view()

elif terminal_view == "Markets":
    render_overview()

elif terminal_view == "Finance":
    render_finance_view()




elif terminal_view == "Portfolio":
    render_portfolio_view()

elif terminal_view == "Research":
    render_agents_view()

elif terminal_view == "Reports":
    render_reports_view()


elif terminal_view == "Valuation":
    render_valuation_lab_view()

elif terminal_view == "Risk":
    render_risk_view()


st.markdown("</div>", unsafe_allow_html=True)
def format_daily_change_text(change_pct) -> tuple[str, str, str]:
    """
    Return arrow, formatted change text, and CSS class for daily ticker update.
    """
    if change_pct is None:
        return "•", "N/A", "neutral-text"

    try:
        change_pct = float(change_pct)
    except (TypeError, ValueError):
        return "•", "N/A", "neutral-text"

    if change_pct > 0:
        return "▲", f"{change_pct:.2f}%", "positive-text"

    if change_pct < 0:
        return "▼", f"{abs(change_pct):.2f}%", "negative-text"

    return "•", "0.00%", "neutral-text"


def build_daily_update_sentence(label: str, category: str, latest, change_pct, purpose: str) -> str:
    """
    Build a short daily market update for the selected ticker.
    """
    arrow, change_text, _ = format_daily_change_text(change_pct)
    latest_text = format_market_value(latest)

    if change_pct is None:
        direction = "has no available daily percentage move"
    else:
        try:
            change_pct_float = float(change_pct)
        except (TypeError, ValueError):
            change_pct_float = 0

        if change_pct_float > 0:
            direction = "is trading higher today"
        elif change_pct_float < 0:
            direction = "is trading lower today"
        else:
            direction = "is broadly flat today"

    return (
        f"{label} ({category}) {direction} at {latest_text} "
        f"with a daily move of {arrow} {change_text}. "
        f"Market relevance: {purpose}"
    )


def render_daily_update_box(label: str, category: str, latest, change_pct, purpose: str):
    """
    Render a color-coded daily update box for a ticker.
    """
    arrow, change_text, css_class = format_daily_change_text(change_pct)
    sentence = build_daily_update_sentence(label, category, latest, change_pct, purpose)

    st.markdown(
        f"""
        <div class="daily-update-box">
            <div class="daily-update-title">Daily Update — {label}</div>
            <p class="daily-update-text">
                <span class="{css_class}">{arrow} {change_text}</span> — {sentence}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )



