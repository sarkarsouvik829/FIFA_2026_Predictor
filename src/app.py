"""Streamlit UI: match prediction + 2026 World Cup fixtures browser."""

from __future__ import annotations

import base64
import html
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Literal

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import datetime

import streamlit as st

from src.matches_common import load_completed_matches_chronological
from src.predict_match import MatchPredictor
from src.wc_disk_cache import load_triple, merge_save_live_ft, merge_save_prediction, merge_save_predictions_batch
from src.wc_live_scores import dates_up_to_today_inclusive, fetch_live_scores_by_fixture_idx
from src.wc_knockout_schedule import (
    KNOCKOUT_ROUNDS_ORDER,
    ROUNDS_FROM_R16,
    get_resolved_knockout_fixtures,
    round_schedule_status,
)
from src import wc_usage_log

# ── 2026 fixture data (ESPN schedule, June 11 results confirmed) ──────────────
# Keys: group, date, home, away, venue, actual (None if unplayed)
_FIXTURES: list[dict] = [
    # ── Group A ────────────────────────────────────────────────────────────────
    {"group":"A","date":"2026-06-11","home":"Mexico",       "away":"South Africa","venue":"Estadio Azteca, Mexico City",          "actual":"2 – 0"},
    {"group":"A","date":"2026-06-11","home":"South Korea",  "away":"Czechia",     "venue":"Estadio Akron, Zapopan",               "actual":"2 – 1"},
    {"group":"A","date":"2026-06-18","home":"Czechia",      "away":"South Africa","venue":"Mercedes-Benz Stadium, Atlanta",        "actual":None},
    {"group":"A","date":"2026-06-18","home":"Mexico",       "away":"South Korea", "venue":"Estadio Akron, Zapopan",               "actual":None},
    {"group":"A","date":"2026-06-24","home":"Czechia",      "away":"Mexico",      "venue":"Estadio Azteca, Mexico City",          "actual":None},
    {"group":"A","date":"2026-06-24","home":"South Africa", "away":"South Korea", "venue":"Estadio BBVA, Guadalupe",              "actual":None},
    # ── Group B ────────────────────────────────────────────────────────────────
    {"group":"B","date":"2026-06-12","home":"Canada",       "away":"Bosnia and Herzegovina","venue":"BMO Field, Toronto",          "actual":"1 – 1"},
    {"group":"B","date":"2026-06-13","home":"Qatar",        "away":"Switzerland", "venue":"Levi's Stadium, Santa Clara",          "actual":"1 – 1"},
    {"group":"B","date":"2026-06-18","home":"Switzerland",  "away":"Bosnia and Herzegovina","venue":"SoFi Stadium, Inglewood",     "actual":None},
    {"group":"B","date":"2026-06-18","home":"Canada",       "away":"Qatar",       "venue":"BC Place, Vancouver",                  "actual":None},
    {"group":"B","date":"2026-06-24","home":"Switzerland",  "away":"Canada",      "venue":"BC Place, Vancouver",                  "actual":None},
    {"group":"B","date":"2026-06-24","home":"Bosnia and Herzegovina","away":"Qatar","venue":"Lumen Field, Seattle",               "actual":None},
    # ── Group C ────────────────────────────────────────────────────────────────
    {"group":"C","date":"2026-06-13","home":"Brazil",       "away":"Morocco",     "venue":"MetLife Stadium, East Rutherford",     "actual":"1 – 1"},
    {"group":"C","date":"2026-06-13","home":"Haiti",        "away":"Scotland",    "venue":"Gillette Stadium, Foxborough",         "actual":"0 – 1"},
    {"group":"C","date":"2026-06-19","home":"Scotland",     "away":"Morocco",     "venue":"Gillette Stadium, Foxborough",         "actual":None},
    {"group":"C","date":"2026-06-19","home":"Brazil",       "away":"Haiti",       "venue":"Lincoln Financial Field, Philadelphia","actual":None},
    {"group":"C","date":"2026-06-24","home":"Scotland",     "away":"Brazil",      "venue":"Hard Rock Stadium, Miami Gardens",     "actual":None},
    {"group":"C","date":"2026-06-24","home":"Morocco",      "away":"Haiti",       "venue":"Mercedes-Benz Stadium, Atlanta",       "actual":None},
    # ── Group D ────────────────────────────────────────────────────────────────
    {"group":"D","date":"2026-06-12","home":"United States","away":"Paraguay",    "venue":"SoFi Stadium, Inglewood",              "actual":"4 – 1"},
    {"group":"D","date":"2026-06-13","home":"Australia",    "away":"Turkey",      "venue":"BC Place, Vancouver",                  "actual":"2 – 0"},
    {"group":"D","date":"2026-06-19","home":"United States","away":"Australia",   "venue":"Lumen Field, Seattle",                 "actual":None},
    {"group":"D","date":"2026-06-19","home":"Turkey",       "away":"Paraguay",    "venue":"Levi's Stadium, Santa Clara",          "actual":None},
    {"group":"D","date":"2026-06-25","home":"Turkey",       "away":"United States","venue":"SoFi Stadium, Inglewood",            "actual":None},
    {"group":"D","date":"2026-06-25","home":"Paraguay",     "away":"Australia",   "venue":"Levi's Stadium, Santa Clara",          "actual":None},
    # ── Group E ────────────────────────────────────────────────────────────────
    {"group":"E","date":"2026-06-14","home":"Germany",      "away":"Curaçao",     "venue":"NRG Stadium, Houston",                 "actual":None},
    {"group":"E","date":"2026-06-14","home":"Ivory Coast",  "away":"Ecuador",     "venue":"Lincoln Financial Field, Philadelphia","actual":None},
    {"group":"E","date":"2026-06-20","home":"Germany",      "away":"Ivory Coast", "venue":"BMO Field, Toronto",                   "actual":None},
    {"group":"E","date":"2026-06-20","home":"Ecuador",      "away":"Curaçao",     "venue":"Arrowhead Stadium, Kansas City",       "actual":None},
    {"group":"E","date":"2026-06-25","home":"Ecuador",      "away":"Germany",     "venue":"MetLife Stadium, East Rutherford",     "actual":None},
    {"group":"E","date":"2026-06-25","home":"Curaçao",      "away":"Ivory Coast", "venue":"Lincoln Financial Field, Philadelphia","actual":None},
    # ── Group F ────────────────────────────────────────────────────────────────
    {"group":"F","date":"2026-06-14","home":"Netherlands",  "away":"Japan",       "venue":"AT&T Stadium, Arlington",              "actual":None},
    {"group":"F","date":"2026-06-14","home":"Sweden",       "away":"Tunisia",     "venue":"Estadio BBVA, Guadalupe",              "actual":None},
    {"group":"F","date":"2026-06-20","home":"Netherlands",  "away":"Sweden",      "venue":"NRG Stadium, Houston",                 "actual":None},
    {"group":"F","date":"2026-06-20","home":"Tunisia",      "away":"Japan",       "venue":"Estadio BBVA, Guadalupe",              "actual":None},
    {"group":"F","date":"2026-06-25","home":"Japan",        "away":"Sweden",      "venue":"AT&T Stadium, Arlington",              "actual":None},
    {"group":"F","date":"2026-06-25","home":"Tunisia",      "away":"Netherlands", "venue":"Arrowhead Stadium, Kansas City",       "actual":None},
    # ── Group G ────────────────────────────────────────────────────────────────
    {"group":"G","date":"2026-06-15","home":"Belgium",      "away":"Egypt",       "venue":"Lumen Field, Seattle",                 "actual":None},
    {"group":"G","date":"2026-06-15","home":"Iran",         "away":"New Zealand", "venue":"SoFi Stadium, Inglewood",              "actual":None},
    {"group":"G","date":"2026-06-21","home":"Belgium",      "away":"Iran",        "venue":"SoFi Stadium, Inglewood",              "actual":None},
    {"group":"G","date":"2026-06-21","home":"New Zealand",  "away":"Egypt",       "venue":"BC Place, Vancouver",                  "actual":None},
    {"group":"G","date":"2026-06-26","home":"Egypt",        "away":"Iran",        "venue":"Lumen Field, Seattle",                 "actual":None},
    {"group":"G","date":"2026-06-26","home":"New Zealand",  "away":"Belgium",     "venue":"BC Place, Vancouver",                  "actual":None},
    # ── Group H ────────────────────────────────────────────────────────────────
    {"group":"H","date":"2026-06-15","home":"Spain",        "away":"Cape Verde",  "venue":"Mercedes-Benz Stadium, Atlanta",       "actual":None},
    {"group":"H","date":"2026-06-15","home":"Saudi Arabia", "away":"Uruguay",     "venue":"Hard Rock Stadium, Miami Gardens",     "actual":None},
    {"group":"H","date":"2026-06-21","home":"Spain",        "away":"Saudi Arabia","venue":"Mercedes-Benz Stadium, Atlanta",       "actual":None},
    {"group":"H","date":"2026-06-21","home":"Uruguay",      "away":"Cape Verde",  "venue":"Hard Rock Stadium, Miami Gardens",     "actual":None},
    {"group":"H","date":"2026-06-26","home":"Cape Verde",   "away":"Saudi Arabia","venue":"NRG Stadium, Houston",                 "actual":None},
    {"group":"H","date":"2026-06-26","home":"Uruguay",      "away":"Spain",       "venue":"Estadio Akron, Zapopan",               "actual":None},
    # ── Group I ────────────────────────────────────────────────────────────────
    {"group":"I","date":"2026-06-16","home":"France",       "away":"Senegal",     "venue":"MetLife Stadium, East Rutherford",     "actual":None},
    {"group":"I","date":"2026-06-16","home":"Iraq",         "away":"Norway",      "venue":"Gillette Stadium, Foxborough",         "actual":None},
    {"group":"I","date":"2026-06-22","home":"France",       "away":"Iraq",        "venue":"Lincoln Financial Field, Philadelphia","actual":None},
    {"group":"I","date":"2026-06-22","home":"Norway",       "away":"Senegal",     "venue":"MetLife Stadium, East Rutherford",     "actual":None},
    {"group":"I","date":"2026-06-26","home":"Norway",       "away":"France",      "venue":"Gillette Stadium, Foxborough",         "actual":None},
    {"group":"I","date":"2026-06-26","home":"Senegal",      "away":"Iraq",        "venue":"BMO Field, Toronto",                   "actual":None},
    # ── Group J ────────────────────────────────────────────────────────────────
    {"group":"J","date":"2026-06-16","home":"Argentina",    "away":"Algeria",     "venue":"Arrowhead Stadium, Kansas City",       "actual":None},
    {"group":"J","date":"2026-06-16","home":"Austria",      "away":"Jordan",      "venue":"Levi's Stadium, Santa Clara",          "actual":None},
    {"group":"J","date":"2026-06-22","home":"Argentina",    "away":"Austria",     "venue":"AT&T Stadium, Arlington",              "actual":None},
    {"group":"J","date":"2026-06-22","home":"Jordan",       "away":"Algeria",     "venue":"Levi's Stadium, Santa Clara",          "actual":None},
    {"group":"J","date":"2026-06-27","home":"Algeria",      "away":"Austria",     "venue":"Arrowhead Stadium, Kansas City",       "actual":None},
    {"group":"J","date":"2026-06-27","home":"Jordan",       "away":"Argentina",   "venue":"AT&T Stadium, Arlington",              "actual":None},
    # ── Group K ────────────────────────────────────────────────────────────────
    {"group":"K","date":"2026-06-17","home":"Portugal",     "away":"DR Congo",    "venue":"NRG Stadium, Houston",                 "actual":None},
    {"group":"K","date":"2026-06-17","home":"Uzbekistan",   "away":"Colombia",    "venue":"Estadio Azteca, Mexico City",          "actual":None},
    {"group":"K","date":"2026-06-23","home":"Portugal",     "away":"Uzbekistan",  "venue":"NRG Stadium, Houston",                 "actual":None},
    {"group":"K","date":"2026-06-23","home":"Colombia",     "away":"DR Congo",    "venue":"Estadio Akron, Zapopan",               "actual":None},
    {"group":"K","date":"2026-06-27","home":"Colombia",     "away":"Portugal",    "venue":"Hard Rock Stadium, Miami Gardens",     "actual":None},
    {"group":"K","date":"2026-06-27","home":"DR Congo",     "away":"Uzbekistan",  "venue":"Mercedes-Benz Stadium, Atlanta",       "actual":None},
    # ── Group L ────────────────────────────────────────────────────────────────
    {"group":"L","date":"2026-06-17","home":"England",      "away":"Croatia",     "venue":"AT&T Stadium, Arlington",              "actual":None},
    {"group":"L","date":"2026-06-17","home":"Ghana",        "away":"Panama",      "venue":"BMO Field, Toronto",                   "actual":None},
    {"group":"L","date":"2026-06-23","home":"England",      "away":"Ghana",       "venue":"Gillette Stadium, Foxborough",         "actual":None},
    {"group":"L","date":"2026-06-23","home":"Panama",       "away":"Croatia",     "venue":"BMO Field, Toronto",                   "actual":None},
    {"group":"L","date":"2026-06-27","home":"Panama",       "away":"England",     "venue":"MetLife Stadium, East Rutherford",     "actual":None},
    {"group":"L","date":"2026-06-27","home":"Croatia",      "away":"Ghana",       "venue":"Lincoln Financial Field, Philadelphia","actual":None},
]

