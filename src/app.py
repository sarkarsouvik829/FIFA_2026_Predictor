"""Streamlit UI: match prediction + 2026 World Cup fixtures browser."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import datetime

import streamlit as st

from src.matches_common import load_completed_matches_chronological
from src.predict_match import MatchPredictor
from src.wc_disk_cache import load_triple, merge_save_live_ft, merge_save_prediction
from src.wc_live_scores import dates_up_to_today_inclusive, fetch_live_scores_by_fixture_idx

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

# Attach a flat index to every fixture so result keys are stable across both tabs
for _i, _f in enumerate(_FIXTURES):
    _f["_idx"] = _i

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


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
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
        .wc-hero h1 { font-size: 1.1rem; letter-spacing: 0.02em; }
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

        /* Shrink heading levels */
        h3, h4, h5 { font-size: 0.9rem !important; }

        /* Radio group: allow labels to wrap naturally */
        .stRadio [role="radiogroup"] {
            gap: 6px;
        }

        /* Date input: full width */
        [data-testid="stDateInput"] > div { width: 100% !important; }

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


@st.cache_resource(show_spinner=False)
def _get_predictor(model: str) -> MatchPredictor:
    """Load and cache the predictor so it is not rebuilt on every button click."""
    return MatchPredictor(model=model)


def _effective_actual(fx: dict, live_by_idx: dict[int, str]) -> str | None:
    """Prefer live fetch, else baked-in ``actual`` from ``_FIXTURES``."""
    return live_by_idx.get(fx["_idx"]) or fx.get("actual")


def _predicted_outcome_max_prob(res: dict) -> str | None:
    """Predicted 1×2 outcome = argmax(home win %, draw %, away win %) from three-way split."""
    if "_err" in res:
        return None
    pa_raw = res["team_a_win_probability"]
    p_home, p_draw, p_away = _three_way(pa_raw)
    probs = {"home": p_home, "draw": p_draw, "away": p_away}
    best = "home"
    for k in ("draw", "away"):
        if probs[k] > probs[best]:
            best = k
    return best


def _prediction_checks(res: dict, actual: str | None) -> dict | None:
    """
    Hierarchical evaluation (user rules):
    1. Exact scoreline → score ✓, GD ✓, result ✓.
    2. Else → score ✗; GD ✓ iff predicted GD equals actual GD; result ✓ iff
       argmax(p_home, p_draw, p_away) matches the true 1×2 outcome.
    """
    if not actual or "_err" in res:
        return None
    goals = _goals_from_actual(actual)
    if not goals:
        return None
    gh, ga = goals
    true_out = _outcome_from_actual(actual)
    if not true_out:
        return None

    ph = res.get("team_a_expected_goals")
    pb = res.get("team_b_expected_goals")
    pred_max = _predicted_outcome_max_prob(res)
    if pred_max is None:
        return None

    if ph is None or pb is None:
        return {
            "result_ok": pred_max == true_out,
            "score_ok": None,
            "gd_ok": None,
            "exact": False,
            "show_gd_note": False,
        }

    ph_i, pb_i = int(ph), int(pb)
    exact = ph_i == gh and pb_i == ga
    if exact:
        return {
            "result_ok": True,
            "score_ok": True,
            "gd_ok": True,
            "exact": True,
            "show_gd_note": False,
        }

    gd_ok = (ph_i - pb_i) == (gh - ga)
    return {
        "result_ok": pred_max == true_out,
        "score_ok": False,
        "gd_ok": gd_ok,
        "exact": False,
        "show_gd_note": gd_ok,
    }


def _checks_rows_html(ch: dict) -> str:
    """Three fixed rows: match result, scoreline, goal difference."""

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
        f'{one_row("Match result (1×2)", ch.get("result_ok"))}'
        f'{one_row("Scoreline", ch.get("score_ok"))}'
        f'{one_row("Goal difference", ch.get("gd_ok"))}'
        f"{note}</div>"
    )


def _goals_from_actual(actual: str | None) -> tuple[int, int] | None:
    if not actual:
        return None
    parts = [x.strip() for x in re.split(r"\s*[-–—]\s*", actual.strip())]
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _three_way(pa_raw: float) -> tuple[float, float, float]:
    """Convert binary win-prob to (p_home, p_draw, p_away) using context-sensitive draw rate.

    Draw probability is highest (~30 %) for evenly matched sides and falls
    toward ~8 % as the mismatch grows — matching WC group-stage empirics.
    The binary classifier implicitly conditions on a result happening, so we
    rescale both win probs by (1 - p_draw) after computing the draw share.
    """
    strength_diff = abs(pa_raw - 0.5)          # 0 = even, 0.5 = maximum mismatch
    p_draw = max(0.08, 0.30 - strength_diff * 0.44)
    p_home = pa_raw * (1.0 - p_draw)
    p_away = (1.0 - pa_raw) * (1.0 - p_draw)
    return p_home, p_draw, p_away


def _fixture_result_html(res: dict, actual: str | None = None) -> str:
    """Three-way probabilities + pred score + three evaluation rows vs FT."""
    a = html.escape(res["team_a"])
    b = html.escape(res["team_b"])
    pa_raw = res["team_a_win_probability"]
    p_home, p_draw, p_away = _three_way(pa_raw)

    checks_html = ""
    ch = _prediction_checks(res, actual) if actual else None
    if ch:
        checks_html = _checks_rows_html(ch)

    score_bit = ""
    if "team_a_expected_goals" in res:
        score_bit = (f'<span style="color:#ffe08a;font-size:0.7rem">'
                     f'Pred score: {int(res["team_a_expected_goals"])}–{int(res["team_b_expected_goals"])}'
                     f'</span> &nbsp;')

    line = (
        f'<span style="white-space:nowrap"><b style="color:#9cf0c0">{p_home*100:.0f}%</b> {a}</span>'
        f' <span style="color:#aaa;white-space:nowrap">| Draw <b>{p_draw*100:.0f}%</b> |</span>'
        f' <span style="white-space:nowrap">{b} <b style="color:#9cf0c0">{p_away*100:.0f}%</b></span>'
    )
    return (
        f'<div class="fx-pred">⚡ '
        f'<span style="display:inline-flex;flex-wrap:wrap;gap:2px 4px;align-items:baseline">'
        f'{line}</span>'
        f'<br>{score_bit}{checks_html}</div>'
    )


def _outcome_from_actual(actual: str | None) -> str | None:
    """'home' | 'draw' | 'away' | None"""
    if not actual:
        return None
    parts = [x.strip() for x in re.split(r"\s*[-–—]\s*", actual.strip())]
    if len(parts) != 2:
        return None
    try:
        gh, ga = int(parts[0]), int(parts[1])
        return "home" if gh > ga else ("away" if ga > gh else "draw")
    except ValueError:
        return None


def _run_prediction(fx: dict, team_set: set, model: str) -> None:
    """Run model for a fixture; store prediction + reasoning in session_state."""
    idx = fx["_idx"]
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
        }
        if eg_a is not None:
            res["team_a_expected_goals"] = eg_a
            res["team_b_expected_goals"] = eg_b
        st.session_state[f"res_fx_{idx}"] = res
        st.session_state[f"rsn_fx_{idx}"] = pred.reasoning(h_ds, a_ds, date, tourn, neutral=True)
        merge_save_prediction(_ROOT, idx, res, st.session_state[f"rsn_fx_{idx}"])
    else:
        missing = [t for t in (fx["home"], fx["away"]) if not _ds(t, team_set)]
        st.session_state[f"res_fx_{idx}"] = {"_err": f"Not in dataset: {', '.join(missing)}"}


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
                with st.spinner(""):
                    _run_prediction(fx, team_set, model)

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
                st.markdown(_fixture_result_html(stored, actual=actual), unsafe_allow_html=True)

    # Reasoning expander — full width, below the row
    rsn = st.session_state.get(f"rsn_fx_{idx}")
    if rsn:
        with st.expander("Data Behind this Prediction", expanded=False):
            st.markdown(_render_reasoning_html(rsn), unsafe_allow_html=True)


def _show_fixtures_tab(team_set: set, fixture_model: str, live_by_idx: dict[int, str]) -> None:
    """Render the Fixtures tab: group tabs A-L + Knockout."""
    groups = sorted({f["group"] for f in _FIXTURES})  # A..L
    tab_labels = [f"Group {g}" for g in groups] + ["🔄 Knockout"]
    tabs = st.tabs(tab_labels)

    # Group tabs
    for ti, grp in enumerate(groups):
        with tabs[ti]:
            grp_fixtures = [f for f in _FIXTURES if f["group"] == grp]
            grp_teams = sorted({t for f in grp_fixtures for t in (f["home"], f["away"])})
            st.markdown(
                f'<div style="color:#ffe08a;font-weight:700;font-size:0.8rem;'
                f'letter-spacing:0.1em;margin-bottom:6px">GROUP {grp} — {" · ".join(grp_teams)}</div>',
                unsafe_allow_html=True,
            )

            for fx in grp_fixtures:
                _render_fixture_row(fx, team_set, fixture_model, show_date=True, tab_prefix="tab2", live_by_idx=live_by_idx)

            # Quick "Predict all" button for this group
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            unplayed = [fx for fx in grp_fixtures if not _effective_actual(fx, live_by_idx)]
            if unplayed and st.button(f"Predict all Group {grp} matches", key=f"pred_all_{grp}"):
                for fx in unplayed:
                    _run_prediction(fx, team_set, fixture_model)
                st.rerun()

    # Knockout tab
    with tabs[-1]:
        st.markdown(
            '<div style="color:#dceaf5;font-size:0.88rem;margin-bottom:10px">'
            'Knockout fixtures are determined by group stage results. '
            'Teams shown as TBD until groups conclude.</div>',
            unsafe_allow_html=True,
        )
        cur_round = None
        for ko in _KO_FIXTURES:
            if ko["round"] != cur_round:
                cur_round = ko["round"]
                st.markdown(
                    f'<div style="color:#ffe08a;font-weight:700;font-size:0.78rem;'
                    f'letter-spacing:0.09em;margin:10px 0 4px;text-transform:uppercase">'
                    f'{html.escape(cur_round)}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div style="padding:3px 8px;border-bottom:1px solid rgba(255,255,255,0.06);'
                f'color:#8bb8d0;font-size:0.8rem">'
                f'<span style="color:#6fa8c0">{ko["date"][5:]} &nbsp;</span>'
                f'{html.escape(ko["label"])}'
                f'<span style="color:#4a7a98;font-style:italic;font-size:0.72rem">'
                f' &nbsp;· 📍 {html.escape(ko["venue"])}</span></div>',
                unsafe_allow_html=True,
            )


def _accuracy_hero_html(live_by_idx: dict[int, str]) -> str:
    """Summary: match result, scoreline, goal-difference accuracy (hierarchical rules)."""
    checks_list: list[dict] = []
    for fx in _FIXTURES:
        actual = _effective_actual(fx, live_by_idx)
        stored = st.session_state.get(f"res_fx_{fx['_idx']}")
        if not stored or "_err" in stored:
            continue
        ch = _prediction_checks(stored, actual)
        if ch is None:
            continue
        checks_list.append(ch)

    if not checks_list:
        return (
            '<div class="wc-acc-hero">'
            '<div style="width:100%;color:#ffe08a;font-size:0.78rem;font-weight:700;'
            'letter-spacing:0.09em;text-transform:uppercase;margin-bottom:8px">'
            'Predictions so far</div>'
            '<div class="acc-sub" style="text-align:center;padding:10px">'
            "<b>Live FT scores</b> load from the web for dates up to today. "
            "Finished games get automatic predictions; "
            "<b>match result</b>, <b>scoreline</b>, and <b>goal difference</b> checks appear here.</div></div>"
        )

    n = len(checks_list)
    r_hit = sum(1 for c in checks_list if c.get("result_ok"))
    score_eval = [c for c in checks_list if c.get("score_ok") is not None]
    s_den = len(score_eval)
    s_hit = sum(1 for c in score_eval if c.get("score_ok")) if s_den else 0
    gd_eval = [c for c in checks_list if c.get("gd_ok") is not None]
    gd_den = len(gd_eval)
    gd_hit = sum(1 for c in gd_eval if c.get("gd_ok")) if gd_den else 0

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
            f'<div class="acc-lbl">Exact Score</div>'
            f'<div class="acc-sub">Pending predictions</div></div>'
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

    return (
        '<div class="wc-acc-hero">'
        '<div style="width:100%;color:#ffe08a;font-size:0.78rem;font-weight:700;'
        'letter-spacing:0.09em;text-transform:uppercase;margin-bottom:8px">'
        'Predictions so far</div>'
        f'<div class="acc-block">'
        f'<div class="acc-val" style="color:{col_r}">{r_hit}/{n}</div>'
        f'<div class="acc-lbl">Match Result</div>'
        f'<div class="acc-sub">{acc_r:.0f}% accuracy</div>'
        f"</div>"
        f"{score_block}"
        f"{gd_block}"
        "</div>"
    )


def main() -> None:
    st.set_page_config(
        page_title="FIFA 2026 — Predictor",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()

    # Build team set (used by _ds() for name normalisation)
    _matches = load_completed_matches_chronological(
        _ROOT / "data" / "dataset_A_international_matches.csv"
    )
    team_set = {m["home_team"] for m in _matches} | {m["away_team"] for m in _matches}

    # Sorted unique dates with fixtures (for date_input bounds)
    _dates = sorted({datetime.date.fromisoformat(f["date"]) for f in _FIXTURES})
    _first, _last = _dates[0], _dates[-1]
    _today = datetime.date.today()
    _picker_default = max(_first, min(_last, _today))

    _first_s = _first.isoformat()
    _last_s = _last.isoformat()
    _ymds = dates_up_to_today_inclusive(_first_s, _last_s, _today)

    live_disk, preds_disk, rsn_disk = load_triple(_ROOT)
    for _idx, _res in preds_disk.items():
        st.session_state.setdefault(f"res_fx_{_idx}", _res)
    for _idx, _rsn in rsn_disk.items():
        st.session_state.setdefault(f"rsn_fx_{_idx}", _rsn)

    st.markdown(
        '<div class="wc-hero"><div class="wc-badge">USA · CAN · MEX 2026</div>'
        '<h1>⚽ FIFA World Cup 2026 — Match Predictor</h1>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Loading scores and predictions…"):
        _api_live = fetch_live_scores_by_fixture_idx(_FIXTURES, list(_ymds))
        live_by_idx = {**live_disk, **_api_live}
        merge_save_live_ft(_ROOT, live_by_idx)
        missing_pred = [
            fx
            for fx in _FIXTURES
            if _effective_actual(fx, live_by_idx) and f"res_fx_{fx['_idx']}" not in st.session_state
        ]
        for fx in missing_pred:
            _run_prediction(fx, team_set, "xgboost")

    st.markdown(_accuracy_hero_html(live_by_idx), unsafe_allow_html=True)

    tab_pred, tab_fix = st.tabs(["⚽  Match predictor", "📋  Fixtures & schedule"])

    # ── Tab 1: Date-based match predictor ────────────────────────────────────
    with tab_pred:
        pred_model = "xgboost"
        sel_date = st.date_input(
            "Match date",
            value=_picker_default,
            min_value=_first,
            max_value=_last,
            key="pred_date",
        )

        date_str = sel_date.isoformat()
        day_fx = [f for f in _FIXTURES if f["date"] == date_str]

        if not day_fx:
            st.info(
                f"No group-stage matches scheduled for **{sel_date.strftime('%B %d, %Y')}**. "
                "Try another date — group stage runs Jun 11–27, knockout Jun 28–Jul 19."
            )
        else:
            # Group the day's fixtures by group letter
            day_groups = sorted({f["group"] for f in day_fx})
            st.markdown(
                f'<div style="color:#dceaf5;font-size:0.88rem;margin-bottom:10px">'
                f'<b>{len(day_fx)}</b> match{"es" if len(day_fx) > 1 else ""} on '
                f'<b style="color:#ffe08a">{sel_date.strftime("%B %d, %Y")}</b> '
                f'— Groups {", ".join(day_groups)}</div>',
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
                    for fx in unplayed_today:
                        _run_prediction(fx, team_set, pred_model)
                    st.rerun()

    # ── Tab 2: Full fixtures & schedule ──────────────────────────────────────
    with tab_fix:
        st.markdown(
            '<p style="color:#dceaf5;font-size:0.88rem;margin:0 0 6px 0">'
            'All 72 group-stage matches + knockout schedule. '
            'Click <strong style="color:#ffe08a">Predict ▶</strong> on any unplayed match, '
            'or use <em>Predict all</em> to fill a whole group at once.</p>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        _show_fixtures_tab(team_set, "xgboost", live_by_idx)


if __name__ == "__main__":
    main()