# Round of 32 + later (TBD teams – shown greyed out)
_KO_FIXTURES: list[dict] = [
    {"round":"Round of 32","date":"2026-06-28","label":"Group A 2nd vs Group B 2nd",       "venue":"SoFi Stadium, Inglewood"},
    {"round":"Round of 32","date":"2026-06-29","label":"Group C 1st vs Group F 2nd",        "venue":"NRG Stadium, Houston"},
    {"round":"Round of 32","date":"2026-06-29","label":"Group E 1st vs Best 3rd (ABCDF)",   "venue":"Gillette Stadium, Foxborough"},
    {"round":"Round of 32","date":"2026-06-29","label":"Group F 1st vs Group C 2nd",        "venue":"Estadio BBVA, Guadalupe"},
    {"round":"Round of 32","date":"2026-06-30","label":"Group E 2nd vs Group I 2nd",        "venue":"AT&T Stadium, Arlington"},
    {"round":"Round of 32","date":"2026-06-30","label":"Group I 1st vs Best 3rd (CDFGH)",   "venue":"MetLife Stadium, East Rutherford"},
    {"round":"Round of 32","date":"2026-06-30","label":"Group A 1st vs Best 3rd (CEFHI)",   "venue":"Estadio Azteca, Mexico City"},
    {"round":"Round of 32","date":"2026-07-01","label":"Group L 1st vs Best 3rd (EHIJK)",   "venue":"Mercedes-Benz Stadium, Atlanta"},
    {"round":"Round of 32","date":"2026-07-01","label":"Group G 1st vs Best 3rd (AEHIJ)",   "venue":"Lumen Field, Seattle"},
    {"round":"Round of 32","date":"2026-07-01","label":"Group D 1st vs Best 3rd (BEFIJ)",   "venue":"Levi's Stadium, Santa Clara"},
    {"round":"Round of 32","date":"2026-07-02","label":"Group H 1st vs Group J 2nd",        "venue":"SoFi Stadium, Inglewood"},
    {"round":"Round of 32","date":"2026-07-02","label":"Group K 2nd vs Group L 2nd",        "venue":"BMO Field, Toronto"},
    {"round":"Round of 32","date":"2026-07-02","label":"Group B 1st vs Best 3rd (EFGIJ)",   "venue":"BC Place, Vancouver"},
    {"round":"Round of 32","date":"2026-07-03","label":"Group D 2nd vs Group G 2nd",        "venue":"AT&T Stadium, Arlington"},
    {"round":"Round of 32","date":"2026-07-03","label":"Group J 1st vs Group H 2nd",        "venue":"Hard Rock Stadium, Miami Gardens"},
    {"round":"Round of 32","date":"2026-07-03","label":"Group K 1st vs Best 3rd (DEIJL)",   "venue":"Arrowhead Stadium, Kansas City"},
    {"round":"Round of 16","date":"2026-07-04","label":"R16 Match 1",                       "venue":"NRG Stadium, Houston"},
    {"round":"Round of 16","date":"2026-07-04","label":"R16 Match 2",                       "venue":"Lincoln Financial Field, Philadelphia"},
    {"round":"Round of 16","date":"2026-07-05","label":"R16 Match 3",                       "venue":"MetLife Stadium, East Rutherford"},
    {"round":"Round of 16","date":"2026-07-05","label":"R16 Match 4",                       "venue":"Estadio Azteca, Mexico City"},
    {"round":"Round of 16","date":"2026-07-06","label":"R16 Match 5",                       "venue":"AT&T Stadium, Arlington"},
    {"round":"Round of 16","date":"2026-07-06","label":"R16 Match 6",                       "venue":"Lumen Field, Seattle"},
    {"round":"Round of 16","date":"2026-07-07","label":"R16 Match 7",                       "venue":"Mercedes-Benz Stadium, Atlanta"},
    {"round":"Round of 16","date":"2026-07-07","label":"R16 Match 8",                       "venue":"BC Place, Vancouver"},
    {"round":"Quarter-Finals","date":"2026-07-09","label":"QF 1",                           "venue":"Gillette Stadium, Foxborough"},
    {"round":"Quarter-Finals","date":"2026-07-10","label":"QF 2",                           "venue":"SoFi Stadium, Inglewood"},
    {"round":"Quarter-Finals","date":"2026-07-11","label":"QF 3",                           "venue":"Hard Rock Stadium, Miami Gardens"},
    {"round":"Quarter-Finals","date":"2026-07-11","label":"QF 4",                           "venue":"Arrowhead Stadium, Kansas City"},
    {"round":"Semi-Finals",   "date":"2026-07-14","label":"SF 1",                           "venue":"AT&T Stadium, Arlington"},
    {"round":"Semi-Finals",   "date":"2026-07-15","label":"SF 2",                           "venue":"Mercedes-Benz Stadium, Atlanta"},
    {"round":"3rd Place",     "date":"2026-07-18","label":"3rd Place Play-off",              "venue":"Hard Rock Stadium, Miami Gardens"},
    {"round":"Final",         "date":"2026-07-19","label":"2026 World Cup Final",            "venue":"MetLife Stadium, East Rutherford"},
]

# Attach a flat index to every group fixture (knockout indices assigned at runtime).
for _i, _f in enumerate(_FIXTURES):
    _f["_idx"] = _i

_KO_IDX_BASE = len(_FIXTURES)

# Team name map: fixture display name → dataset name (only when they differ)
_DS_NAME: dict[str, str] = {
    "Türkiye": "Turkey",
    "Czechia":  "Czech Republic",
}


def _ds(name: str, team_set: set) -> str | None:
    """Return the dataset team name, or None if unrecognised."""
    for candidate in (_DS_NAME.get(name, name), name):
        if candidate in team_set:
            return candidate
    return None


# ── Adidas ball image (base64 so it works in st.markdown HTML) ───────────────
def _ball_img_tag(width: int = 60) -> str:
    path = _ROOT / "adidas-ball-image.png"
    if path.exists():
        b64 = base64.b64encode(path.read_bytes()).decode()
        return (
            f'<span class="wc-ball">'
            f'<img src="data:image/png;base64,{b64}" '
            f'width="{width}" height="{width}" '
            f'style="object-fit:contain;display:block;'
            f'filter:drop-shadow(0 3px 8px rgba(0,0,0,0.5))">'
            f'</span>'
        )
    return "⚽"


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
    @keyframes ball-spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
    }
    .wc-ball {
        animation: ball-spin 5s linear infinite;
        display: inline-block;
        flex-shrink: 0;
    }

    html, body {
        background-color: #1a3352 !important;
    }
    .stApp {
        background-color: #1a3352;
        background: linear-gradient(165deg, #1a3352 0%, #1e3f5e 38%, #1a3550 100%);
        background-attachment: fixed;
        min-height: 100vh;
        color: #eef6fc;
    }
    .main .block-container { color: #eef6fc; }
    header[data-testid="stHeader"] { background: rgba(26, 51, 82, 0.92); }
    div[data-testid="stToolbar"] { visibility: hidden; height: 0; }

    /* Session visit counter — fixed top-right */
    .wc-visit-badge {
        position: fixed;
        top: 3.75rem;
        right: 0.85rem;
        z-index: 999999;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 1px;
        pointer-events: none;
        font-family: "Segoe UI", system-ui, sans-serif;
    }
    .wc-visit-badge .wc-visit-num {
        font-size: 1.28rem;
        font-weight: 900;
        color: #ffe566;
        line-height: 1;
        text-shadow: 0 1px 4px rgba(0,0,0,0.55);
    }
    .wc-visit-badge .wc-visit-lbl {
        font-size: 0.58rem;
        font-weight: 700;
        letter-spacing: 0.07em;
        color: #9ec5e8;
        text-transform: uppercase;
    }

    .stMarkdown, .stMarkdown p, [data-testid="stMarkdownContainer"] p {
        color: #e8f1fa !important;
    }
    label[data-testid="stWidgetLabel"] p,
    .stWidget > label span,
    [data-testid="stWidgetLabel"] { color: #f4f9ff !important; }
    [data-baseweb="radio"] label,
    .stRadio div[role="radiogroup"] label { color: #f0f7ff !important; }
    input, [data-baseweb="input"] input { color: #0d1f2d !important; }

    .wc-hero {
        background: linear-gradient(90deg, rgba(255,223,120,0.18) 0%, rgba(20,120,85,0.22) 50%, rgba(255,215,100,0.14) 100%);
        border: 1px solid rgba(255, 210, 120, 0.55);
        border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;
        box-shadow: 0 8px 28px rgba(0,0,0,0.25);
    }
    .wc-hero h1 {
        font-family: "Segoe UI", system-ui, sans-serif;
        font-size: 1.65rem; font-weight: 700; letter-spacing: 0.04em;
        color: #fff8e8; margin: 0 0 0.35rem 0;
        text-shadow: 0 1px 4px rgba(0,0,0,0.45);
    }
    .wc-hero p { color: #dceaf5; margin: 0; font-size: 0.98rem; line-height: 1.45; }
    .wc-badge {
        display: inline-block;
        background: linear-gradient(135deg, #ffd85c, #c9a227);
        color: #142433; font-size: 0.7rem; font-weight: 800;
        letter-spacing: 0.12em; padding: 0.2rem 0.55rem;
        border-radius: 4px; margin-bottom: 0.5rem;
    }

    .wc-acc-hero {
        display: flex; flex-wrap: wrap; align-items: stretch; gap: 14px;
        background: linear-gradient(135deg, rgba(12, 60, 42, 0.92), rgba(18, 52, 88, 0.88));
        border: 2px solid rgba(255, 210, 120, 0.65);
        border-radius: 14px; padding: 14px 18px; margin-bottom: 14px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.35);
    }
    .wc-acc-hero .acc-block {
        flex: 1; min-width: 140px; text-align: center;
        background: rgba(0,0,0,0.22); border-radius: 10px; padding: 10px 12px;
        border: 1px solid rgba(255,255,255,0.12);
    }
    .wc-acc-hero .acc-val {
        font-size: 1.85rem; font-weight: 900; line-height: 1.1;
        font-family: "Segoe UI", system-ui, sans-serif;
    }
    .wc-acc-hero .acc-lbl {
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.11em;
        color: #ffe08a; text-transform: uppercase; margin-top: 4px;
    }
    .wc-acc-hero .acc-sub {
        font-size: 0.72rem; color: #b8d4ea; margin-top: 6px; line-height: 1.35;
    }
    /* Responsive reasoning grid — 3 cols on desktop, 1 on mobile */
    .rsn-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-bottom: 12px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px; background: rgba(0,0,0,0.18); padding: 5px 6px; border-radius: 10px;
        flex-wrap: wrap;
    }
    .stTabs [data-baseweb="tab"] { border-radius: 7px; color: #cfe6f7 !important; font-weight: 600; font-size: 0.85rem; }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(180deg, #138a56, #0d6b42) !important;
        color: #fffce8 !important;
    }

    .wc-card-title {
        color: #ffe08a; font-weight: 700; font-size: 0.85rem;
        letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.75rem;
    }

    div[data-testid="stButton"] > button[kind="primary"],
    div[data-testid="stButton"] > button {
        background: linear-gradient(180deg, #15965e, #0c6b42) !important;
        border: 1px solid rgba(255, 220, 140, 0.55) !important;
        color: #fffce8 !important; font-weight: 700 !important;
    }
    div[data-testid="stButton"] > button:hover {
        box-shadow: 0 0 18px rgba(255, 220, 140, 0.4);
    }

    /* Match predictor result */
    .wc-result {
        background: linear-gradient(135deg, rgba(30, 110, 75, 0.55), rgba(22, 48, 72, 0.92));
        border: 1px solid rgba(255, 210, 120, 0.45);
        border-radius: 12px; padding: 1.1rem 1.25rem; margin-top: 0.75rem;
    }
    .wc-result .big { font-size: 1.35rem; font-weight: 800; color: #fff8e8; }
    .wc-result .sub { color: #e4f0fb !important; font-size: 0.95rem; margin-top: 0.4rem; line-height: 1.5; }
    .wc-result .wc-xg {
        margin-top: 0.85rem; padding-top: 0.85rem;
        border-top: 1px solid rgba(255, 210, 120, 0.35);
        color: #f2f9ff !important; font-size: 1rem;
    }
    .wc-result .xg-num { color: #ffe566; font-weight: 800; font-size: 1.12rem; }
    .wc-result .wc-xg-note { color: #c5daf0 !important; font-size: 0.82rem; margin-top: 0.35rem; }

    /* Fixture row */
    .fx-row {
        display: flex; align-items: center; gap: 6px;
        padding: 6px 10px; border-radius: 7px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .fx-row:hover { background: rgba(255,255,255,0.04); }
    .fx-date  { color: #6fa8c0; font-size: 0.72rem; min-width: 68px; }
    .fx-match { color: #eef6fc; font-size: 0.88rem; font-weight: 600; flex: 1; }
    .fx-venue { color: #7aa8c0; font-size: 0.72rem; flex: 1; font-style: italic; }
    .fx-actual { color: #ffe08a; font-weight: 700; font-size: 0.8rem; min-width: 54px; text-align: center; }
    .fx-pred {
        background: rgba(30,80,50,0.55);
        border: 1px solid rgba(100,220,140,0.3);
        border-radius: 6px; padding: 3px 8px;
        font-size: 0.75rem; color: #b8f0cc; margin-top: 2px;
    }
    .fx-pred-main { font-size: 0.82rem; font-weight: 700; color: #e8fdf0; margin-bottom: 3px; line-height: 1.35; }
    .fx-pred-ft { font-size: 0.72rem; color: #c5e8d8; margin-bottom: 4px; line-height: 1.4; }
    .fx-pred-winner { color: #ffe566; font-weight: 800; text-shadow: 0 0 10px rgba(255, 230, 100, 0.25); }
    .fx-pred-draw { color: #9cf0ff; font-weight: 800; }

    /* KO fixture row */
    .ko-row {
        padding: 5px 10px; border-radius: 6px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        opacity: 0.6;
        font-size: 0.82rem; color: #8bb8d0;
    }
    .ko-round { color: #ffe08a; font-weight: 700; font-size: 0.7rem; letter-spacing: 0.08em; }

    h3, h4, h5 { color: #ffe08a !important; }
    .stCaption { color: #d0e4f5 !important; }

    /* ── Tighten default block padding on all screens ── */
    .main .block-container {
        padding-left: 1.1rem;
        padding-right: 1.1rem;
        padding-top: 0.9rem;
        max-width: 100%;
    }

    /* ── Mobile — up to 768 px ──────────────────────────────────────── */
    @media screen and (max-width: 768px) {

        /* More breathing room on narrow screens */
        .main .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 0.5rem !important;
        }

        /* Compact hero */
        .wc-hero {
            padding: 0.75rem 0.9rem;
            margin-bottom: 0.6rem;
            border-radius: 10px;
        }
        .wc-hero h1 { font-size: 1.05rem; letter-spacing: 0.02em; }
        .wc-hero img { width: 40px !important; height: 40px !important; }
        .wc-hero p  { font-size: 0.8rem; }
        .wc-badge   { font-size: 0.6rem; padding: 0.15rem 0.4rem; }

        .wc-acc-hero { flex-direction: column !important; gap: 8px !important; padding: 10px 12px !important; }
        .wc-acc-hero .acc-val { font-size: 1.45rem; }

        /* Stack Streamlit columns vertically */
        [data-testid="stHorizontalBlock"],
        [data-testid="stColumns"] {
            flex-direction: column !important;
            gap: 0 !important;
        }
        [data-testid="column"],
        [data-testid="stColumn"] {
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }

        /* Reasoning grid: single column on mobile */
        .rsn-grid {
            grid-template-columns: 1fr !important;
        }

        /* Hide table-header row on mobile (columns stack, headers make no sense) */
        .pred-col-header { display: none !important; }

        /* Group tabs in Fixtures tab — scroll horizontally, don't wrap */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
            -webkit-overflow-scrolling: touch;
            gap: 3px !important;
            padding: 4px 5px !important;
            scrollbar-width: none;          /* Firefox */
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.75rem !important;
            padding: 5px 9px !important;
            white-space: nowrap;
        }

        /* Full-width tap-friendly buttons */
        div[data-testid="stButton"] > button {
            min-height: 48px !important;
            font-size: 0.92rem !important;
            width: 100%;
            border-radius: 8px !important;
        }

        /* Fixture prediction result: wrap text on small screens */
        .fx-pred {
            font-size: 0.78rem;
            line-height: 1.55;
            white-space: normal;
            word-break: break-word;
        }

        /* Date label: white on mobile for legibility */
        .fx-date { color: #ffffff !important; }

        /* Widget labels (e.g. "Match date") — force light colour on mobile */
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span,
        label[data-testid="stWidgetLabel"] { color: #f4f9ff !important; }

        /* Shrink heading levels */
        h3, h4, h5 { font-size: 0.9rem !important; }

        /* Radio group: allow labels to wrap naturally */
        .stRadio [role="radiogroup"] {
            gap: 6px;
        }

        /* Date input: full width, light label, legible text */
        [data-testid="stDateInput"],
        [data-testid="stDateInput"] > div,
        [data-testid="stDateInput"] input {
            width: 100% !important;
            min-width: 0 !important;
            box-sizing: border-box !important;
        }
        [data-testid="stDateInput"] input {
            color: #0d1f2d !important;
            font-size: 1rem !important;
            min-height: 44px !important;
            background-color: #ffffff !important;
            border-radius: 6px !important;
        }
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stDateInput"] [data-baseweb="base-input"] {
            background-color: #ffffff !important;
            border-radius: 6px !important;
        }
        [data-testid="stDateInput"] [data-testid="stWidgetLabel"],
        [data-testid="stDateInput"] [data-testid="stWidgetLabel"] p {
            color: #f4f9ff !important;
            font-size: 0.88rem !important;
        }

        /* Compact wc-result card */
        .wc-result { padding: 0.75rem 0.9rem; }
        .wc-result .big { font-size: 1.1rem; }
        .wc-result .sub { font-size: 0.85rem; }
        .wc-result .wc-xg { font-size: 0.88rem; }
    }

    /* ── Very small screens (iPhone SE etc.) ── */
    @media screen and (max-width: 400px) {
        .main .block-container {
            padding-left: 0.35rem !important;
            padding-right: 0.35rem !important;
        }
        .wc-hero h1 { font-size: 0.98rem; }
    }
</style>
"""


def _inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _streamlit_session_id() -> str | None:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        sid = getattr(ctx, "session_id", None) if ctx else None
        return str(sid) if sid else None
    except Exception:
        return None


def _usage_visitor_label() -> str:
    return wc_usage_log.visitor_token(_streamlit_session_id())


def _record_session_visit_once() -> int:
    """Count one visit per Streamlit browser session; return total visits on disk."""
    if st.session_state.get("_wc_visit_counted"):
        return wc_usage_log.read_visit_count(_ROOT)
    n = wc_usage_log.increment_visit_count(_ROOT)
    st.session_state["_wc_visit_counted"] = True
    return n


def _render_visit_badge(n: int) -> None:
    tip = (
        "Approximate site traffic: one count per browser tab session when the app loads. "
        "Prediction runs are logged under data/wc_prediction_log.jsonl (opaque visitor id)."
    )
    st.markdown(
        f'<div class="wc-visit-badge" title="{html.escape(tip)}">'
        f'<span class="wc-visit-num">{n:,}</span>'
        f'<span class="wc-visit-lbl">Visits</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def _get_predictor(model: str) -> MatchPredictor:
    """Load and cache the predictor so it is not rebuilt on every button click."""
    return MatchPredictor(model=model)


def _effective_actual(fx: dict, live_by_idx: dict[int, str]) -> str | None:
    """Prefer live fetch, else baked-in ``actual`` from ``_FIXTURES``."""
    return live_by_idx.get(fx["_idx"]) or fx.get("actual")


def _pred_scoreline_ints(res: dict) -> tuple[int, int] | None:
    """Integer pred score (team A = home), same rule as the Pred score UI line."""
    if "team_a_expected_goals" not in res or "team_b_expected_goals" not in res:
        return None
    try:
        a = int(float(res["team_a_expected_goals"]))
        b = int(float(res["team_b_expected_goals"]))
    except (TypeError, ValueError):
        return None
    return a, b


def _is_knockout_fixture(fx: dict) -> bool:
    """True for R32 through Final (no draws — must pick a side to advance)."""
    return fx.get("round") in KNOCKOUT_ROUNDS_ORDER


def _res_for_fixture(res: dict, fx: dict | None) -> dict:
    """Attach knockout flag from fixture when missing on stored prediction (older cache)."""
    if fx and _is_knockout_fixture(fx):
        return {**res, "knockout": True}
    return res


def _ko_win_probs(res: dict) -> tuple[float, float]:
    """Home / away win % used for knockout tie-breaks (higher side advances)."""
    pa = float(res.get("team_a_win_probability", 0.5))
    pb = float(res.get("team_b_win_probability", 1.0 - pa))
    return pa, pb


def _ko_pick_side(res: dict) -> str:
    """Knockout tie-break: side with higher win % advances (50/50 → home)."""
    pa, pb = _ko_win_probs(res)
    if pa > pb:
        return "home"
    if pb > pa:
        return "away"
    return "home"


def _ko_tiebreak_used(res: dict) -> bool:
    """True when pred score is level at 90′ so winner comes from win % not goals."""
    if not res.get("knockout"):
        return False
    si = _pred_scoreline_ints(res)
    return si is not None and si[0] == si[1]


def _sign1x2(home_goals: int, away_goals: int) -> int:
    """1 = home win, 0 = draw, -1 = away win (same bucket as home/away goals)."""
    return (home_goals > away_goals) - (home_goals < away_goals)


def _predicted_outcome_max_prob(res: dict) -> str | None:
    """Predicted 1×2 from (p_home, p_draw, p_away). Knockout → home or away only."""
    if "_err" in res:
        return None
    pa_raw = res["team_a_win_probability"]
    if res.get("knockout"):
        return _ko_pick_side(res)
    p_home, p_draw, p_away = _three_way(pa_raw)
    probs = {"home": p_home, "draw": p_draw, "away": p_away}
    max_p = max(probs.values())
    tops = [k for k, v in probs.items() if v >= max_p - 1e-9]
    if len(tops) == 1:
        return tops[0]
    if "draw" in tops:
        return "draw"
    if "home" in tops and "away" in tops:
        return "draw"
    return tops[0]


def _predicted_winner_name(res: dict) -> str:
    """Plain label: home team, away team, or Draw (group stage only)."""
    ta, tb = res["team_a"], res["team_b"]
    ko = res.get("knockout", False)
    si = _pred_scoreline_ints(res)
    if si is not None:
        ha, aa = si
        if ha > aa:
            return ta
        if aa > ha:
            return tb
        if ko:
            return ta if _ko_pick_side(res) == "home" else tb
        return "Draw"
    po = _predicted_outcome_max_prob(res)
    if po == "home":
        return ta
    if po == "away":
        return tb
    return "Draw"


def _prediction_checks(res: dict, actual: str | None) -> dict | None:
    """
    Hierarchical evaluation (user rules):
    1. Exact scoreline → score ✓, GD ✓, result ✓.
    2. Else → score ✗; GD ✓ iff predicted GD equals actual GD; result ✓ iff
       the predicted 1×2 matches FT. When expected goals are present, predicted
       1×2 is derived from the integer pred score (same frame as UI); otherwise
       it is the top outcome among (p_home, p_draw, p_away), with ties resolved
       so symmetric home/away mass does not default to a home win (e.g. 35/30/35 → draw).
    """
    if not actual or "_err" in res:
        return None
    goals = _goals_from_actual(actual)
    if not goals:
        return None
    gh, ga = goals
    act_sign = _sign1x2(gh, ga)
    ko = res.get("knockout", False)

    pred_from_prob = _predicted_outcome_max_prob(res)
    if pred_from_prob is None:
        return None

    score_ints = _pred_scoreline_ints(res)
    if score_ints is None:
        pred_s = {"home": 1, "draw": 0, "away": -1}[pred_from_prob]
        if res.get("knockout") and act_sign == 0:
            result_ok = None
        else:
            result_ok = pred_s == act_sign
        return {
            "result_ok": result_ok,
            "score_ok": None,
            "gd_ok": None,
            "exact": False,
            "show_gd_note": False,
        }

    ph_i, pb_i = score_ints
    exact = ph_i == gh and pb_i == ga
    if exact:
        if ko and act_sign == 0:
            return {
                "result_ok": None,
                "score_ok": True,
                "gd_ok": True,
                "exact": True,
                "show_gd_note": False,
            }
        return {
            "result_ok": True,
            "score_ok": True,
            "gd_ok": True,
            "exact": True,
            "show_gd_note": False,
        }

    gd_ok = (ph_i - pb_i) == (gh - ga)
    if ko:
        if act_sign == 0:
            result_ok = None
        else:
            pred_side = _predicted_outcome_max_prob(res)
            act_side = "home" if act_sign > 0 else "away"
            result_ok = pred_side == act_side
    else:
        result_ok = _sign1x2(ph_i, pb_i) == act_sign
    return {
        "result_ok": result_ok,
        "score_ok": False,
        "gd_ok": gd_ok,
        "exact": False,
        "show_gd_note": gd_ok,
    }


def _checks_rows_html(ch: dict, *, knockout: bool = False) -> str:
    """Three fixed rows: match result, scoreline, goal difference."""
    result_lbl = "Winner to advance" if knockout else "Match result (1×2)"

    def one_row(label: str, ok: bool | None) -> str:
        if ok is None:
            return (
                f'<div style="font-size:0.7rem;color:#8899aa;margin:2px 0">'
                f'<span style="color:#666">—</span> {label} <span style="color:#666">(n/a)</span></div>'
            )
        col = "#7fd4a0" if ok else "#f08080"
        sym, word = ("✓", "correct") if ok else ("✗", "incorrect")
        return (
            f'<div style="font-size:0.7rem;color:#dceaf5;margin:2px 0">'
            f'<span style="color:{col};font-weight:800">{sym}</span> '
            f'<b style="color:{col}">{word}</b> · {label}</div>'
        )

    note = ""
    if ch.get("show_gd_note"):
        note = (
            '<div style="font-size:0.65rem;color:#9cf0ff;margin-top:4px;font-style:italic">'
            "Goal difference matches FT; scoreline does not.</div>"
        )

    return (
        '<div style="margin-top:6px;border-top:1px solid rgba(255,255,255,0.12);padding-top:6px">'
        f'{one_row(result_lbl, ch.get("result_ok"))}'
        f'{one_row("Scoreline", ch.get("score_ok"))}'
        f'{one_row("Goal difference", ch.get("gd_ok"))}'
        f"{note}</div>"
    )


def _goals_from_actual(actual: str | None) -> tuple[int, int] | None:
    """Parse fixture home–away goals from FT text (handles NFKC + common dash characters)."""
    if not actual:
        return None
    s = unicodedata.normalize("NFKC", actual.strip())
    # Unicode dashes / hyphen used by ESPN, docs, or copy-paste
    sep = r"[-–—−‒⁃]"
    parts = [p.strip() for p in re.split(rf"\s*{sep}\s*", s)]
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _ft_winner_name(team_a: str, team_b: str, actual: str) -> str | None:
    """FT 1×2 as team_a name, team_b name, or Draw; None if score not parsed."""
    g = _goals_from_actual(actual)
    if not g:
        return None
    gh, ga = g
    if gh > ga:
        return team_a
    if ga > gh:
        return team_b
    return "Draw"


def _three_way(pa_raw: float, *, knockout: bool = False) -> tuple[float, float, float]:
    """Convert binary win-prob to (p_home, p_draw, p_away). Knockout: no draw mass."""
    if knockout:
        return pa_raw, 0.0, 1.0 - pa_raw
    strength_diff = abs(pa_raw - 0.5)          # 0 = even, 0.5 = maximum mismatch
    p_draw = max(0.08, 0.30 - strength_diff * 0.44)
    p_home = pa_raw * (1.0 - p_draw)
    p_away = (1.0 - pa_raw) * (1.0 - p_draw)
    return p_home, p_draw, p_away


def _fixture_result_html(res: dict, actual: str | None = None, *, fx: dict | None = None) -> str:
    """Predicted winner + pred score + vs-FT check. Knockout: always a side to advance."""
    res = _res_for_fixture(res, fx)
    ko = res.get("knockout", False)
    ta_raw, tb_raw = res["team_a"], res["team_b"]
    pred_lbl = _predicted_winner_name(res)
    pred_esc = html.escape(pred_lbl)
    pred_cls = "fx-pred-winner"

    ch = _prediction_checks(res, actual) if actual else None
    checks_html = _checks_rows_html(ch, knockout=ko) if ch else ""

    ft_line = ""
    if actual:
        ft_lbl = _ft_winner_name(ta_raw, tb_raw, actual)
        if ft_lbl is not None:
            ft_esc = html.escape(ft_lbl)
            ft_cls = "fx-pred-draw" if ft_lbl == "Draw" and not ko else "fx-pred-winner"
            cmp_bit = ""
            if ch is not None and ch.get("result_ok") is not None:
                if ch["result_ok"]:
                    cmp_bit = ' <span style="color:#7fd4a0;font-weight:800">· Match ✓</span>'
                else:
                    cmp_bit = ' <span style="color:#f08080;font-weight:800">· No match ✗</span>'
            ft_hdr = "FT (90 min)" if ko and ft_lbl == "Draw" else "FT winner"
            ft_line = (
                f'<div class="fx-pred-ft">{ft_hdr}: <span class="{ft_cls}">{ft_esc}</span>{cmp_bit}</div>'
            )

    score_bit = ""
    _ps = _pred_scoreline_ints(res)
    if _ps is not None:
        score_bit = (
            f'<span style="color:#ffe08a;font-size:0.7rem">'
            f'Pred score (90′): {_ps[0]}–{_ps[1]}'
            f'</span> &nbsp;'
        )

    tiebreak_bit = ""
    if ko and _ko_tiebreak_used(res):
        pa, pb = _ko_win_probs(res)
        tiebreak_bit = (
            f'<div style="font-size:0.68rem;color:#9cf0ff;margin-top:3px">'
            f'Level at 90′ — tie-break by win %: '
            f'{html.escape(ta_raw)} {pa * 100:.0f}% · '
            f'{html.escape(tb_raw)} {pb * 100:.0f}%</div>'
        )

    head = "To advance" if ko else "Prediction"
    return (
        f'<div class="fx-pred">⚡ '
        f'<div class="fx-pred-main">{head}: <span class="{pred_cls}">{pred_esc}</span></div>'
        f"{tiebreak_bit}"
        f"{ft_line}"
        f'<span style="display:inline-flex;flex-wrap:wrap;gap:2px 4px;align-items:baseline">'
        f"{score_bit}</span>"
        f"<br>{checks_html}</div>"
    )


def _outcome_from_goals(home_goals: int, away_goals: int) -> str:
    """1×2 from home/away goals (team A = home in fixture / pred score display)."""
    s = _sign1x2(home_goals, away_goals)
    return "home" if s > 0 else ("away" if s < 0 else "draw")


def _outcome_from_actual(actual: str | None) -> str | None:
    """'home' | 'draw' | 'away' | None"""
    g = _goals_from_actual(actual)
    if not g:
        return None
    return _outcome_from_goals(g[0], g[1])


def _run_predictions_batch(
    fixtures: list[dict],
    team_set: set,
    model: str,
    *,
    source: str,
) -> None:
    """Run predictions for many fixtures; one disk write at the end."""
    batch: list[tuple[int, dict[str, Any], dict[str, Any] | None]] = []
    for fx in fixtures:
        _run_prediction(fx, team_set, model, source=source, persist_disk=False)
        idx = fx["_idx"]
        if f"res_fx_{idx}" in st.session_state:
            batch.append(
                (idx, st.session_state[f"res_fx_{idx}"], st.session_state.get(f"rsn_fx_{idx}"))
            )
    merge_save_predictions_batch(_ROOT, batch)


def _run_prediction(fx: dict, team_set: set, model: str, *, source: str = "ui", persist_disk: bool = True) -> bool:
    """Run model for a fixture; store prediction + reasoning in session_state. Returns True on success."""
    idx = fx["_idx"]
    try:
        h_ds = _ds(fx["home"], team_set)
        a_ds = _ds(fx["away"], team_set)
        if h_ds and a_ds:
            pred = _get_predictor(model)
            date, tourn = fx["date"], "FIFA World Cup"
            pa = pred.team_a_win_probability(h_ds, a_ds, date, tourn, neutral=True)
            eg_a, eg_b = pred.expected_goals(h_ds, a_ds, date, tourn, neutral=True)
            res: dict = {
                "team_a": h_ds,
                "team_b": a_ds,
                "team_a_win_probability": round(pa, 4),
                "team_b_win_probability": round(1.0 - pa, 4),
                "knockout": _is_knockout_fixture(fx),
            }
            if eg_a is not None:
                res["team_a_expected_goals"] = eg_a
                res["team_b_expected_goals"] = eg_b
            st.session_state[f"res_fx_{idx}"] = res
            st.session_state[f"rsn_fx_{idx}"] = pred.reasoning(h_ds, a_ds, date, tourn, neutral=True)
            if persist_disk:
                merge_save_prediction(_ROOT, idx, res, st.session_state[f"rsn_fx_{idx}"])
            try:
                wc_usage_log.append_prediction_event(
                    _ROOT,
                    visitor=_usage_visitor_label(),
                    source=source,
                    fixture_idx=idx,
                    home=fx["home"],
                    away=fx["away"],
                    model=model,
                    res=res,
                )
            except OSError:
                pass
            return True
        missing = [t for t in (fx["home"], fx["away"]) if not _ds(t, team_set)]
        st.session_state[f"res_fx_{idx}"] = {"_err": f"Not in dataset: {', '.join(missing)}"}
        return False
    except Exception as exc:
        st.session_state[f"res_fx_{idx}"] = {"_err": str(exc)}
        return False


def _render_reasoning_html(rsn: dict) -> str:
    """Build the reasoning HTML block (Elo bars, form badges, H2H table)."""
    a = html.escape(rsn["team_a"])
    b = html.escape(rsn["team_b"])
    elo_a, elo_b = rsn["elo_a"], rsn["elo_b"]

    # Elo bar widths – normalise so the larger value fills ~90 % of the bar
    lo = min(elo_a, elo_b) - 50
    hi = max(elo_a, elo_b) + 50
    span = max(hi - lo, 1)
    bar_a = round((elo_a - lo) / span * 90 + 5)
    bar_b = round((elo_b - lo) / span * 90 + 5)

    def _trend(v: float) -> str:
        if v > 10:
            return f'<span style="color:#22c55e;font-size:0.68rem">↑ +{v:.0f} (90 d)</span>'
        if v < -10:
            return f'<span style="color:#ef4444;font-size:0.68rem">↓ {v:.0f} (90 d)</span>'
        return f'<span style="color:#888;font-size:0.68rem">→ stable</span>'

    def _form_badges(form_list: list) -> str:
        if not form_list:
            return '<span style="color:#666;font-size:0.72rem">No data</span>'
        out = ""
        for r in reversed(form_list):   # most recent on the left
            if r["points"] == 1.0:
                bg, lbl = "#166534", "W"
            elif r["points"] == 0.0:
                bg, lbl = "#7f1d1d", "L"
            else:
                bg, lbl = "#713f12", "D"
            opp = html.escape((r.get("opp") or "?")[:3].upper())
            score = f'{r["gf"]}-{r["ga"]} vs {html.escape(str(r.get("opp","?")))}'
            out += (
                f'<span title="{score}" style="background:{bg};color:#fff;font-size:0.65rem;'
                f'font-weight:800;padding:2px 6px;border-radius:3px;margin-right:3px;'
                f'cursor:default">{lbl}</span>'
                f'<span style="color:#6fa8c0;font-size:0.6rem;margin-right:5px">{opp}</span>'
            )
        return out

    # H2H rows
    h2h_body = ""
    for m in reversed(rsn.get("h2h", [])):
        if (m["home"] == rsn["team_a"] and m["winner"] == "home") or \
           (m["away"] == rsn["team_a"] and m["winner"] == "away"):
            wlbl = f'<span style="color:#22c55e;font-weight:700">{a[:14]} win</span>'
        elif m["winner"] == "draw":
            wlbl = '<span style="color:#eab308;font-weight:700">Draw</span>'
        else:
            wlbl = f'<span style="color:#ef4444;font-weight:700">{b[:14]} win</span>'
        h2h_body += (
            f'<div style="display:flex;flex-wrap:wrap;gap:3px 8px;font-size:0.72rem;padding:3px 0;'
            f'border-bottom:1px solid rgba(255,255,255,0.05)">'
            f'<span style="color:#6fa8c0;min-width:52px">{m["date"][:7]}</span>'
            f'<span style="color:#dceaf5;flex:1">{html.escape(m["home"])} '
            f'<b>{m["home_score"]}–{m["away_score"]}</b> {html.escape(m["away"])}</span>'
            f'{wlbl}</div>'
        )
    if not h2h_body:
        h2h_body = '<div style="color:#666;font-size:0.72rem">No previous meetings in dataset</div>'

    h2h_summary = (
        f'<span style="color:#9cf0c0;font-weight:700">{rsn["h2h_a_wins"]}W</span> '
        f'{rsn["h2h_draws"]}D '
        f'<span style="color:#f08080;font-weight:700">{rsn["h2h_b_wins"]}W</span> '
        f'<span style="color:#888">(last {len(rsn["h2h"])} meetings)</span>'
    )

    return (
        # ── Elo / Form / H2H — responsive 3-col grid (1-col on mobile) ──
        '<div class="rsn-grid">'

        # Elo block
        '<div><div style="color:#ffe08a;font-size:0.65rem;font-weight:700;letter-spacing:0.09em;'
        'margin-bottom:6px">ELO RATING</div>'
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
        f'<span style="color:#eef6fc;font-size:0.72rem;min-width:70px;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap">{a}</span>'
        f'<div style="flex:1;background:rgba(255,255,255,0.1);border-radius:2px;height:8px">'
        f'<div style="width:{bar_a}%;background:#22c55e;height:8px;border-radius:2px"></div></div>'
        f'<span style="color:#9cf0c0;font-weight:700;font-size:0.8rem;min-width:38px">{elo_a}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<span style="color:#eef6fc;font-size:0.72rem;min-width:70px;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap">{b}</span>'
        f'<div style="flex:1;background:rgba(255,255,255,0.1);border-radius:2px;height:8px">'
        f'<div style="width:{bar_b}%;background:#3b82f6;height:8px;border-radius:2px"></div></div>'
        f'<span style="color:#93c5fd;font-weight:700;font-size:0.8rem;min-width:38px">{elo_b}</span>'
        f'</div>'
        f'<div style="margin-top:5px;font-size:0.67rem">'
        f'{a[:10]}: {_trend(rsn["elo_trend_a_90"])}&nbsp;&nbsp;'
        f'{b[:10]}: {_trend(rsn["elo_trend_b_90"])}</div>'
        '</div>'

        # Form block
        '<div><div style="color:#ffe08a;font-size:0.65rem;font-weight:700;letter-spacing:0.09em;'
        'margin-bottom:6px">LAST 5 MATCHES</div>'
        f'<div style="margin-bottom:5px">'
        f'<div style="color:#dceaf5;font-size:0.7rem;margin-bottom:3px">{a}</div>'
        f'{_form_badges(rsn["form_a"])}</div>'
        f'<div style="color:#7aa8c0;font-size:0.65rem;margin-bottom:7px">'
        f'Avg: {rsn["avg_scored_a"]} scored · {rsn["avg_conceded_a"]} conceded (last 10)</div>'
        f'<div style="margin-bottom:5px">'
        f'<div style="color:#dceaf5;font-size:0.7rem;margin-bottom:3px">{b}</div>'
        f'{_form_badges(rsn["form_b"])}</div>'
        f'<div style="color:#7aa8c0;font-size:0.65rem">'
        f'Avg: {rsn["avg_scored_b"]} scored · {rsn["avg_conceded_b"]} conceded (last 10)</div>'
        '</div>'

        # H2H block
        '<div><div style="color:#ffe08a;font-size:0.65rem;font-weight:700;letter-spacing:0.09em;'
        'margin-bottom:6px">HEAD TO HEAD</div>'
        f'<div style="font-size:0.72rem;margin-bottom:5px">{a[:12]} {h2h_summary}</div>'
        f'{h2h_body}'
        '</div>'

        '</div>'
    )


def _render_fixture_row(
    fx: dict,
    team_set: set,
    model: str,
    show_date: bool = False,
    tab_prefix: str = "tab",
    live_by_idx: dict[int, str] | None = None,
) -> None:
    """Render one fixture row: match+venue (full-width) then button | result columns."""
    live_by_idx = live_by_idx or {}
    idx = fx["_idx"]
    home, away = fx["home"], fx["away"]
    actual = _effective_actual(fx, live_by_idx)
    date_bit = (
        f'<span class="fx-date">{fx["date"][5:]} &nbsp;</span>'
        if show_date else ""
    )

    # Full-width match name + venue — always visible on every screen size
    st.markdown(
        f'<div style="padding:5px 0 2px">{date_bit}'
        f'<span style="color:#eef6fc;font-weight:600">'
        f'{html.escape(home)} <span style="color:#5a90b0">vs</span> {html.escape(away)}'
        f'</span>'
        f'<div style="color:#7aa8c0;font-size:0.7rem;font-style:italic;margin-top:2px">'
        f'📍 {html.escape(fx["venue"])}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 2 columns: action (button or FT score) | prediction result
    c_btn, c_res = st.columns([1.5, 4])

    with c_btn:
        if actual:
            st.markdown(
                f'<div style="color:#ffe08a;font-weight:700;font-size:0.82rem;padding:7px 0">'
                f'FT &nbsp;{actual}</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button("Predict ▶", key=f"btn_{tab_prefix}_{idx}", use_container_width=True):
                with st.spinner("Predicting…"):
                    ok = _run_prediction(fx, team_set, model, source="fixture_button")
                stored = st.session_state.get(f"res_fx_{idx}")
                if ok and stored and "_err" not in stored:
                    disp = _res_for_fixture(stored, fx)
                    label = "To advance" if disp.get("knockout") else "Prediction"
                    st.toast(f"{label}: {_predicted_winner_name(disp)}")

    with c_res:
        stored = st.session_state.get(f"res_fx_{idx}")
        if stored:
            if "_err" in stored:
                st.markdown(
                    f'<div style="color:#f08080;font-size:0.75rem;padding:5px 0">'
                    f'⚠️ {html.escape(stored["_err"])}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(_fixture_result_html(stored, actual=actual, fx=fx), unsafe_allow_html=True)

    # Reasoning expander — full width, below the row
    rsn = st.session_state.get(f"rsn_fx_{idx}")
    if rsn:
        with st.expander("Data Behind this Prediction", expanded=False):
            st.markdown(_render_reasoning_html(rsn), unsafe_allow_html=True)


def _render_knockout_fixtures(
    team_set: set,
    fixture_model: str,
    live_by_idx: dict[int, str],
    ko_fixtures: list[dict],
    ko_cache: dict[str, Any],
) -> None:
    ko_by_round: dict[str, list[dict]] = {}
    for fx in ko_fixtures:
        ko_by_round.setdefault(fx["round"], []).append(fx)

    st.markdown(
        '<div style="color:#dceaf5;font-size:0.88rem;margin-bottom:10px">'
        'Knockout pairings load from ESPN when teams are known. '
        'Complete rounds are cached locally (<code>data/wc_knockout_schedule.json</code>).</div>',
        unsafe_allow_html=True,
    )

    display_rounds = [r for r in KNOCKOUT_ROUNDS_ORDER if r in ROUNDS_FROM_R16 or ko_by_round.get(r)]
    if "Round of 32" in ko_by_round and "Round of 32" not in display_rounds:
        display_rounds = ["Round of 32"] + list(display_rounds)

    for rnd in display_rounds:
        have, exp, complete = round_schedule_status(ko_cache, rnd)
        st.markdown(
            f'<div style="color:#ffe08a;font-weight:700;font-size:0.78rem;'
            f'letter-spacing:0.09em;margin:10px 0 4px;text-transform:uppercase">'
            f'{html.escape(rnd)}'
            f'<span style="color:#8bb8d0;font-weight:600;margin-left:8px;font-size:0.68rem">'
            f'({have}/{exp} pairings)</span></div>',
            unsafe_allow_html=True,
        )

        resolved = ko_by_round.get(rnd) or []
        if resolved:
            for fx in resolved:
                _render_fixture_row(
                    fx, team_set, fixture_model, show_date=True, tab_prefix="ko", live_by_idx=live_by_idx
                )
            unplayed = [fx for fx in resolved if not _effective_actual(fx, live_by_idx)]
            if unplayed and st.button(
                f"Predict all {rnd} ({len(unplayed)} unplayed)",
                key=f"pred_all_ko_{rnd.replace(' ', '_')}",
            ):
                with st.spinner(f"Predicting {len(unplayed)} matches…"):
                    _run_predictions_batch(unplayed, team_set, fixture_model, source="predict_all_ko")
                st.toast(f"Predictions saved for {len(unplayed)} {rnd} match(es)")

        if not complete and not resolved:
            pending = [k for k in _KO_FIXTURES if k["round"] == rnd]
            for ko in pending:
                st.markdown(
                    f'<div style="padding:3px 8px;border-bottom:1px solid rgba(255,255,255,0.06);'
                    f'color:#6a8aa0;font-size:0.8rem">'
                    f'<span style="color:#5a8098">{ko["date"][5:]} &nbsp;</span>'
                    f'{html.escape(ko["label"])}'
                    f'<span style="color:#4a6a80;font-style:italic;font-size:0.72rem">'
                    f' &nbsp;· 📍 {html.escape(ko["venue"])} · awaiting teams</span></div>',
                    unsafe_allow_html=True,
                )
        elif not complete and resolved:
            st.caption(f"{exp - have} more {rnd} pairing(s) will appear when earlier knockout games finish.")


def _show_fixtures_tab(
    team_set: set,
    fixture_model: str,
    live_by_idx: dict[int, str],
    ko_fixtures: list[dict],
    ko_cache: dict[str, Any],
) -> None:
    """Render the Fixtures tab: group picker (persists across reruns) + Knockout."""
    groups = sorted({f["group"] for f in _FIXTURES})
    view_options = [f"Group {g}" for g in groups] + ["🔄 Knockout"]
    fixtures_view = st.selectbox(
        "Browse fixtures",
        view_options,
        key="wc_fixtures_view",
    )

    if fixtures_view == "🔄 Knockout":
        _render_knockout_fixtures(team_set, fixture_model, live_by_idx, ko_fixtures, ko_cache)
        return

    grp = fixtures_view.replace("Group ", "")
    grp_fixtures = [f for f in _FIXTURES if f["group"] == grp]
    grp_teams = sorted({t for f in grp_fixtures for t in (f["home"], f["away"])})
    st.markdown(
        f'<div style="color:#ffe08a;font-weight:700;font-size:0.8rem;'
        f'letter-spacing:0.1em;margin-bottom:6px">GROUP {grp} — {" · ".join(grp_teams)}</div>',
        unsafe_allow_html=True,
    )

    for fx in grp_fixtures:
        _render_fixture_row(fx, team_set, fixture_model, show_date=True, tab_prefix="tab2", live_by_idx=live_by_idx)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    unplayed = [fx for fx in grp_fixtures if not _effective_actual(fx, live_by_idx)]
    if unplayed and st.button(f"Predict all Group {grp} matches", key=f"pred_all_{grp}"):
        with st.spinner(f"Predicting {len(unplayed)} matches…"):
            _run_predictions_batch(unplayed, team_set, fixture_model, source="predict_all_group")
        st.toast(f"Predictions saved for Group {grp}")


def _accuracy_eval_rows(active_fixtures: list[dict], live_by_idx: dict[int, str]) -> list[dict[str, Any]]:
    """Fixtures with FT + stored prediction + check dict (same set as accuracy hero)."""
    out: list[dict[str, Any]] = []
    for fx in active_fixtures:
        actual = _effective_actual(fx, live_by_idx)
        if not actual:
            continue
        stored = st.session_state.get(f"res_fx_{fx['_idx']}")
        if not stored or "_err" in stored:
            continue
        res = _res_for_fixture(stored, fx)
        ch = _prediction_checks(res, actual)
        if ch is None:
            continue
        out.append({"fx": fx, "stored": stored, "ch": ch, "actual": actual})
    return out


def _accuracy_split_ok_bad(
    rows: list[dict[str, Any]], kind: Literal["result", "score", "gd"]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if kind == "result":
        ok = [r for r in rows if r["ch"].get("result_ok") is True]
        bad = [r for r in rows if r["ch"].get("result_ok") is False]
        return ok, bad
    if kind == "score":
        sub = [r for r in rows if r["ch"].get("score_ok") is not None]
        ok = [r for r in sub if r["ch"].get("score_ok")]
        bad = [r for r in sub if not r["ch"].get("score_ok")]
        return ok, bad
    sub = [r for r in rows if r["ch"].get("gd_ok") is not None]
    ok = [r for r in sub if r["ch"].get("gd_ok")]
    bad = [r for r in sub if not r["ch"].get("gd_ok")]
    return ok, bad


def _accuracy_match_line_html(r: dict[str, Any]) -> str:
    fx, stored, actual = r["fx"], r["stored"], r["actual"]
    ps = _pred_scoreline_ints(stored)
    pred_sc = f"{ps[0]}–{ps[1]}" if ps is not None else "—"
    stage = fx.get("group")
    if stage is None:
        stage = fx.get("round", "KO")
    return (
        f'{html.escape(fx["date"])} · {html.escape(str(stage))} · '
        f'{html.escape(fx["home"])} vs {html.escape(fx["away"])} · '
        f'Pred {html.escape(pred_sc)} · FT {html.escape(actual)}'
    )


def _accuracy_expander_colored(rows: list[dict[str, Any]], kind: Literal["result", "score", "gd"]) -> None:
    ok, bad = _accuracy_split_ok_bad(rows, kind)
    parts: list[str] = ['<div style="font-size:0.72rem;line-height:1.45">']
    if ok:
        parts.append(
            '<div style="font-weight:700;margin:0 0 6px 0;color:#7fd4a0">Correct</div>'
        )
        for r in ok:
            parts.append(
                f'<div style="color:#7fd4a0;margin:2px 0">{_accuracy_match_line_html(r)}</div>'
            )
    if bad:
        parts.append(
            '<div style="font-weight:700;margin:12px 0 6px 0;color:#f08080">Wrong</div>'
        )
        for r in bad:
            parts.append(
                f'<div style="color:#f08080;margin:2px 0">{_accuracy_match_line_html(r)}</div>'
            )
    if not ok and not bad:
        parts.append('<div style="color:#8899aa">—</div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _load_app_context(team_set: set, today: datetime.date) -> dict[str, Any]:
    """Load scores + knockout schedule once per session (avoids ~8s ESPN refetch every click)."""
    if st.session_state.get("_wc_ctx_loaded"):
        return st.session_state["_wc_ctx"]

    with st.spinner("Loading knockout schedule, scores and predictions…"):
        _get_predictor("xgboost")
        ko_fixtures, ko_cache = get_resolved_knockout_fixtures(
            _ROOT, today, idx_base=_KO_IDX_BASE
        )
        active_fixtures = _FIXTURES + ko_fixtures

        dates = sorted({datetime.date.fromisoformat(f["date"]) for f in active_fixtures})
        first, last = dates[0], dates[-1]
        picker_default = max(first, min(last, today))

        ymds = dates_up_to_today_inclusive(first.isoformat(), last.isoformat(), today)

        live_disk, preds_disk, rsn_disk = load_triple(_ROOT)
        for _idx, _res in preds_disk.items():
            st.session_state.setdefault(f"res_fx_{_idx}", _res)
        for _idx, _rsn in rsn_disk.items():
            st.session_state.setdefault(f"rsn_fx_{_idx}", _rsn)

        api_live = fetch_live_scores_by_fixture_idx(active_fixtures, list(ymds))
        live_by_idx = {**live_disk, **api_live}
        merge_save_live_ft(_ROOT, live_by_idx)

        if not st.session_state.get("_wc_auto_pred_done"):
            missing_pred = [
                fx
                for fx in active_fixtures
                if _effective_actual(fx, live_by_idx)
                and not st.session_state.get(f"res_fx_{fx['_idx']}")
            ]
            if missing_pred:
                _run_predictions_batch(missing_pred, team_set, "xgboost", source="auto_finished")
            st.session_state["_wc_auto_pred_done"] = True

    ctx = {
        "ko_fixtures": ko_fixtures,
        "ko_cache": ko_cache,
        "active_fixtures": active_fixtures,
        "live_by_idx": live_by_idx,
        "first": first,
        "last": last,
        "picker_default": picker_default,
    }
    st.session_state["_wc_ctx"] = ctx
    st.session_state["_wc_ctx_loaded"] = True
    return ctx


def _render_accuracy_hero(active_fixtures: list[dict], live_by_idx: dict[int, str]) -> None:
    """Predictions-so-far summary; open MATCH RESULT / EXACT SCORE / GOAL DIFFERENCE for green/red lists."""
    rows = _accuracy_eval_rows(active_fixtures, live_by_idx)
    if not rows:
        st.markdown(
            '<div class="wc-acc-hero">'
            '<div style="width:100%;color:#ffe08a;font-size:0.78rem;font-weight:700;'
            'letter-spacing:0.09em;text-transform:uppercase;margin-bottom:8px">'
            'Predictions so far</div>'
            '<div class="acc-sub" style="text-align:center;padding:10px">'
            "<b>Live FT scores</b> load from the web for dates up to today. "
            "Finished games get automatic predictions; "
            "<b>match result</b>, <b>scoreline</b>, and <b>goal difference</b> checks appear here.</div></div>",
            unsafe_allow_html=True,
        )
        return

    n = len(rows)
    r_hit = sum(1 for r in rows if r["ch"].get("result_ok"))
    score_sub = [r for r in rows if r["ch"].get("score_ok") is not None]
    s_den = len(score_sub)
    s_hit = sum(1 for r in score_sub if r["ch"].get("score_ok")) if s_den else 0
    gd_sub = [r for r in rows if r["ch"].get("gd_ok") is not None]
    gd_den = len(gd_sub)
    gd_hit = sum(1 for r in gd_sub if r["ch"].get("gd_ok")) if gd_den else 0

    acc_r = r_hit / n * 100
    col_r = "#7fd4a0" if acc_r >= 60 else "#f0c060" if acc_r >= 40 else "#f08080"
    if s_den:
        acc_s = s_hit / s_den * 100
        col_s = "#7fd4a0" if acc_s >= 20 else "#f0c060" if acc_s >= 8 else "#f08080"
        score_block = (
            f'<div class="acc-block">'
            f'<div class="acc-val" style="color:{col_s}">{s_hit}/{s_den}</div>'
            f'<div class="acc-lbl">Exact Score</div>'
            f'<div class="acc-sub">{acc_s:.0f}% accuracy</div></div>'
        )
    else:
        score_block = (
            '<div class="acc-block">'
            '<div class="acc-val" style="color:#6b7f93">—</div>'
            '<div class="acc-lbl">Exact Score</div>'
            '<div class="acc-sub">Pending predictions</div></div>'
        )

    if gd_den:
        acc_g = gd_hit / gd_den * 100
        col_g = "#7fd4a0" if acc_g >= 35 else "#f0c060" if acc_g >= 20 else "#f08080"
        gd_block = (
            f'<div class="acc-block">'
            f'<div class="acc-val" style="color:{col_g}">{gd_hit}/{gd_den}</div>'
            f'<div class="acc-lbl">Goal Difference</div>'
            f'<div class="acc-sub">{acc_g:.0f}% accuracy</div></div>'
        )
    else:
        gd_block = (
            '<div class="acc-block">'
            '<div class="acc-val" style="color:#6b7f93">—</div>'
            '<div class="acc-lbl">Goal Difference</div>'
            '<div class="acc-sub">See Exact Score</div></div>'
        )

    def _card(val: str, lbl: str, sub: str, col: str) -> str:
        return (
            f'<div class="acc-block">'
            f'<div class="acc-val" style="color:{col}">{val}</div>'
            f'<div class="acc-lbl">{lbl}</div>'
            f'<div class="acc-sub">{sub}</div>'
            f"</div>"
        )

    st.markdown(
        '<div class="wc-acc-hero">'
        '<div style="width:100%;color:#ffe08a;font-size:0.78rem;font-weight:700;'
        'letter-spacing:0.09em;text-transform:uppercase;margin-bottom:8px">'
        'Predictions so far</div>'
        f'{_card(f"{r_hit}/{n}", "Match Result", f"{acc_r:.0f}% accuracy", col_r)}'
        f"{score_block}"
        f"{gd_block}"
        "</div>",
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        with st.expander("MATCH RESULT", expanded=False):
            _accuracy_expander_colored(rows, "result")
    with col_b:
        with st.expander("EXACT SCORE", expanded=False):
            if s_den:
                _accuracy_expander_colored(rows, "score")
            else:
                st.caption("Predictions need expected goals before exact score can be judged.")
    with col_c:
        with st.expander("GOAL DIFFERENCE", expanded=False):
            if gd_den:
                _accuracy_expander_colored(rows, "gd")
            else:
                st.caption("Predictions need expected goals before goal difference can be judged.")



def main() -> None:
    st.set_page_config(
        page_title="FIFA 2026 — Predictor",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()
    _render_visit_badge(_record_session_visit_once())

    # Build team set (used by _ds() for name normalisation)
    _matches = load_completed_matches_chronological(
        _ROOT / "data" / "dataset_A_international_matches.csv"
    )
    team_set = {m["home_team"] for m in _matches} | {m["away_team"] for m in _matches}

    _today = datetime.date.today()

    st.markdown(
        '<div class="wc-hero"><div class="wc-badge">USA · CAN · MEX 2026</div>'
        '<div style="display:flex;align-items:center;gap:14px;flex-wrap:nowrap">'
        f'{_ball_img_tag(60)}'
        '<h1 style="margin:0;font-family:\'Segoe UI\',system-ui,sans-serif;'
        'font-size:1.65rem;font-weight:700;letter-spacing:0.04em;'
        'color:#fff8e8;text-shadow:0 1px 4px rgba(0,0,0,0.45)">'
        'FIFA World Cup 2026 — Match Predictor</h1>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    ctx = _load_app_context(team_set, _today)

    ko_fixtures = ctx["ko_fixtures"]
    ko_cache = ctx["ko_cache"]
    active_fixtures = ctx["active_fixtures"]
    live_by_idx = ctx["live_by_idx"]
    _first = ctx["first"]
    _last = ctx["last"]
    _picker_default = ctx["picker_default"]

    _render_accuracy_hero(active_fixtures, live_by_idx)

    nav1, nav2 = st.columns([5, 1])
    with nav2:
        if st.button("Refresh scores", key="wc_refresh_ctx", use_container_width=True):
            st.session_state.pop("_wc_ctx_loaded", None)
            st.session_state.pop("_wc_ctx", None)
            st.rerun()
    with nav1:
        main_view = st.radio(
            "Section",
            ["⚽  Match predictor", "📋  Fixtures & schedule"],
            horizontal=True,
            key="wc_main_view",
            label_visibility="collapsed",
        )

    if main_view.startswith("⚽"):
        pred_model = "xgboost"
        sel_date = st.date_input(
            "Match date",
            value=_picker_default,
            min_value=_first,
            max_value=_last,
            key="pred_date",
        )

        date_str = sel_date.isoformat()
        day_fx = [f for f in active_fixtures if f["date"] == date_str]

        if not day_fx:
            st.info(
                f"No matches scheduled for **{sel_date.strftime('%B %d, %Y')}**. "
                "Try another date — group stage Jun 11–27, knockout Jun 28–Jul 19."
            )
        else:
            day_groups = sorted({f["group"] for f in day_fx if f.get("group")})
            day_rounds = sorted({f["round"] for f in day_fx if f.get("round")})
            stage_bits: list[str] = []
            if day_groups:
                stage_bits.append(f'Groups {", ".join(day_groups)}')
            if day_rounds:
                stage_bits.append(", ".join(day_rounds))
            stage_line = " — ".join(stage_bits) if stage_bits else "Knockout"
            st.markdown(
                f'<div style="color:#dceaf5;font-size:0.88rem;margin-bottom:10px">'
                f'<b>{len(day_fx)}</b> match{"es" if len(day_fx) > 1 else ""} on '
                f'<b style="color:#ffe08a">{sel_date.strftime("%B %d, %Y")}</b> '
                f'— {html.escape(stage_line)}</div>',
                unsafe_allow_html=True,
            )

            # Column header (prediction column only — match/venue is now full-width)
            _, hc_pred = st.columns([1.5, 4])
            hc_pred.markdown(
                '<div class="pred-col-header" style="color:#ffe08a;font-size:0.68rem;font-weight:700;'
                'letter-spacing:0.08em;padding-bottom:4px;'
                'border-bottom:1px solid rgba(255,210,120,0.3)">Prediction</div>',
                unsafe_allow_html=True,
            )

            for fx in day_fx:
                _render_fixture_row(
                    fx, team_set, pred_model, show_date=False, tab_prefix="tab1", live_by_idx=live_by_idx
                )

            # Predict all today's matches
            unplayed_today = [fx for fx in day_fx if not _effective_actual(fx, live_by_idx)]
            if unplayed_today:
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                if st.button(
                    f"Predict all {len(unplayed_today)} match{'es' if len(unplayed_today) > 1 else ''} today",
                    type="primary",
                    key="pred_all_today",
                ):
                    with st.spinner(f"Predicting {len(unplayed_today)} matches…"):
                        _run_predictions_batch(unplayed_today, team_set, pred_model, source="predict_all_today")
                    st.toast(f"Predictions saved for {len(unplayed_today)} match(es) today")

    else:
        st.markdown(
            '<p style="color:#dceaf5;font-size:0.88rem;margin:0 0 6px 0">'
            'All 72 group-stage matches + knockout schedule. '
            'Click <strong style="color:#ffe08a">Predict ▶</strong> on any unplayed match, '
            'or use <em>Predict all</em> to fill a whole group at once.</p>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        _show_fixtures_tab(team_set, "xgboost", live_by_idx, ko_fixtures, ko_cache)


if __name__ == "__main__":
    main()
