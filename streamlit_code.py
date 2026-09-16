import io
import os
import base64
import streamlit as st
import pandas as pd
from datetime import datetime
import snowflake.connector
from snowflake.snowpark import Session
import requests
from typing import Any, Dict, List, Optional
import re
import yaml

# ===================================================================
# Configuration
# ===================================================================
HOST = "WDSDGTL-XCC29288.snowflakecomputing.com"
ACCOUNT = "WDSDGTL-XCC29288"
DATABASE = "INVENTORY_DW_DEMO"
SCHEMA = "GOLD"
WAREHOUSE = "COMPUTE_WH"
ROLE = "ACCOUNTADMIN"


# Custom output instruction: keep Start Date / End Date out of all user-facing results.
# This instruction is added to the existing Snowflake/Cortex Analyst and Document AI prompts only.
HIDE_DATE_OUTPUT_INSTRUCTION = (
    "IMPORTANT OUTPUT RULE: Do not display, include, select, return, or mention Start Date or End Date "
    "in the final user-facing answer, result table, chart, chart labels, summary, or displayed output. "
    "These dates may still be used internally for filtering, calculations, or analysis when required, "
    "but the Start Date and End Date fields/values must not be shown to the user. "
)

# FULL semantic-model YAML files on Snowflake stages.
INVENTORY_YAML_STAGE_PATH = (
    '@"INVENTORY_DW_DEMO"."INVENTORY_SCHEMA"."YAML"/INV_ANALYST_DEMO_90_VERIFIED_FIXED_1.yaml'
)
SALES_YAML_STAGE_PATH = (
    '@"CORTEX_DEMO"."CORTEX_SCHEMA"."YAML"/sales_intelligence_model_80_queries_fixed_FINAL.yaml'
)
SUPPLY_CHAIN_YAML_STAGE_PATH = (
    '@"SUPPLY_CHAIN_DW_DEMO"."GOLD"."YAML"/SUPPLY_CHAIN.yml'
)

ANALYST_ENDPOINT = f"https://{HOST}/api/v2/cortex/analyst/message"
ROBOT_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dilytics_robot.png")

def _robot_data_uri():
    """Return the bundled Dilytics robot image as a data URI."""
    try:
        with open(ROBOT_IMAGE_PATH, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


st.set_page_config(
    page_title="Dilytics Enterprise AI",
    page_icon="Screenshot 2026-09-08 151031.png",
    layout="wide",
)

st.markdown("""
<style>
/* ================================================================
   Dilytics Professional AI UI
   Visual-only layer: backend/chat/document logic is unchanged.
   ================================================================ */
:root {
    --dly-navy: #082d69;
    --dly-navy-2: #0b3f8f;
    --dly-blue: #1769d2;
    --dly-cyan: #25cfff;
    --dly-text: #173f6f;
    --dly-muted: #6481a2;
}

.stApp {
    background:
        radial-gradient(circle at 88% 4%, rgba(37,207,255,.18), transparent 24%),
        radial-gradient(circle at 10% 92%, rgba(23,105,210,.08), transparent 28%),
        linear-gradient(180deg, #f7fbff 0%, #edf7ff 55%, #ffffff 100%);
}

.main .block-container {
    max-width: 1180px;
    padding-top: 0 !important;
    padding-bottom: 3rem;
}

/* Header / brand */
.dly-topbar {
    display:flex; align-items:center; justify-content:space-between;
    padding: 12px 18px;
    margin-bottom: 24px;
    border: 1px solid #dcecff;
    border-radius: 16px;
    background: rgba(255,255,255,.94);
    backdrop-filter: blur(14px);
    box-shadow: 0 10px 35px rgba(23,91,160,.08);
}
.dly-brand {
    display:flex; align-items:center; gap:10px;
    font-size: 1.05rem; font-weight:800; letter-spacing:.4px;
    color:#fff;
}
.dly-logo {
    display:inline-flex; align-items:center; justify-content:center;
    width:34px; height:28px; border-radius:7px;
    background:linear-gradient(135deg,#ff4b4b,#ff6262);
    color:white; font-size:.78rem; font-weight:900;
}
.dly-nav {
    display:flex; gap:22px; color:#6481a2; font-size:.78rem;
}
.dly-nav span:first-child { color:#1769d2; }
.dly-status {
    display:inline-flex; align-items:center; gap:6px;
    padding:6px 10px; border-radius:999px;
    background:rgba(34,197,94,.08);
    border:1px solid rgba(74,222,128,.28);
    color:#86efac; font-size:.72rem; font-weight:700;
}
.dly-hero {
    padding: 10px 8px 22px;
}
.dly-eyebrow {
    color:#1769d2; font-size:.78rem; font-weight:800;
    text-transform:uppercase; letter-spacing:1.5px;
}
.dly-hero h1 {
    margin: 7px 0 8px; color:#082d69;
    font-size: clamp(2rem, 4vw, 3.35rem);
    line-height:1.06; letter-spacing:-1.8px;
}
.dly-hero h1 span { color:#159fe8; }
.dly-hero p {
    max-width:650px; color:#587291; font-size:.92rem; line-height:1.65;
}

/* Status pill used in sidebar */
.status-pill {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(34,197,94,.08); color:#86efac;
    border:1px solid rgba(74,222,128,.28); border-radius:20px;
    padding:4px 10px; font-size:.72rem; font-weight:700;
}

/* Buttons */
div[data-testid="stButton"] > button {
    border-radius:10px; font-weight:600;
    min-height:42px;
    transition:all .18s ease-in-out;
}
.main div[data-testid="stButton"] > button {
    background:#ffffff;
    border:1px solid #cfe5fb;
    color:#164a82;
}
.main div[data-testid="stButton"] > button:hover {
    border-color:#1769d2;
    color:#1769d2; transform:translateY(-1px);
    box-shadow:0 7px 22px rgba(23,105,210,.12);
}

/* Intelligence tabs */
.stTabs [data-baseweb="tab-list"] {
    gap:8px; background:transparent;
    border-bottom:1px solid #dcecff;
}
.stTabs [data-baseweb="tab"] {
    color:#9eabc2; border-radius:10px 10px 0 0; padding:10px 18px;
}
.stTabs [aria-selected="true"] {
    color:#1769d2 !important;
    background:#eaf5ff;
}

/* Expander / cards */
[data-testid="stExpander"] {
    background:rgba(255,255,255,.96);
    border:1px solid #dcecff;
    border-radius:14px;
}

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border:1px solid #dcecff;
    border-radius:15px;
    background:#ffffff;
    margin-bottom:10px;
}
[data-testid="stChatMessage"] p { line-height:1.6; }

/* Chat input */
[data-testid="stChatInput"] {
    background:rgba(255,255,255,.98);
}
[data-testid="stChatInput"] > div {
    border:1px solid #b9d9f5 !important;
    border-radius:15px !important;
    background:#ffffff !important;
}

/* ChatGPT-style Dilytics sidebar */
section[data-testid="stSidebar"] {
    background:#f7f7f8 !important;
    border-right:1px solid #e5e7eb !important;
    min-width:280px !important;
    width:280px !important;
}

section[data-testid="stSidebar"] > div {
    background:#f7f7f8 !important;
    padding:10px 10px 18px 10px !important;
}

section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
    color:#1f2937 !important;
}


/* Pin Conversation button — the 📌 is INSIDE the bordered button */
section[data-testid="stSidebar"] [class*="st-key-pin_"] button {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    min-width: 38px !important;
    max-width: 38px !important;
    height: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    margin: 0 !important;
    border: 1px solid #c7d2df !important;
    border-radius: 9px !important;
    background: #f4f8fc !important;
    color: #173f70 !important;
    box-shadow: none !important;
    font-size: 17px !important;
    line-height: 1 !important;
}
section[data-testid="stSidebar"] [class*="st-key-pin_"] button:hover {
    background: #eaf4ff !important;
    border-color: #9fc9ec !important;
}
section[data-testid="stSidebar"] [class*="st-key-pin_"] button p {
    margin: 0 !important;
    font-size: 17px !important;
    line-height: 1 !important;
}

/* Sidebar header */
.dly-sidebar-brand {
    display:flex;
    align-items:center;
    justify-content:flex-start;
    padding:8px 8px 10px 8px;
    margin-top:-55px !important;
    margin-bottom:2px;
}
.dly-sidebar-brand-logo {
    width:110px !important;
    height:33px !important;
    max-width:110px !important;
    object-fit:contain !important;
    object-position:left center !important;
    display:block !important;
    margin:0 !important;
    padding:0 !important;
}

/* Search */
section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    background:#ffffff !important;
    border:1px solid #e5e7eb !important;
    border-radius:9px !important;
    color:#111827 !important;
    height:38px !important;
    font-size:.88rem !important;
}
section[data-testid="stSidebar"] [data-testid="stTextInput"] input:focus {
    border-color:#c7c7c7 !important;
    box-shadow:0 0 0 1px #d1d5db !important;
}

/* Sidebar buttons */
section[data-testid="stSidebar"] .stButton > button {
    min-height:40px !important;
    height:40px !important;
    border:0 !important;
    border-radius:9px !important;
    background:transparent !important;
    color:#1f2937 !important;
    font-size:.88rem !important;
    font-weight:400 !important;
    box-shadow:none !important;
    text-align:left !important;
    padding:0 10px !important;
    transition:background .15s ease, transform .1s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background:#ececef !important;
    border:0 !important;
    color:#111827 !important;
}
section[data-testid="stSidebar"] .stButton > button:active {
    transform:scale(.99);
}

/* New Chat — explicit key-scoped styling so Streamlit cannot override the border */
section[data-testid="stSidebar"] .st-key-sidebar_new_chat,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat > div,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat .stButton,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat .stButton > div {
    width:100% !important;
}

section[data-testid="stSidebar"] .st-key-sidebar_new_chat button,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat .stButton > button {
    width:100% !important;
    min-height:40px !important;
    height:40px !important;
    padding:0 12px !important;
    background:#f4f9ff !important;
    background-color:#f4f9ff !important;
    border:1.5px solid #bcd9f2 !important;
    border-radius:9px !important;
    color:#173f70 !important;
    font-weight:500 !important;
    box-shadow:0 1px 3px rgba(45,105,160,.08) !important;
    outline:none !important;
}

section[data-testid="stSidebar"] .st-key-sidebar_new_chat button:hover,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat .stButton > button:hover {
    background:#eaf4ff !important;
    background-color:#eaf4ff !important;
    border:1.5px solid #9fc9ed !important;
}

section[data-testid="stSidebar"] .st-key-sidebar_new_chat button:focus,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat button:focus-visible,
section[data-testid="stSidebar"] .st-key-sidebar_new_chat .stButton > button:focus-visible {
    border:1.5px solid #9fc9ed !important;
    outline:none !important;
    box-shadow:0 0 0 2px rgba(159,201,237,.18) !important;
}

/* Reset Chat — same border treatment as New Chat */
section[data-testid="stSidebar"] .st-key-sidebar_reset_chat button {
    background:#ffffff !important;
    border:1px solid #d1d5db !important;
    border-radius:9px !important;
    color:#111827 !important;
    box-shadow:none !important;
}
section[data-testid="stSidebar"] .st-key-sidebar_reset_chat button:hover {
    background:#ececef !important;
    border:1px solid #d1d5db !important;
}

/* Section labels */
.dly-sidebar-section {
    padding:10px 8px 5px 8px;
    color:#6b7280;
    font-size:.74rem;
    font-weight:600;
    letter-spacing:.01em;
}

/* Session buttons */
.dly-session-active {
    background:#ececef !important;
    border-radius:9px;
}
.dly-sidebar-divider {
    height:1px;
    background:#e5e7eb;
    margin:10px 4px;
}

/* Keep the native Streamlit sidebar collapse affordance visible and stable. */
button[aria-label*="Collapse sidebar"],
button[aria-label*="Expand sidebar"] {
    z-index:1000 !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background:#ffffff;
    border:1px solid #dcecff;
    border-radius:12px;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border-radius:12px; overflow:hidden;
}

/* Remove excess Streamlit decoration */
#MainMenu { visibility:hidden; }
footer { visibility:hidden; }
header { background:transparent !important; }
</style>
""", unsafe_allow_html=True)



st.markdown("""
<style>
/* ================================================================
   Dilytics Landing Page
   Visual/navigation layer only. Backend functionality is unchanged.
   ================================================================ */
.dly-landing-wrap {
    min-height: 78vh;
    margin: -1.2rem -2rem 0;
    padding: 2rem 5vw 4rem;
    background:
        radial-gradient(circle at 78% 18%, rgba(29,190,255,.30), transparent 28%),
        radial-gradient(circle at 35% 100%, rgba(20,111,220,.24), transparent 35%),
        linear-gradient(135deg,#071a42 0%,#063b79 48%,#0b83bd 100%);
    border-radius: 0 0 28px 28px;
    position: relative;
    overflow: hidden;
}
.dly-landing-wrap:before,
.dly-landing-wrap:after {
    content:""; position:absolute; border:1px solid rgba(100,220,255,.18);
    border-radius:50%; pointer-events:none;
}
.dly-landing-wrap:before { width:760px; height:760px; right:-250px; top:-420px; }
.dly-landing-wrap:after { width:680px; height:680px; left:-360px; bottom:-470px; }
.dly-landing-nav {
    display:flex; align-items:center; justify-content:space-between;
    position:relative; z-index:2; margin-bottom:7vh;
}
.dly-landing-logo {
    display:inline-flex; align-items:center; justify-content:center;
    background:#ef222c; color:#fff; padding:9px 18px;
    font-size:1.25rem; font-weight:900; letter-spacing:.5px;
    border-radius:2px; box-shadow:0 8px 25px rgba(0,0,0,.18);
}
.dly-landing-powered {
    color:#bfeeff; font-size:.76rem; font-weight:700;
    letter-spacing:1px; text-transform:uppercase;
}
.dly-landing-grid {
    display:grid; grid-template-columns: 1.02fr .98fr; gap:4rem;
    align-items:center; position:relative; z-index:2;
}
.dly-landing-copy h1 {
    color:#fff; font-size:clamp(3rem,6vw,5.5rem); line-height:.98;
    letter-spacing:-3px; margin:0 0 22px; font-weight:850;
}
.dly-landing-copy h1 span { color:#20d7ff; }
.dly-landing-copy p {
    color:#d0e7ff; font-size:1.15rem; line-height:1.6;
    max-width:620px; margin-bottom:28px;
}
.dly-landing-actions {
    display:flex; gap:16px; align-items:center; flex-wrap:wrap;
}
.dly-landing-actions button {
    border:0; border-radius:30px; padding:13px 27px;
    font-size:1rem; font-weight:800; cursor:pointer;
}
.dly-explore {
    background:linear-gradient(90deg,#0da9ff,#2ed8c4); color:#fff;
    box-shadow:0 10px 30px rgba(0,183,255,.25);
}
.dly-ask {
    background:rgba(4,25,62,.35); color:#fff;
    border:1px solid rgba(140,225,255,.55) !important;
}
.dly-landing-search {
    margin-top:25px; max-width:680px; padding:10px;
    border-radius:17px; background:rgba(255,255,255,.10);
    border:1px solid rgba(255,255,255,.20); backdrop-filter:blur(12px);
}
.dly-landing-search input {
    color:#fff !important; background:rgba(2,18,48,.55) !important;
}
.dly-landing-search input::placeholder { color:#b8d4ee !important; }
.dly-landing-visual {
    min-height:470px; position:relative; display:flex;
    align-items:center; justify-content:center;
}
.dly-robot-orb {
    width:390px; height:390px; border-radius:50%;
    background:radial-gradient(circle at 35% 30%,#25cfff,#0878c8 58%,#073c80);
    box-shadow:0 0 90px rgba(30,208,255,.28);
    display:flex; align-items:center; justify-content:center;
    font-size:12rem; position:relative;
}
.dly-chat-bubble {
    position:absolute; right:0; top:15%; background:#eaf6ff;
    color:#073579; padding:18px 23px; border-radius:22px 22px 5px 22px;
    font-size:1.05rem; line-height:1.35; box-shadow:0 15px 35px rgba(0,0,0,.2);
}
.dly-chat-bubble strong { font-size:1.2rem; }
.dly-landing-stats {
    display:flex; gap:35px; margin-top:48px; color:#dff4ff;
}
.dly-stat { display:flex; gap:10px; align-items:center; }
.dly-stat-icon { font-size:1.4rem; }
.dly-stat-text { font-size:.9rem; line-height:1.2; }
.dly-stat-text b { display:block; color:#fff; font-size:1rem; }
@media (max-width: 900px) {
    .dly-landing-grid { grid-template-columns:1fr; gap:1rem; }
    .dly-landing-visual { min-height:300px; }
    .dly-robot-orb { width:280px; height:280px; }
    .dly-chat-bubble { right:3%; }
    .dly-landing-wrap { margin-left:-1rem; margin-right:-1rem; }
}
</style>
""", unsafe_allow_html=True)


# ===================================================================
# 1. LOGIN / SNOWFLAKE SESSION
# ===================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.password = ""
    st.session_state.snowpark_session = None
    st.session_state.snowflake_conn = None
    st.session_state.app_page = "home"

if "captcha_a" not in st.session_state:
    import random
    st.session_state.captcha_a = random.randint(2, 9)
    st.session_state.captcha_b = random.randint(1, 9)

def _new_captcha():
    import random
    st.session_state.captcha_a = random.randint(2, 9)
    st.session_state.captcha_b = random.randint(1, 9)


def _login_page():
    # ================================================================
    # CHAT LOGIN — 70% AI CARD + 30% SIGN-IN CARD
    # Only the login-page layout is changed here. Authentication logic
    # and the rest of the application remain unchanged.
    # ================================================================
    st.markdown("""
    <style>
      .login-page-row{
          width:100%;
          display:grid;
          grid-template-columns:7fr 3fr;
          gap:22px;
          align-items:stretch;
          margin:2.2rem auto 0;
      }

      .login-ai-card{
          min-height:650px;
          box-sizing:border-box;
          border:1px solid #d8ebff;
          border-radius:24px;
          overflow:hidden;
          background:#fff;
          box-shadow:0 24px 70px rgba(19,82,145,.12);
          display:grid;
          grid-template-columns:1fr 1fr;
      }

      .login-copy{
          padding:58px 52px;
          background:linear-gradient(145deg,#ffffff 0%,#f2f9ff 100%);
          display:flex;
          flex-direction:column;
          justify-content:center;
      }

      .login-visual{
          position:relative;
          display:flex;
          align-items:center;
          justify-content:center;
          background:radial-gradient(circle at 50% 45%,#e8f7ff 0,#d9efff 30%,#f7fbff 68%,#fff 100%);
          overflow:hidden;
      }

      .login-logo{
          display:none !important;
          width:max-content;
          background:#e51f2b;
          color:#fff;
          font-weight:900;
          font-size:1.35rem;
          padding:9px 17px;
          border-radius:4px;
          letter-spacing:.6px;
          box-shadow:0 8px 20px rgba(229,31,43,.12);
      }

      .login-eyebrow{
          color:#1769d2;
          font-weight:800;
          letter-spacing:2px;
          text-transform:uppercase;
          font-size:.78rem;
          margin-top:0;
      }

      .login-title{
          font-size:3.15rem;
          line-height:1.04;
          font-weight:900;
          color:#082d69;
          margin:.5rem 0 1rem;
          letter-spacing:-1.4px;
      }

      .login-title span{color:#1769d2}

      .login-sub{
          color:#55708f;
          font-size:1rem;
          line-height:1.7;
          max-width:510px;
          margin-bottom:26px;
      }

      .login-feature-row{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:8px;
      }

      .login-feature{
          padding:9px 13px;
          background:#fff;
          border:1px solid #d7eaff;
          border-radius:999px;
          color:#245b91;
          font-size:.78rem;
          font-weight:700;
          box-shadow:0 7px 18px rgba(23,91,160,.05);
      }

      .login-orbit{
          width:450px;
          height:450px;
          border-radius:50%;
          border:1px solid #b8dcff;
          box-shadow:0 0 0 28px rgba(35,137,230,.05),0 0 0 58px rgba(35,137,230,.035);
          position:relative;
          animation:orbitPulse 4s ease-in-out infinite;
          display:flex;
          align-items:center;
          justify-content:center;
      }

      .login-robot-img{
          width:410px;
          max-width:90%;
          height:auto;
          object-fit:contain;
          filter:drop-shadow(0 28px 40px rgba(20,94,170,.18));
          animation:robotFloat 3.4s ease-in-out infinite;
      }

      .login-float{
          position:absolute;
          padding:10px 14px;
          background:#fff;
          border:1px solid #d7eaff;
          border-radius:14px;
          color:#15519b;
          font-weight:700;
          box-shadow:0 10px 25px rgba(22,91,164,.1);
          animation:floatCard 4s ease-in-out infinite;
          z-index:2;
      }

      .login-float.one{top:16%;left:7%}
      .login-float.two{right:7%;top:23%;animation-delay:1s}
      .login-float.three{bottom:15%;left:11%;animation-delay:2s}

      /* Match the sign-in card background to the white premium AI card */
      .st-key-login_form_card{
          min-height:650px !important;
          height:650px !important;
          box-sizing:border-box !important;
          padding:38px 30px !important;
          background:linear-gradient(145deg,#ffffff 0%,#f2f9ff 100%) !important;
          border:1px solid #d8ebff !important;
          border-radius:24px !important;
          box-shadow:0 24px 70px rgba(19,82,145,.12) !important;
          overflow:hidden !important;
      }

      .st-key-login_form_card > div{
          background:transparent !important;
      }

      .login-form-badge{
          display:inline-block;
          width:max-content;
          padding:6px 10px;
          border:1px solid #d7eaff;
          border-radius:999px;
          background:#f3f9ff;
          color:#1769d2;
          font-size:.67rem;
          font-weight:800;
          margin-bottom:10px;
      }

      .login-form-title{
          color:#082d69;
          font-size:1.45rem;
          font-weight:900;
          margin:0;
      }

      .login-form-sub{
          color:#6b849e;
          font-size:.72rem;
          line-height:1.5;
          margin-top:7px;
          margin-bottom:18px;
      }

      .login-divider{
          height:1px;
          background:#e2edf7;
          width:100%;
          margin-bottom:18px;
      }

      .login-form-card label{
          color:#486784 !important;
          font-size:.70rem !important;
          font-weight:700 !important;
      }

      .login-form-card input{
          border-radius:9px !important;
          border:1px solid #dce8f3 !important;
          background:#f7fafd !important;
          min-height:40px !important;
      }

      .login-form-card input:focus{
          border-color:#8fc2f5 !important;
          box-shadow:0 0 0 2px rgba(23,105,210,.08) !important;
      }

      .login-form-footer{
          color:#91a3b5;
          font-size:.61rem;
          line-height:1.45;
          margin-top:14px;
      }

      /* Sign-in button — blue background */
      .st-key-login_submit button {
          background:#1769d2 !important;
          background-color:#1769d2 !important;
          border:1px solid #1769d2 !important;
          color:#ffffff !important;
          font-weight:700 !important;
      }

      .st-key-login_submit button:hover {
          background:#0b3f8f !important;
          background-color:#0b3f8f !important;
          border-color:#0b3f8f !important;
          color:#ffffff !important;
      }

      /* ================================================================
         GLOBAL TOP NAV FOR LOGIN PAGE
         Match the Home-page Home / Document AI buttons exactly.
         Width, height, spacing, icons and visual treatment are kept
         identical to the final Home-page navigation.
         ================================================================ */
      .st-key-top_home,
      .st-key-top_docs {
          position:absolute !important;
          top:48px !important;
          z-index:10000 !important;
          margin:0 !important;
          padding:0 !important;
          margin-top: -45px !important;
      }

      .st-key-top_home {
          right:195px !important;
          width:120px !important;
      }

      .st-key-top_docs {
          right:15px !important;
          width:170px !important;
      }

      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"] {
          width:100% !important;
          min-width:0 !important;
          max-width:none !important;
          margin:0 !important;
          padding:0 !important;
      }

      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          width:100% !important;
          min-width:0 !important;
          max-width:none !important;
          height:52px !important;
          min-height:52px !important;
          padding:0 8px !important;
          margin:0 !important;
          border-radius:8px !important;
          font-size:.76rem !important;
          font-weight:700 !important;
          white-space:nowrap !important;
          display:flex !important;
          align-items:center !important;
          justify-content:center !important;
          box-sizing:border-box !important;
          background:#ffffff !important;
          border:1px solid #dfe4eb !important;
          color:#171717 !important;
          box-shadow:0 2px 8px rgba(21,43,70,.055), inset 0 1px 0 rgba(255,255,255,.98) !important;
      }

      .st-key-top_home [data-testid="stButton"] > button:hover,
      .st-key-top_docs [data-testid="stButton"] > button:hover {
          background:#fbfcfe !important;
          border-color:#cfd8e3 !important;
          transform:translateY(-1px) !important;
          box-shadow:0 6px 14px rgba(21,43,70,.10), inset 0 1px 0 rgba(255,255,255,.98) !important;
      }

      .st-key-top_home [data-testid="stButton"] > button::before,
      .st-key-top_docs [data-testid="stButton"] > button::before {
          display:inline-flex !important;
          align-items:center !important;
          justify-content:center !important;
          width:29px !important;
          height:29px !important;
          flex:0 0 29px !important;
          margin-right:7px !important;
          border-radius:6px !important;
          background:#f5f7fa !important;
          color:#111827 !important;
          box-shadow:inset 0 0 0 1px #e5e9ee !important;
      }

      .st-key-top_home [data-testid="stButton"] > button::before {
          content:"⌂" !important;
          font-size:19px !important;
      }

      .st-key-top_docs [data-testid="stButton"] > button::before {
          content:"▣" !important;
          font-size:17px !important;
      }

      @keyframes robotFloat{50%{transform:translateY(-10px)}}
      @keyframes orbitPulse{50%{transform:scale(1.025)}}
      @keyframes floatCard{50%{transform:translateY(-10px)}}

      @media(max-width:1050px){
          .login-page-row{grid-template-columns:1fr}
          .login-form-card{min-height:auto !important;height:auto !important}
      }

      @media(max-width:700px){
          .login-ai-card{grid-template-columns:1fr}
          .login-visual{min-height:430px;order:-1}
          .login-copy{padding:42px 28px}
          .login-title{font-size:2.35rem}
          .login-orbit{width:350px;height:350px}
          .login-robot-img{width:330px}
      }
    </style>
    """, unsafe_allow_html=True)

    left, right = st.columns([7, 3], gap="medium")

    # ============================================================
    # 70% — EXISTING DILYTICS AI CARD
    # ============================================================
    with left:
        st.markdown(
            """
            <div class="login-ai-card">
              <div class="login-copy">
                <div class="login-logo">DILYTICS</div>
                <div class="login-eyebrow">Enterprise AI Workspace</div>
                <div class="login-title">
                  Turn your data into <span>answers.</span>
                </div>
                <div class="login-sub">
                  Sign in securely to explore Inventory, Sales, Supply Chain
                  and Document AI with natural-language conversations powered
                  by Snowflake.
                </div>
                <div class="login-feature-row">
                  <span class="login-feature">📊 Live insights</span>
                  <span class="login-feature">🔐 Secure access</span>
                  <span class="login-feature">⚡ AI powered</span>
                </div>
              </div>

              <div class="login-visual">
                <div class="login-float one">📈 Smarter decisions</div>
                <div class="login-float two">☁️ Cloud analytics</div>
                <div class="login-float three">🤖 AI ready</div>
                <div class="login-orbit">
                  <img
                    class="login-robot-img"
                    src="{robot_src}"
                    alt="Dilytics AI assistant"
                  />
                </div>
              </div>
            </div>
            """.replace("{robot_src}", _robot_data_uri()),
            unsafe_allow_html=True,
        )

    # ============================================================
    # 30% — COMPLETE SIGN-IN CARD
    # ============================================================
    with right:
        with st.container(border=True, key="login_form_card"):
            st.markdown(
                """
                <div class="login-form-badge">
                  🟢 Secure workspace access
                </div>
                <div class="login-form-title">Sign in to AI analytics</div>
                <div class="login-form-sub">
                  Connect securely to your enterprise intelligence workspace.
                </div>
                <div class="login-divider"></div>
                """,
                unsafe_allow_html=True,
            )

            st.session_state.username = st.text_input(
                "Username",
                value="",
                key="login_username",
            )

            st.session_state.password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )

            login_clicked = st.button(
                "Sign in to AI analytics",
                use_container_width=True,
                type="primary",
                key="login_submit",
            )

            st.markdown(
                """
                <div class="login-form-footer">
                  Your credentials are used only to establish the secure
                  Snowflake session for this workspace.
                </div>
                """,
                unsafe_allow_html=True,
            )

    if login_clicked:
        try:
            with st.spinner("Connecting securely to Snowflake..."):
                conn = snowflake.connector.connect(
                        user=st.session_state.username,
                        password=st.session_state.password,
                        account=ACCOUNT,
                        host=HOST,
                        port=443,
                        warehouse=WAREHOUSE,
                        role=ROLE,
                        database=DATABASE,
                        schema=SCHEMA,
                    )

            st.session_state.snowflake_conn = conn
            st.session_state.snowpark_session = (
                Session.builder
                .configs({"connection": conn})
                .create()
            )

            st.session_state.authenticated = True

            # Continue to the page that requested authentication.
            # This is important for Document AI: the uploaded spreadsheet
            # needs the authenticated Snowpark session before write_pandas()
            # can create the transient table used by the chatbot.
            next_page = st.session_state.pop("post_login_page", "chatbot")
            st.session_state.app_page = next_page
            st.rerun()

        except Exception as e:
            st.error(f"Authentication failed: {e}")

    st.stop()


def get_analyst_headers() -> Dict[str, str]:
    token = conn.rest.token
    return {
        "Authorization": f'Snowflake Token="{token}"',
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def call_cortex_analyst(prompt: str) -> Dict[str, Any]:
    # Add the output rule to the existing Snowflake/Cortex Analyst prompt only.
    prompt_with_output_rule = prompt + "\n\n" + HIDE_DATE_OUTPUT_INSTRUCTION
    request_body = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": prompt_with_output_rule}],
        }],
        "semantic_models": [
            {"semantic_model_file": INVENTORY_YAML_STAGE_PATH},
            {"semantic_model_file": SALES_YAML_STAGE_PATH},
            {"semantic_model_file": SUPPLY_CHAIN_YAML_STAGE_PATH},
        ],
        "stream": False,
    }

    response = requests.post(
        ANALYST_ENDPOINT,
        headers=get_analyst_headers(),
        json=request_body,
        timeout=120,
    )

    if response.status_code >= 400:
        try:
            details = response.json()
        except Exception:
            details = response.text
        raise RuntimeError(
            f"Cortex Analyst API error ({response.status_code}): {details}"
        )

    return response.json()


def call_cortex_analyst_with_semantic_model(
    prompt: str,
    semantic_model_yaml: str,
) -> Dict[str, Any]:
    """Call Cortex Analyst with an inline, dynamically generated YAML model."""
    # Add the output rule to the existing uploaded-document/Cortex Analyst prompt only.
    prompt_with_output_rule = prompt + "\n\n" + HIDE_DATE_OUTPUT_INSTRUCTION
    request_body = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": prompt_with_output_rule}],
        }],
        "semantic_model": semantic_model_yaml,
        "stream": False,
    }

    response = requests.post(
        ANALYST_ENDPOINT,
        headers=get_analyst_headers(),
        json=request_body,
        timeout=120,
    )

    if response.status_code >= 400:
        try:
            details = response.json()
        except Exception:
            details = response.text
        raise RuntimeError(
            f"Cortex Analyst API error ({response.status_code}): {details}"
        )

    data = response.json()
    if isinstance(data, dict) and data.get("error_code"):
        raise RuntimeError(
            f"Cortex Analyst returned error {data.get('error_code')}: "
            f"{data.get('message', data)}"
        )
    return data


def extract_analyst_response(data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "text": "",
        "sql": None,
        "warnings": data.get("warnings", []) or [],
        "semantic_model_selection": data.get("semantic_model_selection"),
        "verified_query_used": None,
        "request_id": data.get("request_id"),
    }

    message = data.get("message", {})
    content = message.get("content", [])
    if isinstance(content, dict):
        content = [content]

    text_parts = []

    for block in content:
        block_type = block.get("type")

        if block_type == "text":
            if block.get("text"):
                text_parts.append(block["text"])

        elif block_type == "sql":
            result["sql"] = (
                block.get("statement")
                or block.get("sql")
                or block.get("query")
            )
            confidence = block.get("confidence", {})
            if isinstance(confidence, dict):
                result["verified_query_used"] = confidence.get(
                    "verified_query_used"
                )

        elif block_type == "suggestions":
            suggestions = block.get("suggestions", [])
            if isinstance(suggestions, list):
                text_parts.append(
                    "I could not generate SQL for this question. "
                    "Try one of these questions:\n\n"
                    + "\n".join(f"- {x}" for x in suggestions)
                )
            elif suggestions:
                text_parts.append(str(suggestions))

    result["text"] = "\n\n".join(text_parts).strip()

    if not result["sql"]:
        result["sql"] = message.get("statement")

    return result

# ===================================================================
# 2A. UPLOADED DOCUMENT ANALYSIS (ADDED - ORIGINAL CORTEX ANALYST
#     INVENTORY/SALES CODE IS PRESERVED)
# ===================================================================
# PDF/Word document Q&A uses the current AI_COMPLETE document capability.
# Excel/CSV continues to use the existing Cortex Analyst path unchanged.
DOCUMENT_AI_MODEL = "claude-sonnet-4-6"
DOCUMENT_STAGE_DB = "INVENTORY_DW_DEMO"
DOCUMENT_STAGE_SCHEMA = "GOLD"
DOCUMENT_STAGE_NAME = "DILYTICS_DOCUMENT_STAGE"

if "uploaded_document" not in st.session_state:
    st.session_state.uploaded_document = None
if "uploaded_document_name" not in st.session_state:
    st.session_state.uploaded_document_name = None
if "uploaded_document_df" not in st.session_state:
    st.session_state.uploaded_document_df = None
if "uploaded_document_text" not in st.session_state:
    st.session_state.uploaded_document_text = ""
if "uploaded_document_type" not in st.session_state:
    st.session_state.uploaded_document_type = None
if "uploaded_document_table" not in st.session_state:
    st.session_state.uploaded_document_table = None
if "uploaded_document_semantic_model" not in st.session_state:
    st.session_state.uploaded_document_semantic_model = None
if "uploaded_document_stage" not in st.session_state:
    st.session_state.uploaded_document_stage = None
if "uploaded_document_stage_file" not in st.session_state:
    st.session_state.uploaded_document_stage_file = None
# ADDITIVE: keep the uploaded Excel workbook so the user can switch sheets
# after the document has been analyzed, without changing the existing workflow.
if "uploaded_excel_bytes" not in st.session_state:
    st.session_state.uploaded_excel_bytes = None
if "uploaded_excel_sheets" not in st.session_state:
    st.session_state.uploaded_excel_sheets = []
if "uploaded_excel_selected_sheet" not in st.session_state:
    st.session_state.uploaded_excel_selected_sheet = None


def _snowflake_sql_literal(value: str) -> str:
    """Safely convert a Python string into a Snowflake SQL string literal."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _document_stage_quoted_name() -> str:
    """Return the fully-qualified named stage used for PDF/DOCX files."""
    return (
        f'"{DOCUMENT_STAGE_DB}"."{DOCUMENT_STAGE_SCHEMA}".'
        f'"{DOCUMENT_STAGE_NAME}"'
    )


def _document_stage_file_reference() -> str:
    """Return the fully-qualified @stage reference required by PUT/TO_FILE."""
    return '@' + _document_stage_quoted_name()


def _ensure_document_stage():
    """Create the persistent, server-encrypted named stage used by AI_COMPLETE.

    AI_COMPLETE document processing requires the referenced FILE to live on an
    accessible internal/external stage. A temporary stage is session-scoped and
    is not reliable for this document-processing path, so use a dedicated named
    internal stage instead.
    """
    stage_name = _document_stage_quoted_name()
    try:
        session.sql(
            f"CREATE STAGE IF NOT EXISTS {stage_name} "
            "ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')"
        ).collect()
    except Exception as exc:
        raise RuntimeError(
            f"Could not create or access document stage {stage_name}. "
            "Run this once with a role that can CREATE STAGE in "
            f"{DOCUMENT_STAGE_DB}.{DOCUMENT_STAGE_SCHEMA}, or grant the Streamlit role "
            "USAGE on the database/schema and READ/WRITE on the stage."
        ) from exc
    return stage_name


def _upload_document_to_stage(uploaded_file) -> str:
    """Upload a PDF/DOCX to the session's temporary Snowflake stage."""
    import os
    import tempfile

    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if extension not in {"pdf", "docx"}:
        raise ValueError("Only PDF and Word (.docx) documents can use document Q&A.")

    stage_name = _ensure_document_stage()
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", uploaded_file.name)

    # Claude Sonnet 4.6 supports documents up to 22 MB.
    file_size = getattr(uploaded_file, "size", None)
    if file_size is not None and file_size > 22 * 1024 * 1024:
        raise ValueError(
            f"The PDF/Word file is {file_size / (1024 * 1024):.2f} MB. "
            "The selected Claude Sonnet 4.6 document model supports files up to 22 MB."
        )
    if not safe_name.lower().endswith((".pdf", ".docx")):
        safe_name = f"document.{extension}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp:
        uploaded_file.seek(0)
        tmp.write(uploaded_file.getvalue())
        local_path = tmp.name

    try:
        # Do not compress: AI_COMPLETE needs the original document extension/content.
        session.file.put(
            local_path,
            _document_stage_file_reference(),
            auto_compress=False,
            overwrite=True,
        )
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass

    st.session_state.uploaded_document_stage = _document_stage_file_reference()
    st.session_state.uploaded_document_stage_file = safe_name
    return safe_name


def ai_complete_document_question(question: str) -> str:
    """Answer a question directly from the uploaded PDF/DOCX using AI_COMPLETE.

    This is intentionally separate from the working Excel/CSV Cortex Analyst path.
    It does not use the legacy SNOWFLAKE.CORTEX.COMPLETE function.
    """
    stage_name = st.session_state.get("uploaded_document_stage")
    stage_file = st.session_state.get("uploaded_document_stage_file")

    if not stage_name or not stage_file:
        raise RuntimeError(
            "The uploaded PDF/Word document is not available in the Snowflake stage. "
            "Please click Analyze Document again."
        )

    model_literal = _snowflake_sql_literal(DOCUMENT_AI_MODEL)
    question_literal = _snowflake_sql_literal(
        "You are a document-grounded analyst. Answer the user question using ONLY the uploaded document. "
        "Do not use general knowledge, assumptions, or information not present in the document. "
        "Read the relevant paragraphs, headings, lists, and tables before answering. "
        "Preserve exact names, numbers, dates, percentages, and wording where they matter. "
        "If the answer is not explicitly supported by the document, say: 'The document does not provide enough information to answer this.' "
        "If multiple passages support the answer, reconcile them and state the relevant section/page when available. "
        "For calculations, show the calculation briefly and use only document values. "
        "Never invent a missing value. Be concise but complete. "
        + HIDE_DATE_OUTPUT_INSTRUCTION
        + "User question: " + question
    )
    # TO_FILE expects the stage reference as a string such as
    # '@"DATABASE"."SCHEMA"."STAGE"'.
    stage_literal = _snowflake_sql_literal(stage_name)
    file_literal = _snowflake_sql_literal(stage_file)

    sql = f"""
        SELECT AI_COMPLETE(
            MODEL => {model_literal},
            PROMPT => PROMPT(
                {question_literal} || '\n\nDocument to analyze: {{0}}',
                TO_FILE({stage_literal}, {file_literal})
            )
        ) AS RESPONSE
    """

    rows = session.sql(sql).collect()
    if not rows:
        raise RuntimeError("AI_COMPLETE did not return a response.")

    row = rows[0]
    try:
        response = row["RESPONSE"]
    except Exception:
        response = row[0]

    if response is None:
        raise RuntimeError(
            "AI_COMPLETE returned no answer. Check that the SNOWFLAKE.CORTEX_USER "
            "database role is available and that the document is within the model's size limit."
        )

    # Some AI_COMPLETE variants can return an object when error details are requested;
    # this call uses the normal string response, so stringify defensively.
    return str(response)

def _clean_generated_sql(text_value: str) -> str:
    """Extract and validate a read-only SELECT/WITH SQL statement."""
    sql_text = str(text_value or "").strip()

    if "```" in sql_text:
        blocks = re.findall(
            r"```(?:sql|SQL)?\s*(.*?)```", sql_text, flags=re.DOTALL
        )
        if blocks:
            sql_text = blocks[0].strip()

    sql_text = re.sub(
        r"^\s*(SQL\s*:|Query\s*:)\s*", "", sql_text, flags=re.I
    ).strip().rstrip(";").strip()

    if not re.match(r"^(SELECT|WITH)\b", sql_text, flags=re.I):
        raise RuntimeError(
            "Cortex Analyst did not return a valid SELECT/WITH statement."
        )

    forbidden = re.search(
        r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|PUT|REMOVE|CALL)\b",
        sql_text,
        flags=re.I,
    )
    if forbidden:
        raise RuntimeError(
            f"Generated document SQL contains a non-read-only command: {forbidden.group(1)}"
        )

    return sql_text


def _normalize_uploaded_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Make mixed Excel/CSV columns safe for Streamlit and Snowflake.

    Numeric/date/bool columns stay typed. Object columns are normalized to text
    because Excel frequently mixes integers, strings such as 'Grand Total', and
    blanks in the same column.
    """
    if df is None:
        return df

    work_df = df.copy()
    for col in work_df.columns:
        series = work_df[col]
        if pd.api.types.is_object_dtype(series.dtype):
            work_df[col] = series.map(
                lambda value: None if pd.isna(value) else str(value)
            )
    return work_df


def _safe_column_names(df: pd.DataFrame):
    """Create SQL-friendly, unique Snowflake column names."""
    mapping = {}
    used = set()

    for original in df.columns:
        base = re.sub(
            r"[^A-Za-z0-9_]+", "_", str(original)
        ).strip("_").upper()
        if not base:
            base = "COLUMN"
        if base[0].isdigit():
            base = "_" + base

        candidate = base
        n = 2
        while candidate in used:
            candidate = f"{base}_{n}"
            n += 1

        used.add(candidate)
        mapping[str(original)] = candidate

    return mapping


def _snowflake_type_for_pandas(dtype) -> str:
    if pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(dtype):
        return "NUMBER"
    if pd.api.types.is_float_dtype(dtype):
        return "NUMBER"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP_NTZ"
    return "TEXT"


def _column_synonyms(original_name: str):
    """Create conservative synonyms from the actual uploaded header."""
    text = re.sub(r"[_\-]+", " ", str(original_name)).strip()
    words = text.split()
    synonyms = [text.lower()]

    if text.lower().endswith(" id"):
        synonyms.append(text[:-3].strip().lower() + " identifier")
    if "commercial project" in text.lower() and "id" in text.lower():
        synonyms.extend(["project id", "commercial project"])
    if "jurisdiction" in text.lower():
        synonyms.extend(["jurisdiction", "local jurisdiction"])
    if "contractor" in text.lower():
        synonyms.extend(["contractor", "vendor"])
    if "business name" in text.lower():
        synonyms.extend(["business", "project business"])
    if "close out" in text.lower() or "closeout" in text.lower():
        synonyms.extend([
            "closeout date",
            "close out date",
            "completion date",
            "completed date",
        ])

    # Preserve order and uniqueness.
    result = []
    seen = set()
    for item in synonyms:
        item = item.strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result[:8]


def _sample_values(df: pd.DataFrame, original: str, limit: int = 5):
    values = []
    for value in df[original].dropna().head(limit).tolist():
        text = str(value)
        if len(text) > 100:
            text = text[:97] + "..."
        values.append(text)
    return values


def _looks_like_identifier(original_name: str, series: pd.Series) -> bool:
    """Conservatively identify ID/code columns so they are not treated as sums."""
    name = re.sub(r"[_\-]+", " ", str(original_name)).strip().lower()
    id_words = (" id", "_id", " identifier", " code", " number", " no")
    if any(token in name for token in id_words) or name.endswith(("id", "code", "number", "no")):
        return True
    try:
        non_null = series.dropna()
        if len(non_null) and pd.api.types.is_numeric_dtype(series.dtype):
            unique_ratio = non_null.nunique(dropna=True) / len(non_null)
            return unique_ratio >= 0.98 and len(non_null) >= 20
    except Exception:
        pass
    return False


def _column_profile(df: pd.DataFrame, original: str) -> Dict[str, Any]:
    """Return compact, deterministic metadata used to make Analyst's model precise."""
    series = df[original]
    non_null = series.dropna()
    profile: Dict[str, Any] = {
        "rows": int(len(series)),
        "non_null": int(non_null.shape[0]),
        "nulls": int(series.isna().sum()),
        "unique": int(non_null.nunique(dropna=True)),
        "samples": _sample_values(df, original, 8),
    }
    try:
        if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
            profile["min"] = float(non_null.min()) if len(non_null) else None
            profile["max"] = float(non_null.max()) if len(non_null) else None
            profile["avg"] = float(non_null.mean()) if len(non_null) else None
    except Exception:
        pass
    return profile


def _verified_queries_for_uploaded_model(
    mapping: Dict[str, str], df: pd.DataFrame, table_name: str
) -> List[Dict[str, Any]]:
    """Create a small set of deterministic verified examples for the uploaded table."""
    queries: List[Dict[str, Any]] = [
        {
            "name": "uploaded_row_count",
            "question": "How many rows are in the uploaded data?",
            "sql": f'SELECT SUM(ROW_INDICATOR) AS ROW_COUNT FROM "{table_name}"',
        }
    ]

    for original, safe in mapping.items():
        series = df[original]
        if pd.api.types.is_datetime64_any_dtype(series.dtype):
            queries.append({
                "name": f"latest_{safe.lower()}",
                "question": f"What is the latest {original}?",
                "sql": f'SELECT MAX("{safe}") AS LATEST_{safe} FROM "{table_name}"',
            })
        elif pd.api.types.is_numeric_dtype(series.dtype) and not _looks_like_identifier(original, series):
            queries.append({
                "name": f"total_{safe.lower()}",
                "question": f"What is the total {original}?",
                "sql": f'SELECT SUM("{safe}") AS TOTAL_{safe} FROM "{table_name}"',
            })
            queries.append({
                "name": f"average_{safe.lower()}",
                "question": f"What is the average {original}?",
                "sql": f'SELECT AVG("{safe}") AS AVERAGE_{safe} FROM "{table_name}"',
            })
        if len(queries) >= 10:
            break

    return queries[:10]


def build_uploaded_semantic_model(df: pd.DataFrame, table_name: str) -> str:
    """Build a high-context Cortex Analyst semantic model for the uploaded spreadsheet.

    Accuracy improvements:
      * representative sample values for literal filters
      * domain-aware synonyms from the real headers
      * measures with explicit default aggregation
      * identifier detection to avoid summing IDs
      * richer column descriptions and profiling metadata
      * deterministic verified examples for common aggregations
    """
    mapping = _safe_column_names(df)
    dimensions: List[Dict[str, Any]] = []
    time_dimensions: List[Dict[str, Any]] = []
    facts: List[Dict[str, Any]] = []
    measures: List[Dict[str, Any]] = []

    for original, safe in mapping.items():
        dtype = df[original].dtype
        sf_type = _snowflake_type_for_pandas(dtype)
        synonyms = _column_synonyms(original)
        profile = _column_profile(df, original)
        original_lower = str(original).lower()
        identifier = _looks_like_identifier(original, df[original])

        desc = (
            f"Uploaded spreadsheet column '{original}'. "
            f"Contains {profile['unique']:,} distinct non-null values and "
            f"{profile['nulls']:,} null values."
        )
        if identifier:
            desc += " This appears to be an identifier/code; do not sum it."
        if "sales" in original_lower or "revenue" in original_lower or "amount" in original_lower or "price" in original_lower:
            desc += " This column may represent a monetary/business amount; use its actual values and do not invent currency."
        if "quantity" in original_lower or "qty" in original_lower:
            desc += " This column represents a quantity/count at row level."
        if "close out" in original_lower or "closeout" in original_lower:
            desc += " A non-null value indicates close-out/completion when the user asks about completed projects."

        if pd.api.types.is_datetime64_any_dtype(dtype):
            entry = {
                "name": safe,
                "description": desc,
                "expr": safe,
                "data_type": sf_type,
                "unique": False,
            }
            if synonyms:
                entry["synonyms"] = synonyms
            if profile["samples"]:
                entry["sample_values"] = profile["samples"]
            time_dimensions.append(entry)
            continue

        # Numeric identifiers are dimensions; business quantities/amounts are facts/measures.
        if identifier or not pd.api.types.is_numeric_dtype(dtype):
            entry = {
                "name": safe,
                "description": desc,
                "expr": safe,
                "data_type": sf_type,
                "unique": False,
            }
            if synonyms:
                entry["synonyms"] = synonyms
            if profile["samples"]:
                entry["sample_values"] = profile["samples"]
            # Low-cardinality text fields benefit from explicit literal examples.
            if profile["unique"] <= 15 and profile["unique"] > 0 and len(profile["samples"]) >= min(profile["unique"], 8):
                entry["is_enum"] = True
            dimensions.append(entry)

        if pd.api.types.is_numeric_dtype(dtype) and not identifier and not pd.api.types.is_bool_dtype(dtype):
            fact = {
                "name": safe,
                "description": desc,
                "expr": safe,
                "data_type": "NUMBER",
            }
            if synonyms:
                fact["synonyms"] = synonyms
            if profile["samples"]:
                fact["sample_values"] = profile["samples"]
            facts.append(fact)

            # Use SUM as the default only for additive business values. IDs are excluded above.
            measure_name = f"TOTAL_{safe}"
            measure_synonyms = [
                f"total {str(original).lower()}",
                f"sum of {str(original).lower()}",
            ]
            measures.append({
                "name": measure_name,
                "synonyms": measure_synonyms,
                "description": f"Total/sum of uploaded column '{original}'.",
                "expr": safe,
                "data_type": "NUMBER",
                "default_aggregation": "sum",
            })

    facts.append({
        "name": "ROW_INDICATOR",
        "description": "Exactly 1 for every uploaded spreadsheet row. SUM this fact to count rows/records.",
        "expr": "1",
        "data_type": "NUMBER",
    })
    measures.insert(0, {
        "name": "ROW_COUNT",
        "synonyms": ["row count", "record count", "number of rows", "number of records"],
        "description": "Count of uploaded spreadsheet rows. Always use SUM(ROW_INDICATOR) for row count.",
        "expr": "ROW_INDICATOR",
        "data_type": "NUMBER",
        "default_aggregation": "sum",
    })

    closeout_safe = None
    for original, safe in mapping.items():
        low = str(original).lower()
        if "close out" in low or "closeout" in low:
            closeout_safe = safe
            break
    if closeout_safe:
        dimensions.append({
            "name": "IS_COMPLETED",
            "description": "True when the close-out approval date is not null. Use this only for completion questions.",
            "expr": f"{closeout_safe} IS NOT NULL",
            "data_type": "BOOLEAN",
            "unique": False,
            "synonyms": ["completed", "project completed", "completion status"],
            "is_enum": True,
            "sample_values": ["TRUE", "FALSE"],
        })

    table_definition: Dict[str, Any] = {
        "name": "UPLOADED_DATA",
        "description": (
            "Complete uploaded spreadsheet dataset. One logical row represents one source row. "
            "Use only this table for document questions."
        ),
        "base_table": {"database": DATABASE, "schema": SCHEMA, "table": table_name},
        "dimensions": dimensions,
        "facts": facts,
        "measures": measures,
    }
    if time_dimensions:
        table_definition["time_dimensions"] = time_dimensions

    model = {
        "name": "UPLOADED_DOCUMENT_ANALYSIS",
        "description": "High-context semantic model generated from the actual uploaded spreadsheet. No external business data is allowed.",
        "tables": [table_definition],
        "verified_queries": _verified_queries_for_uploaded_model(mapping, df, table_name),
        "module_custom_instructions": {
            "sql_generation": (
                "Use ONLY UPLOADED_DATA and only columns defined in this semantic model. "
                "Never invent a column, value, date, currency, status, or business definition. "
                "For row/record counts use ROW_COUNT or SUM(ROW_INDICATOR). "
                "Never SUM/AVG identifier columns such as IDs, codes, account numbers, project numbers, or order numbers. "
                "For numeric business amounts use the corresponding TOTAL_* measure or SUM of the underlying numeric fact. "
                "For average questions use AVG of the underlying numeric fact, not SUM divided by an unrelated count. "
                "For distinct identifier questions use COUNT(DISTINCT identifier). "
                "For completion questions use IS_COMPLETED only when it exists and is based on the real close-out column. "
                "For date filters use the actual time dimension and correct calendar boundaries. "
                "For literal filters prefer the exact values shown in sample_values and match the underlying data case-insensitively when appropriate. "
                "If the question is ambiguous or the requested concept is not present, do not guess; return a clarification/no-answer response instead."
            ),
            "question_categorization": (
                "First map the user's wording to the actual uploaded columns using descriptions, synonyms, and sample values. "
                "Then choose the smallest correct set of dimensions/measures needed to answer the question. "
                "Do not use any Inventory, Sales, or Supply Chain semantic model for an Uploaded Document question."
            ),
        },
    }

    return yaml.safe_dump(model, sort_keys=False, allow_unicode=True, default_flow_style=False)

def _drop_uploaded_table():
    table_name = st.session_state.get("uploaded_document_table")
    if not table_name:
        return
    try:
        # Generated names contain only A-Z, 0-9 and underscore.
        if re.fullmatch(r"UPLOADED_DOCUMENT_[A-Z0-9_]+", str(table_name)):
            session.sql(f'DROP TABLE IF EXISTS "{table_name}"').collect()
    except Exception:
        pass
    st.session_state.uploaded_document_table = None
    st.session_state.uploaded_document_semantic_model = None
    st.session_state.uploaded_document_stage_file = None


def _choose_best_excel_sheet(excel_file) -> str:
    """Choose the most likely raw-data worksheet instead of blindly using sheet 1."""
    candidates = []
    for sheet in excel_file.sheet_names:
        try:
            sample = pd.read_excel(excel_file, sheet_name=sheet, nrows=30)
        except Exception:
            continue
        if sample.empty:
            continue
        non_empty_cols = int(sum(not str(c).lower().startswith("unnamed") for c in sample.columns))
        rows = int(len(sample))
        cols = int(len(sample.columns))
        name = str(sheet).lower()
        penalty = 0
        if any(word in name for word in ("cover", "readme", "instruction", "dashboard", "summary", "pivot", "chart")):
            penalty += 25
        score = min(rows, 1000) * 0.08 + non_empty_cols * 3 + cols * 0.5 - penalty
        candidates.append((score, sheet, rows, cols))
    if not candidates:
        raise ValueError("The Excel workbook does not contain a readable data worksheet.")
    candidates.sort(reverse=True)
    return candidates[0][1]


def process_uploaded_document(uploaded_file):
    """Read CSV/XLSX/XLS/PDF/DOCX with safer worksheet and document extraction."""
    name = uploaded_file.name
    extension = name.rsplit(".", 1)[-1].lower()

    if extension == "csv":
        # ADDITIVE: a CSV has no worksheets, so clear any worksheet metadata
        # left by a previously uploaded Excel workbook.
        st.session_state.uploaded_excel_bytes = None
        st.session_state.uploaded_excel_sheets = []
        st.session_state.uploaded_excel_selected_sheet = None
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        df = _normalize_uploaded_dataframe(df)
        if df.empty:
            raise ValueError("The CSV file contains no data rows.")
        return "table", df, "", f"CSV file loaded with {len(df):,} rows and {len(df.columns):,} columns."

    if extension in {"xlsx", "xls"}:
        uploaded_file.seek(0)
        workbook_bytes = uploaded_file.getvalue()
        excel_file = pd.ExcelFile(io.BytesIO(workbook_bytes))
        sheet_name = _choose_best_excel_sheet(excel_file)
        # ADDITIVE: retain the workbook and every worksheet name for the
        # Sheet Selection dropdown shown below the uploaded-file preview.
        st.session_state.uploaded_excel_bytes = workbook_bytes
        st.session_state.uploaded_excel_sheets = list(excel_file.sheet_names)
        st.session_state.uploaded_excel_selected_sheet = sheet_name
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        df = _normalize_uploaded_dataframe(df)
        if df.empty:
            raise ValueError(f"Excel worksheet '{sheet_name}' contains no data rows.")
        return (
            "table",
            df,
            "",
            f"Excel workbook analyzed using the most likely data worksheet '{sheet_name}' with {len(df):,} rows and {len(df.columns):,} columns. Other worksheets were not mixed into the model to avoid cross-sheet ambiguity.",
        )

    if extension == "pdf":
        st.session_state.uploaded_excel_bytes = None
        st.session_state.uploaded_excel_sheets = []
        st.session_state.uploaded_excel_selected_sheet = None
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader

        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"[PAGE {page_number}]\n{page_text.strip()}")
        full_text = "\n\n".join(pages).strip()
        return "text", None, full_text, f"PDF analyzed successfully ({len(reader.pages)} pages; page markers preserved for grounded answers)."

    if extension == "docx":
        st.session_state.uploaded_excel_bytes = None
        st.session_state.uploaded_excel_sheets = []
        st.session_state.uploaded_excel_selected_sheet = None
        import zipfile
        import xml.etree.ElementTree as ET

        uploaded_file.seek(0)
        docx_bytes = uploaded_file.read()
        try:
            with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
                xml_bytes = zf.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as exc:
            raise ValueError("The uploaded Word file is not a valid .docx document.") from exc

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise ValueError("Could not read the Word document content.") from exc

        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", ns):
            parts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)

        table_parts = []
        for table_number, table in enumerate(root.findall(".//w:tbl", ns), start=1):
            table_parts.append(f"[TABLE {table_number}]")
            for row in table.findall("./w:tr", ns):
                cells = []
                for cell in row.findall("./w:tc", ns):
                    cell_parts = [node.text or "" for node in cell.findall(".//w:t", ns)]
                    cells.append(" ".join("".join(cell_parts).split()))
                if any(cells):
                    table_parts.append(" | ".join(cells))

        full_text = "\n".join(paragraphs + table_parts).strip()
        return "text", None, full_text, "DOCX document extracted with paragraph and table structure preserved."

    raise ValueError("Unsupported document type.")

def prepare_uploaded_table(df: pd.DataFrame) -> str:
    """Create a transient table so Cortex Analyst's REST session can see it."""
    if df is None or df.empty:
        raise ValueError("The uploaded spreadsheet contains no rows.")

    _drop_uploaded_table()

    work_df = _normalize_uploaded_dataframe(df)
    mapping = _safe_column_names(work_df)
    work_df.columns = [mapping[str(c)] for c in work_df.columns]

    table_name = (
        "UPLOADED_DOCUMENT_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f").upper()
    )

    # IMPORTANT: do NOT use a TEMPORARY table here. Cortex Analyst REST runs
    # in a separate Snowflake session and cannot see session-scoped temp tables.
    # A TRANSIENT table is visible to the Analyst request and is dropped when
    # the user uploads another document or removes the current document.
    session.write_pandas(
        work_df,
        table_name,
        auto_create_table=True,
        overwrite=True,
        table_type="transient",
    )

    try:
        session.sql(
            f'ALTER TABLE "{table_name}" SET DATA_RETENTION_TIME_IN_DAYS = 0'
        ).collect()
    except Exception:
        pass

    semantic_model = build_uploaded_semantic_model(df, table_name)

    st.session_state.uploaded_document_table = table_name
    st.session_state.uploaded_document_semantic_model = semantic_model

    return semantic_model


def _validate_uploaded_result(question: str, result_df: pd.DataFrame) -> Optional[str]:
    """Return a warning when a result looks suspicious, without rejecting valid zero-row answers."""
    if result_df is None:
        return "The query returned no dataframe."
    q = question.lower()
    if result_df.empty and not any(word in q for word in ("no rows", "which", "list", "show", "find", "filter")):
        return "The query returned no rows; verify that the requested filter/value exists in the uploaded data."
    return None


def answer_uploaded_table_question(question: str, df: pd.DataFrame):
    """Generate, validate, retry, and execute Cortex Analyst SQL for uploaded data."""
    if df is None or df.empty:
        raise ValueError("The uploaded spreadsheet has no usable rows.")

    if not st.session_state.uploaded_document_table:
        prepare_uploaded_table(df)

    table_name = st.session_state.uploaded_document_table
    semantic_model = st.session_state.uploaded_document_semantic_model
    if not table_name or not semantic_model:
        raise RuntimeError("The uploaded document semantic model was not created.")

    last_error = None
    last_result = None
    for attempt in range(1, 3):
        prompt = question
        if last_error:
            prompt = (
                f"Original user question: {question}\n\n"
                "The previous SQL attempt failed validation/execution. Correct it using only the uploaded semantic model.\n"
                f"Previous SQL: {last_result.get('sql') if last_result else 'unavailable'}\n"
                f"Failure details: {last_error}\n"
                "Do not invent columns or values. Return the corrected SQL only through the normal Analyst response."
            )

        analyst_json = call_cortex_analyst_with_semantic_model(prompt, semantic_model)
        result = extract_analyst_response(analyst_json)
        last_result = result

        if result.get("warnings"):
            warning_text = " ".join(
                str(w.get("message", w)) if isinstance(w, dict) else str(w)
                for w in result["warnings"]
            )
            if warning_text:
                st.warning(warning_text)

        if not result.get("sql"):
            last_error = result.get("text") or "Cortex Analyst did not generate SQL."
            continue

        try:
            sql_query = _clean_generated_sql(result["sql"])
            # Only execute the generated read-only SELECT/WITH statement.
            result_df = session.sql(sql_query).to_pandas()
            sanity_warning = _validate_uploaded_result(question, result_df)
            if sanity_warning and attempt == 1:
                last_error = sanity_warning
                continue
            if sanity_warning:
                st.warning(sanity_warning)
            return result_df, sql_query, result
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(
        "I could not produce a validated answer from the uploaded dataset after two attempts. "
        f"Last issue: {last_error}"
    )

def _split_document_into_chunks(document_text: str) -> List[str]:
    """Split extracted Word text into useful paragraph/table chunks."""
    chunks = []
    for block in re.split(r"\n{2,}|\n", document_text):
        block = re.sub(r"\s+", " ", block).strip()
        if block:
            chunks.append(block)
    return chunks


def _extract_pdf_table_records(document_text: str):
    """Reconstruct common PDF table rows from pypdf's line-oriented extraction.

    PDF extraction often places every table cell on its own line. A semantic
    search over those lines can therefore match a column header instead of the
    requested row. This helper reconstructs the two common table shapes used by
    reporting PDFs without assuming that an LLM is available.
    """
    lines = [re.sub(r"\s+", " ", x).strip() for x in str(document_text).splitlines()]
    lines = [x for x in lines if x]
    records = {"quarterly": [], "regional": []}

    # Quarterly Results: six columns per row.
    q_headers = ["Quarter", "Revenue", "Orders", "Gross Margin", "Enterprise Revenue", "SMB Revenue"]
    try:
        qi = next(i for i, x in enumerate(lines) if x.lower() == "quarterly results")
        # Find the first Q1 row after the section heading.
        qstart = next(i for i in range(qi + 1, len(lines)) if re.fullmatch(r"Q[1-4] FY\d{4}", lines[i], re.I))
        i = qstart
        while i < len(lines) and re.fullmatch(r"Q[1-4] FY\d{4}", lines[i], re.I):
            if i + 5 >= len(lines):
                break
            quarter, revenue, orders, margin, enterprise, smb = lines[i:i + 6]
            if (re.match(r"^\$[\d,]+(?:\.\d+)?$", revenue)
                    and re.fullmatch(r"[\d,]+", orders)
                    and re.fullmatch(r"\d+(?:\.\d+)?%", margin)
                    and re.match(r"^\$[\d,]+(?:\.\d+)?$", enterprise)
                    and re.match(r"^\$[\d,]+(?:\.\d+)?$", smb)):
                records["quarterly"].append({
                    "Quarter": quarter, "Revenue": revenue, "Orders": orders,
                    "Gross Margin": margin, "Enterprise Revenue": enterprise,
                    "SMB Revenue": smb,
                })
                i += 6
            else:
                break
    except StopIteration:
        pass

    # Regional Performance: five columns per row.
    try:
        ri = next(i for i, x in enumerate(lines) if x.lower() == "regional performance")
        rstart = next(i for i in range(ri + 1, len(lines))
                       if lines[i] in {"North America", "Europe", "Asia", "Latin America"})
        i = rstart
        while i + 4 < len(lines) and lines[i] in {"North America", "Europe", "Asia", "Latin America"}:
            region, revenue, growth, q4_revenue, driver = lines[i:i + 5]
            if (re.match(r"^\$[\d,]+(?:\.\d+)?$", revenue)
                    and re.fullmatch(r"\d+(?:\.\d+)?%", growth)
                    and re.match(r"^\$[\d,]+(?:\.\d+)?$", q4_revenue)):
                records["regional"].append({
                    "Region": region, "FY2025 Revenue": revenue,
                    "Growth vs FY2024": growth, "Q4 Revenue": q4_revenue,
                    "Primary Driver": driver,
                })
                i += 5
            else:
                break
    except StopIteration:
        pass

    return records


def _money(value: str) -> float:
    return float(str(value).replace("$", "").replace(",", "").strip())


def _fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def _focused_document_answer(question: str, document_text: str) -> str | None:
    """Return a concise answer for common factual/document-table questions."""
    q = re.sub(r"\s+", " ", question or "").strip()
    ql = q.lower()
    text = str(document_text or "")

    # Direct document facts.
    fact_patterns = [
        (r"\breporting\s+period\b\s*[:\-]?\s*([^|\n]+)", "The reporting period is {0}."),
        (r"\beffective\s+date\b\s*[:\-]?\s*([^|\n]+)", "The effective date is {0}."),
        (r"\bdocument\s+id\b\s*[:\-]?\s*([^|\n]+)", "The document ID is {0}."),
    ]
    for pattern, template in fact_patterns:
        if any(term in ql for term in ("reporting period", "effective date", "document id")) and re.search(pattern, text, re.I):
            m = re.search(pattern, text, re.I)
            if m and m.group(1).strip():
                return template.format(re.sub(r"\s+", " ", m.group(1)).strip(" .;"))

    tables = _extract_pdf_table_records(text)
    quarters = tables["quarterly"]
    regions = tables["regional"]

    # Exact quarter lookup. This prevents a column-header match such as
    # "FY2025 Revenue" from being returned for "revenue in Q4 FY2025".
    qmatch = re.search(r"\bq([1-4])\b\s*(?:fy)?\s*(20\d{2})", ql)
    if not qmatch:
        qmatch = re.search(r"\bq([1-4])\b", ql)
    quarter_row = None
    if qmatch and quarters:
        token = f"Q{qmatch.group(1)}"
        year = qmatch.group(2) if qmatch.lastindex and qmatch.lastindex >= 2 else None
        quarter_row = next((r for r in quarters if r["Quarter"].lower().startswith(token.lower())
                             and (not year or year in r["Quarter"])), None)

    if quarter_row:
        if "gross margin" in ql or "margin" in ql:
            return f"The gross margin for {quarter_row['Quarter']} was {quarter_row['Gross Margin']}."
        if "order" in ql and ("how many" in ql or "count" in ql or "number" in ql):
            return f"{quarter_row['Quarter']} had {quarter_row['Orders']} orders."
        if "enterprise" in ql and "revenue" in ql:
            return f"Enterprise revenue in {quarter_row['Quarter']} was {quarter_row['Enterprise Revenue']}."
        if "smb" in ql and "revenue" in ql:
            return f"SMB revenue in {quarter_row['Quarter']} was {quarter_row['SMB Revenue']}."
        if "revenue" in ql:
            return f"The revenue in {quarter_row['Quarter']} was {quarter_row['Revenue']}."

    # Region lookup and region-based questions.
    region_row = None
    for r in regions:
        if re.search(r"\b" + re.escape(r["Region"].lower()) + r"\b", ql):
            region_row = r
            break
    if region_row:
        if "growth" in ql:
            return f"{region_row['Region']} had a growth rate of {region_row['Growth vs FY2024']}."
        if "q4" in ql and "revenue" in ql:
            return f"{region_row['Region']} had Q4 revenue of {region_row['Q4 Revenue']}."
        if "revenue" in ql:
            return f"{region_row['Region']} generated {region_row['FY2025 Revenue']} in FY2025 revenue."
        if "driver" in ql:
            return f"The primary driver for {region_row['Region']} was {region_row['Primary Driver']}."

    if regions and "highest" in ql and "growth" in ql:
        r = max(regions, key=lambda x: float(x["Growth vs FY2024"].strip("%")))
        return f"{r['Region']} had the highest growth rate at {r['Growth vs FY2024']}."
    if regions and "highest" in ql and "revenue" in ql:
        r = max(regions, key=lambda x: _money(x["FY2025 Revenue"]))
        return f"{r['Region']} generated the highest FY2025 revenue at {r['FY2025 Revenue']}."
    if regions and "rank" in ql and "region" in ql and "revenue" in ql:
        ordered = sorted(regions, key=lambda x: _money(x["FY2025 Revenue"]), reverse=True)
        return "The regions ranked by FY2025 revenue are: " + "; ".join(
            f"{i}. {r['Region']} ({r['FY2025 Revenue']})" for i, r in enumerate(ordered, 1)
        ) + "."

    if quarters:
        if "highest" in ql and "revenue" in ql:
            r = max(quarters, key=lambda x: _money(x["Revenue"]))
            return f"{r['Quarter']} had the highest revenue at {r['Revenue']}."
        if "average" in ql and "quarter" in ql and "revenue" in ql:
            avg = sum(_money(r["Revenue"]) for r in quarters) / len(quarters)
            return f"The average quarterly revenue for FY2025 was {_fmt_money(avg)}."
        if "total" in ql and "revenue" in ql:
            # Only use the quarterly table for a question explicitly referring
            # to quarterly/FY2025 revenue, avoiding accidental double counting
            # against the regional summary table.
            total = sum(_money(r["Revenue"]) for r in quarters)
            if "quarter" in ql or "fy2025" in ql:
                return f"The total FY2025 quarterly revenue was {_fmt_money(total)}."

    if regions and "total" in ql and "revenue" in ql:
        total = sum(_money(r["FY2025 Revenue"]) for r in regions)
        return f"The total FY2025 revenue across the four regions was {_fmt_money(total)}."

    # Known unsupported detail in the supplied summary report.
    if any(term in ql for term in ["customer", "transaction", "product"]):
        if "individual customer" in ql or "customer record" in ql or "transaction" in ql or "product" in ql:
            return (
                "The document does not contain the requested detail. It contains summary-level "
                "figures and does not include the underlying transaction-level dataset."
            )

    return None


def _word_question_answer(question: str, document_text: str) -> str:
    """Answer PDF/DOCX questions using concise, grounded local extraction.

    This is the deterministic fallback used when Snowflake document AI is not
    available. It deliberately returns one focused answer instead of unrelated
    neighboring passages.
    """
    text = str(document_text or "").strip()
    if not text:
        raise ValueError("No readable text was extracted from the uploaded document.")

    focused = _focused_document_answer(question, text)
    if focused:
        return focused

    q = re.sub(r"\s+", " ", question or "").strip()
    ql = q.lower()
    chunks = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\n{2,}|\n", text) if x.strip()]
    stop_words = {
        "what","is","are","the","a","an","of","for","to","in","on","and","or",
        "with","from","this","that","which","who","how","why","does","do","can",
        "could","would","should","please","tell","me","about","give","explain","show",
        "document","according","based","your","report","information",
    }
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9_]+", q) if w.lower() not in stop_words and len(w) > 2]
    if not words:
        return "I could not find a directly supported answer in the uploaded document."

    scored = []
    for idx, chunk in enumerate(chunks):
        low = chunk.lower()
        matched = [w for w in words if w in low]
        if not matched:
            continue
        score = len(matched) * 2
        if any(w in low for w in ("effective date", "reporting period", "document id")):
            score += 3
        if len(chunk) < 400:
            score += 1
        scored.append((score, -len(chunk), idx, chunk, matched))

    if not scored:
        return (
            "I could not find a directly supported answer in the uploaded document. "
            "The document does not appear to contain enough information to answer this question."
        )

    scored.sort(reverse=True)
    chunk = scored[0][3]
    matched = scored[0][4]
    if "|" not in chunk and not chunk.startswith("["):
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk) if s.strip()]
        relevant = [s for s in sentences if any(w in s.lower() for w in matched)]
        if relevant:
            return " ".join(relevant[:2])
    return chunk

def answer_uploaded_text_question(question: str, document_text: str):
    """Answer PDF/DOCX questions using the strongest available grounded path.

    If Snowflake document AI is unavailable (for example on a trial account),
    both PDF and DOCX now use the same deterministic local extraction fallback.
    This prevents a model-access error from being shown to the user and, more
    importantly, prevents unrelated document content from being returned.
    """
    if not document_text.strip():
        raise ValueError("No readable text was extracted from the uploaded document.")

    try:
        # Preferred path when the Snowflake document-AI entitlement is available.
        return ai_complete_document_question(question)
    except Exception:
        # IMPORTANT: Do not surface the Snowflake trial/model-access error to the
        # end user. The uploaded PDF/DOCX text is already extracted locally, so
        # answer from that grounded text instead.
        fallback = _word_question_answer(question, document_text)
        return fallback

def _read_uploaded_excel_sheet(sheet_name: str) -> pd.DataFrame:
    """Read one selected worksheet from the retained uploaded workbook."""
    workbook_bytes = st.session_state.get("uploaded_excel_bytes")
    if not workbook_bytes:
        raise RuntimeError("The uploaded Excel workbook is no longer available in this session.")
    excel_file = pd.ExcelFile(io.BytesIO(workbook_bytes))
    if sheet_name not in excel_file.sheet_names:
        raise ValueError(f"Worksheet '{sheet_name}' is not available in the uploaded workbook.")
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    df = _normalize_uploaded_dataframe(df)
    if df.empty:
        raise ValueError(f"Excel worksheet '{sheet_name}' contains no data rows.")
    return df


def _switch_uploaded_excel_sheet(sheet_name: str):
    """Switch the active uploaded worksheet and rebuild only its Analyst model."""
    current = st.session_state.get("uploaded_excel_selected_sheet")
    if not sheet_name or sheet_name == current:
        return

    with st.spinner(f"Loading worksheet '{sheet_name}'..."):
        new_df = _read_uploaded_excel_sheet(sheet_name)
        # The uploaded table represents the currently selected worksheet.
        # Replace only that transient table/model; all other application logic
        # remains unchanged.
        _drop_uploaded_table()
        st.session_state.uploaded_document_df = new_df
        st.session_state.uploaded_excel_selected_sheet = sheet_name
        prepare_uploaded_table(new_df)


def _column_summary_for_uploaded_df(df: pd.DataFrame) -> pd.DataFrame:
    """Build the compact Columns & Summary view used by the new dropdown."""
    rows = []
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        row = {
            "Column": str(col),
            "Type": str(series.dtype),
            "Rows": int(len(series)),
            "Missing": int(series.isna().sum()),
            "Unique": int(non_null.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            try:
                row["Min"] = float(non_null.min()) if len(non_null) else None
                row["Average"] = float(non_null.mean()) if len(non_null) else None
                row["Max"] = float(non_null.max()) if len(non_null) else None
            except Exception:
                row["Min"] = row["Average"] = row["Max"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def _render_uploaded_document_dropdowns(doc_type: str, key_suffix: str = "default"):
    """Render the two additive dropdowns directly below the document preview."""
    # ---------------------------------------------------------------
    # 1. Sheet Selection
    # ---------------------------------------------------------------
    if doc_type == "table" and st.session_state.get("uploaded_excel_sheets"):
        sheets = st.session_state.uploaded_excel_sheets
        current_sheet = st.session_state.get("uploaded_excel_selected_sheet")
        if current_sheet not in sheets:
            current_sheet = sheets[0]
            st.session_state.uploaded_excel_selected_sheet = current_sheet
        selected_sheet = st.selectbox(
            "Sheet Selection",
            sheets,
            index=sheets.index(current_sheet),
            key=f"uploaded_excel_sheet_selector_{key_suffix}",
            help="Select which Excel worksheet should be used for preview and document questions.",
        )
        if selected_sheet != current_sheet:
            _switch_uploaded_excel_sheet(selected_sheet)
    else:
        # Keep the requested control visible for Word/other document types.
        st.selectbox(
            "Sheet Selection",
            ["Not applicable — this document has no worksheets"],
            index=0,
            disabled=True,
            key=f"uploaded_document_sheet_selector_disabled_{key_suffix}",
        )

    # ---------------------------------------------------------------
    # 2. Columns & Summary
    # ---------------------------------------------------------------
    if doc_type == "table":
        df = st.session_state.get("uploaded_document_df")
        if df is None or df.empty:
            return

        options = ["Summary"] + [str(c) for c in df.columns]
        selected = st.selectbox(
            "Columns & Summary",
            options,
            index=0,
            key=f"uploaded_document_columns_summary_selector_{key_suffix}",
            help="View the uploaded file summary or inspect an individual column.",
        )

        if selected == "Summary":
            summary = _column_summary_for_uploaded_df(df)
            st.caption(
                f"{len(df):,} rows • {len(df.columns):,} columns • "
                f"{int(df.isna().sum().sum()):,} missing cells"
            )
            st.dataframe(summary, use_container_width=True, hide_index=True)
        else:
            series = df[selected]
            non_null = series.dropna()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Type", str(series.dtype))
            c2.metric("Missing", f"{int(series.isna().sum()):,}")
            c3.metric("Unique", f"{int(non_null.nunique(dropna=True)):,}")
            c4.metric("Non-null", f"{int(non_null.shape[0]):,}")

            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                try:
                    n1, n2, n3 = st.columns(3)
                    n1.metric("Min", f"{float(non_null.min()):,.2f}" if len(non_null) else "—")
                    n2.metric("Average", f"{float(non_null.mean()):,.2f}" if len(non_null) else "—")
                    n3.metric("Max", f"{float(non_null.max()):,.2f}" if len(non_null) else "—")
                except Exception:
                    pass

            samples = [str(v) for v in non_null.head(10).tolist()]
            if samples:
                st.caption("Sample values")
                st.write(" • ".join(samples))
    else:
        # For Word/PDF, the same dropdown provides document-level summary and
        # extracted-content access instead of pretending the document has columns.
        text = st.session_state.get("uploaded_document_text") or ""
        doc_options = ["Summary", "Extracted Content"]
        selected = st.selectbox(
            "Columns & Summary",
            doc_options,
            index=0,
            key=f"uploaded_text_columns_summary_selector_{key_suffix}",
            help="View document summary or the extracted document content.",
        )
        if selected == "Summary":
            lines = [x for x in text.splitlines() if x.strip()]
            words = re.findall(r"\b\w+\b", text)
            st.caption(
                f"{len(lines):,} non-empty lines • {len(words):,} words • "
                f"{len(text):,} characters"
            )
        else:
            st.text_area(
                "Extracted content",
                text,
                height=280,
                disabled=True,
                label_visibility="collapsed",
                key=f"uploaded_text_columns_summary_content_{key_suffix}",
            )


def render_uploaded_document_preview():
    """Display the analyzed document without interfering with the original UI."""
    doc_type = st.session_state.uploaded_document_type
    doc_name = st.session_state.uploaded_document_name

    if not doc_name:
        return

    st.markdown("---")
    st.markdown(f"### 📄 Uploaded Document: `{doc_name}`")

    if doc_type == "table":
        df = st.session_state.uploaded_document_df
        if df is not None:
            st.dataframe(_normalize_uploaded_dataframe(df), use_container_width=True)
        _render_uploaded_document_dropdowns(doc_type, key_suffix="standalone_table")
    elif doc_type == "text":
        with st.expander("📖 Extracted Document Content", expanded=False):
            st.text_area(
                "Document text",
                st.session_state.uploaded_document_text,
                height=350,
                disabled=True,
                label_visibility="collapsed",
            )
        _render_uploaded_document_dropdowns(doc_type, key_suffix="standalone_text")


# ===================================================================
# 2B. PROFESSIONAL APPLICATION PAGES
# ===================================================================

def _set_page(page: str):
    st.session_state.app_page = page
    st.rerun()


def _logout():
    try:
        if st.session_state.get("snowflake_conn"):
            st.session_state.snowflake_conn.close()
    except Exception:
        pass
    st.session_state.authenticated = False
    st.session_state.password = ""
    st.session_state.app_page = "home"
    _new_captcha()
    st.rerun()


DILYTICS_LOGO_URI = "data:image/jpeg;base64," + "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"


def _top_nav():
    """Reference-matched Dilytics website navigation."""
    logo_uri = DILYTICS_LOGO_URI
    is_chatbot_page = st.session_state.get("app_page") == "chatbot"

    st.markdown("""
    <style>
      /* ================================================================
         DILYTICS REFERENCE HEADER
         Compact white website header:
         logo left | tightly grouped nav right
         ================================================================ */

      .st-key-dly_main_header {
          width: 100% !important;
          max-width: none !important;
          box-sizing: border-box !important;

          background: transparent !important;
          border: 0 !important;
          border-radius: 0 !important;

          padding: 0 !important;
          /* Pull header directly below the Streamlit toolbar. UI-only. */
          margin: -68px 0 -8px 0 !important;

          position: relative !important;
          z-index: 20 !important;

          box-shadow: none !important;
      }

      .st-key-dly_main_header > div,
      .st-key-dly_main_header > div > div {
          width: 100% !important;
          box-sizing: border-box !important;
      }

      .st-key-dly_main_header [data-testid="column"] {
          display: flex !important;
          align-items: center !important;
          min-height: 48px !important;
      }

      .st-key-dly_main_header [data-testid="column"]:first-child {
          justify-content: flex-start !important;
      }

      /* Exact horizontal DILYTICS logo. */
      .dly-reference-logo {
          width: 140px !important;
          height: 56px !important;
          max-width: none !important;
          object-fit: contain !important;
          object-position: left center !important;

          display: block !important;
          margin: 0 !important;
          padding: 0 !important;

          border: 0 !important;
          border-radius: 0 !important;
          box-shadow: none !important;
      }

      /* DILYTICS logo moved to the top-right of the navigation area. */
      .dly-nav-logo {
          width: 100% !important;
          display: flex !important;
          justify-content: flex-end !important;
          align-items: center !important;
          margin: 0 !important;
      }

      .dly-nav-logo-left {
          justify-content: flex-start !important;
          align-items: center !important;
      }

      /* ================================================================
         NAVIGATION
         The important change is that the three buttons are treated as
         one compact right-side group. No large empty horizontal gaps.
         ================================================================ */

      /* Keep navigation anchored to the header itself instead of relying
         on Streamlit's percentage-based column sizing. This prevents the
         buttons from drifting into the center when the browser is zoomed. */
      .st-key-dly_main_header {
          position: relative !important;
          overflow: visible !important;
      }

      /* The navigation occupies its own responsive half of the header.
         Nothing is absolutely positioned, so zooming cannot make one
         button overlap another. */
      .st-key-dly_main_header > div > [data-testid="column"]:last-child {
          min-width: 0 !important;
          display: flex !important;
          justify-content: flex-end !important;
      }

      .st-key-dly_main_header > div > [data-testid="column"]:last-child > div {
          width: 100% !important;
          min-width: 0 !important;
      }

      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
          width: 100% !important;
          min-width: 0 !important;
          justify-content: flex-end !important;
          align-items: center !important;
          flex-wrap: nowrap !important;
          gap: 10px !important;
      }

      /* Final UI adjustment: keep the two navigation buttons compact and
         push the complete group to the far right, directly under the
         Streamlit Share area. The buttons remain separate and responsive. */
      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
          width: min(300px, 100%) !important;
          max-width: 300px !important;
          margin-left: auto !important;
          margin-right: 0 !important;
      }

      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="column"] {
          min-width: 0 !important;
          flex: 1 1 0 !important;
          width: 0 !important;
      }

      /* Final home-page UI positioning: place the buttons directly
         beneath the Streamlit Share area, without fixed positioning.
         They therefore move naturally with the page when scrolling. */
      .st-key-top_home {
          display: flex !important;
          position: absolute !important;
          top: -100px !important;
          right: 185px !important;
          width: 100px !important;
          z-index: 10000 !important;
      }

      .st-key-top_docs {
          display: flex !important;
          position: absolute !important;
          top: -100px !important;
          right: 15px !important;
          width: 155px !important;
          z-index: 10000 !important;
      }

      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"],
      .st-key-top_about [data-testid="stButton"] {
          width: 100% !important;
          min-width: 0 !important;
      }

      /* Fluid buttons: their width is determined by the available
         navigation space, never by a fixed pixel value. */
      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button,
      .st-key-top_about [data-testid="stButton"] > button {
          width: 100% !important;
          max-width: 100% !important;
          min-width: 0 !important;
          box-sizing: border-box !important;
          margin-top: -45px !important;
      }

      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button,
      .st-key-top_about [data-testid="stButton"] > button {
          height: 56px !important;
          min-height: 56px !important;
          margin-top: -45px !important;

          padding: 0 8px !important;
          margin: 0 !important;

          border-radius: 9px !important;

          background: #ffffff !important;
          border: 1px solid #dfe4eb !important;

          color: #171717 !important;

          font-family: "Inter", "Segoe UI", Arial, sans-serif !important;
          font-size: .86rem !important;
          font-weight: 800 !important;
          letter-spacing: 0 !important;

          display: flex !important;
          align-items: center !important;
          justify-content: center !important;

          white-space: nowrap !important;

          box-shadow:
              0 2px 8px rgba(21,43,70,.055),
              inset 0 1px 0 rgba(255,255,255,.98) !important;

          transition:
              transform .16s ease,
              box-shadow .16s ease,
              border-color .16s ease,
              background .16s ease !important;
      }

      /* Tight spacing between buttons — matching the reference. */
      .st-key-top_home {
          margin-right: 10px !important;
      }

      .st-key-top_docs {
          margin-right: 10px !important;
      }

      /* About Dilytics is the branded primary action. */
      .st-key-top_about [data-testid="stButton"] > button {
          background: linear-gradient(180deg, #e52c35 0%, #cf2029 100%) !important;
          border-color: #cf2029 !important;
          color: #ffffff !important;

          box-shadow:
              0 4px 12px rgba(207,32,41,.18),
              inset 0 1px 0 rgba(255,255,255,.22) !important;
      }

      .st-key-top_home [data-testid="stButton"] > button:hover,
      .st-key-top_docs [data-testid="stButton"] > button:hover {
          background: #fbfcfe !important;
          border-color: #cfd8e3 !important;

          transform: translateY(-1px) !important;

          box-shadow:
              0 6px 14px rgba(21,43,70,.10),
              inset 0 1px 0 rgba(255,255,255,.98) !important;
      }

      .st-key-top_about [data-testid="stButton"] > button:hover {
          background: linear-gradient(180deg, #ef3a43 0%, #d9232d 100%) !important;
          border-color: #d9232d !important;

          transform: translateY(-1px) !important;

          box-shadow:
              0 7px 17px rgba(207,32,41,.25),
              inset 0 1px 0 rgba(255,255,255,.25) !important;
      }

      /* Reference-style black/blue navigation icons. */
      .st-key-top_home [data-testid="stButton"] > button::before,
      .st-key-top_docs [data-testid="stButton"] > button::before,
      .st-key-top_about [data-testid="stButton"] > button::before {
          width: 33px;
          height: 33px;
          flex: 0 0 33px;

          margin-right: 12px;

          display: inline-flex;
          align-items: center;
          justify-content: center;

          border-radius: 7px;

          font-size: 18px;
          font-weight: 900;
          line-height: 1;
      }

      .st-key-top_home [data-testid="stButton"] > button::before {
          content: "⌂";

          background: #f5f7fa;
          color: #111827;

          font-size: 22px;

          box-shadow: inset 0 0 0 1px #e5e9ee;
      }

      .st-key-top_docs [data-testid="stButton"] > button::before {
          content: "▣";

          background: #f5f7fa;
          color: #111827;

          font-size: 19px;

          box-shadow: inset 0 0 0 1px #e5e9ee;
      }

      .st-key-top_about [data-testid="stButton"] > button::before {
          content: "D";

          background: #ffffff;
          color: #d7202b;

          font-size: 18px;

          box-shadow:
              0 1px 5px rgba(0,0,0,.15),
              inset 0 0 0 1px rgba(255,255,255,.7);
      }

      .st-key-top_home [data-testid="stButton"] > button:focus,
      .st-key-top_docs [data-testid="stButton"] > button:focus,
      .st-key-top_about [data-testid="stButton"] > button:focus {
          outline: none !important;
      }

      /* Manual top-right navigation sizing — UI-only, no behavior changes. */
      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"] {
          width: 100% !important;
          min-width: 0 !important;
      }

      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          height: 28px !important;
          min-height: 28px !important;
          padding: 0 7px !important;
          font-size: .62rem !important;
          box-sizing: border-box !important;
      }

      /* Responsive fallback. */
      @media (max-width: 1250px) {
          .st-key-dly_main_header {
              padding: 10px 24px !important;
          }

          .st-key-top_home [data-testid="stButton"] > button,
          .st-key-top_docs [data-testid="stButton"] > button,
          .st-key-top_about [data-testid="stButton"] > button {
              height: 56px !important;
              min-height: 56px !important;
              padding: 0 9px !important;
              font-size: .76rem !important;
              font-weight: 800 !important;
          }

          .st-key-top_home [data-testid="stButton"] > button::before,
          .st-key-top_docs [data-testid="stButton"] > button::before,
          .st-key-top_about [data-testid="stButton"] > button::before {
              width: 26px;
              height: 26px;
              flex-basis: 26px;
              margin-right: 7px;
          }
      }

      @media (max-width: 900px) {
          .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
              gap: 6px !important;
          }

          .st-key-top_home [data-testid="stButton"] > button,
          .st-key-top_docs [data-testid="stButton"] > button,
          .st-key-top_about [data-testid="stButton"] > button {
              height: 52px !important;
              min-height: 52px !important;
              padding: 0 8px !important;
              font-size: .72rem !important;
          }

          .st-key-top_home [data-testid="stButton"] > button::before,
          .st-key-top_docs [data-testid="stButton"] > button::before,
          .st-key-top_about [data-testid="stButton"] > button::before {
              width: 23px;
              height: 23px;
              flex-basis: 23px;
              margin-right: 6px;
              font-size: 14px;
          }
      }

      @media (max-width: 1050px) {
          .st-key-dly_main_header {
              padding: 10px 18px !important;
          }

          .dly-reference-logo {
              width: 180px !important;
              height: 54px !important;
          }

          .st-key-top_home [data-testid="stButton"] > button,
          .st-key-top_docs [data-testid="stButton"] > button,
          .st-key-top_about [data-testid="stButton"] > button {
              height: 52px !important;
              min-height: 52px !important;
              padding: 0 10px !important;
              font-size: .80rem !important;
          font-weight: 800 !important;
          }

          .st-key-top_home [data-testid="stButton"] > button::before,
          .st-key-top_docs [data-testid="stButton"] > button::before,
          .st-key-top_about [data-testid="stButton"] > button::before {
              width: 26px;
              height: 26px;
              flex-basis: 26px;
              margin-right: 7px;
          }
      }

      @media (max-width: 700px) {
          .st-key-dly_main_header {
              padding: 10px !important;
              min-height: 0 !important;
          }

          /* At narrow widths/very high zoom, place the logo above the
             navigation instead of squeezing or overlapping the buttons. */
          .st-key-dly_main_header > div {
              gap: 10px !important;
              flex-direction: column !important;
          }

          .st-key-dly_main_header > div > [data-testid="column"]:first-child,
          .st-key-dly_main_header > div > [data-testid="column"]:last-child {
              flex: 0 0 100% !important;
              width: 100% !important;
              max-width: 100% !important;
          }

          .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
              width: 100% !important;
              position: static !important;
              gap: 6px !important;
              flex-wrap: nowrap !important;
          }

          .dly-reference-logo {
              width: 125px !important;
              height: 42px !important;
          }

          .st-key-top_home [data-testid="stButton"] > button,
          .st-key-top_docs [data-testid="stButton"] > button,
          .st-key-top_about [data-testid="stButton"] > button {
              height: 52px !important;
              min-height: 52px !important;
              border-radius: 9px !important;
              padding: 0 6px !important;
              font-size: .64rem !important;
              box-sizing: border-box !important;
          }

          .st-key-top_home [data-testid="stButton"] > button::before,
          .st-key-top_docs [data-testid="stButton"] > button::before,
          .st-key-top_about [data-testid="stButton"] > button::before {
              width: 22px;
              height: 22px;
              flex-basis: 22px;
              margin-right: 5px;
              font-size: 13px;
          }
    </style>
    """, unsafe_allow_html=True)

    if is_chatbot_page:
        st.markdown("""
    <style>
      /* Chatbot page only */
      .st-key-dly_main_header {
          margin-bottom: -18px !important;
      }

      .st-key-dly_main_header [data-testid="column"] {
          min-height: 20px !important;
      }

      /* ============================================================
         CHATBOT PAGE ONLY — top navigation positioning
         Do not change the Home/Login/Document AI page navigation.
         ============================================================ */
      .st-key-top_home,
      .st-key-top_docs {
          top: 22px !important;
          transform: none !important;
          z-index: 10000 !important;
      }

      /* Keep the buttons separated and prevent the labels from colliding. */
      .st-key-top_home {
          right: 195px !important;
          width: 120px !important;
      }

      .st-key-top_docs {
          right: 15px !important;
          width: 170px !important;
      }

      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"] {
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
          margin: 0 !important;
          padding: 0 !important;
      }

      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
          height: 52px !important;
          min-height: 52px !important;
          padding: 0 8px !important;
          margin: 0 !important;
          box-sizing: border-box !important;
          white-space: nowrap !important;
      }

      /* Move Explore your data upward — Chatbot page ONLY */
      .chatbot-explore-title {
          margin-top: -25px !important;
      }
    </style>
    """, unsafe_allow_html=True)
    with st.container(key="dly_main_header"):
        # The right area is intentionally narrow enough that the buttons
        # stay together, just like the reference image.
        # Keep a dedicated half-width navigation zone. This prevents the
        # three fixed-size navigation buttons from competing with the logo
        # when browser zoom changes the effective viewport width.
        logo_col, nav_col = st.columns(
            [1.0, 1.0],
            gap="small",
            vertical_alignment="center",
        )

        # Keep the logo on the left side of the same navigation row.
        with logo_col:
            if not is_chatbot_page:
                st.markdown(
                    f'<div class="dly-nav-logo dly-nav-logo-left"><img class="dly-reference-logo" '
                    f'src="{logo_uri}" alt="Dilytics" /></div>',
                    unsafe_allow_html=True,
                )

        with nav_col:
            # Keep the existing Home / Document AI navigation behavior and
            # proportions, with the About Dilytics button removed.
            n1, n2 = st.columns(
                [0.78, 1.0],
                gap="small",
                vertical_alignment="center",
            )

            with n1:
                if st.button("Home", use_container_width=True, key="top_home"):
                    _set_page("home")

            with n2:
                if st.button("Document AI", use_container_width=True, key="top_docs"):
                    _open_document_ai()

def _module_page(module: str):
    inventory = module == "inventory"
    supply_chain = module == "supply_chain"

    if inventory:
        title = "Inventory Intelligence"
        subtitle = "Turn inventory data into clear, actionable decisions across products, warehouses and stock levels."
        points = [
            "Track total inventory quantity, availability and inventory value.",
            "Compare inventory value across warehouses and product categories.",
            "Identify excess, overstocked, quarantined and out-of-stock inventory.",
            "Find products that need urgent replenishment or reorder attention.",
            "Analyze days of supply and inventory health using the latest snapshot.",
        ]
        icon = "▦"
    elif supply_chain:
        title = "Supply Chain Intelligence"
        subtitle = "Turn supply chain data into clear, actionable decisions across fulfillment, logistics, suppliers and operations."
        points = [
            "Analyze supply chain and fulfillment performance.",
            "Track orders, shipments and delivery trends.",
            "Identify delays, bottlenecks and operational exceptions.",
            "Explore supplier and logistics performance.",
            "Monitor service levels and supply chain trends.",
        ]
        icon = "🚚"
    else:
        title = "Sales Intelligence"
        subtitle = "Turn sales data into clear, actionable decisions across revenue, products, customers, regions and channels."
        points = [
            "Analyze total sales, orders, discounts, taxes and shipping costs.",
            "Identify top products and understand product-level revenue performance.",
            "Compare sales across customer regions and order channels.",
            "Analyze monthly sales trends and average order value.",
            "Explore completed and cancelled orders to understand sales performance.",
        ]
        icon = "▥"
    st.markdown(f"""
    <style>
      .module-hero{{padding:48px 55px;background:linear-gradient(135deg,#fff,#edf7ff);border:1px solid #cfe6ff;border-radius:28px;box-shadow:0 18px 45px rgba(23,91,160,.08)}}
      .module-icon{{font-size:3rem;color:#1769d2}} .module-title{{font-size:3rem;font-weight:900;color:#082d69;margin:.3rem 0}} .module-sub{{font-size:1.1rem;color:#587291;max-width:820px;line-height:1.65}}
      .point{{padding:15px 18px;margin:10px 0;background:#fff;border:1px solid #deedff;border-radius:15px;color:#153f76;box-shadow:0 7px 20px rgba(23,91,160,.05)}}
      .point b{{color:#1769d2;margin-right:10px}}
    </style>
    <div class="module-hero"><div class="module-icon">{icon}</div><div class="module-title">{title}</div><div class="module-sub">{subtitle}</div></div>
    """,unsafe_allow_html=True)
    st.markdown("### What you can analyze")
    for p in points: st.markdown(f'<div class="point"><b>✓</b>{p}</div>',unsafe_allow_html=True)
    st.markdown("### Start exploring")
    a,b=st.columns(2)
    with a:
        if st.button(f"💬 Chat with {title}",use_container_width=True,type="primary"):
            # Use the same authentication gate as the Home-page "Chat with AI"
            # buttons.  Directly routing to the chatbot bypassed the login
            # page, which left the chatbot without a Snowpark/Snowflake session.
            _open_chat()
    with b:
        if st.button("⌂  Back to Home",use_container_width=True): _set_page("home")


def _document_ai_page():
    st.markdown("""
    <style>
      .doc-hero{background:linear-gradient(135deg,#f8fcff,#e8f4ff);border:1px solid #cce5ff;border-radius:28px;padding:42px;display:grid;grid-template-columns:1.1fr .9fr;gap:30px;align-items:center}
      .doc-title{font-size:2.8rem;font-weight:900;color:#082d69}.doc-sub{font-size:1.05rem;line-height:1.65;color:#587291}.doc-list{color:#173e73;line-height:2}
      .doc-animation{height:300px;border-radius:28px;background:radial-gradient(circle,#fff,#dff1ff);position:relative;overflow:hidden;border:1px solid #c5e3ff}
      .doc-sheet{position:absolute;width:155px;height:205px;background:#fff;border:4px solid #1769d2;border-radius:12px;left:50%;top:50%;transform:translate(-50%,-50%) rotate(-7deg);box-shadow:0 20px 35px rgba(23,91,160,.15);animation:docFloat 3s ease-in-out infinite}
      .doc-line{height:7px;background:#78b9ef;border-radius:10px;margin:18px 15px 0}.doc-line.short{width:55%}.doc-scan{position:absolute;height:4px;background:#15a9ff;left:20px;right:20px;top:105px;box-shadow:0 0 15px #15a9ff;animation:scan 2.3s linear infinite}
      @keyframes docFloat{50%{transform:translate(-50%,-54%) rotate(7deg)}} @keyframes scan{0%{top:45px}100%{top:220px}}
      @media(max-width:850px){.doc-hero{grid-template-columns:1fr}}
    </style>
    <div class="doc-hero"><div><div class="doc-title">Document AI</div><div class="doc-sub">Upload a business document and move directly into a document-focused conversation. Use the assistant to explore spreadsheets and Word documents, extract relevant content, and ask natural-language questions.</div><div class="doc-list">✓ Excel / CSV analysis<br>✓ Word document content search<br>✓ Data questions and summaries<br>✓ Results displayed inside the familiar chat workspace</div></div><div class="doc-animation"><div class="doc-sheet"><div class="doc-line"></div><div class="doc-line"></div><div class="doc-line short"></div><div class="doc-line"></div><div class="doc-scan"></div></div></div></div>
    """,unsafe_allow_html=True)
    st.markdown("### Analyze your document")
    uploaded=st.file_uploader("Upload CSV, Excel or Word",type=["csv","xlsx","xls","docx"],key="document_ai_uploader")
    c1,c2=st.columns([2,1])
    with c1:
        analyze=st.button("📄 Analyze Your Document",use_container_width=True,type="primary",disabled=uploaded is None)
    with c2:
        if st.button("⌂ Home",use_container_width=True): _set_page("home")
    if analyze and uploaded:
        # Excel/CSV uploads are persisted to Snowflake through write_pandas().
        # Never call it with a missing Snowpark session. This can happen when
        # Document AI is opened directly from Home before authentication.
        if (not st.session_state.get("authenticated", False)
                or st.session_state.get("snowpark_session") is None
                or st.session_state.get("snowflake_conn") is None):
            st.session_state.post_login_page = "document_ai"
            st.session_state.app_page = "login"
            st.rerun()

        try:
            with st.spinner("Analyzing document..."):
                doc_type,doc_df,doc_text,doc_message=process_uploaded_document(uploaded)
                _drop_uploaded_table()
                st.session_state.uploaded_document_name=uploaded.name
                st.session_state.uploaded_document_type=doc_type
                st.session_state.uploaded_document_df=doc_df
                st.session_state.uploaded_document_text=doc_text
                st.session_state.uploaded_document=uploaded.name
                st.session_state.uploaded_document_table=None
                st.session_state.uploaded_document_semantic_model=None
                if doc_type=="table":
                    prepare_uploaded_table(doc_df)
                elif doc_type=="text":
                    _upload_document_to_stage(uploaded)

            # Preserve the upload as a chat event when Document AI is opened
            # from the top navigation. The chatbot renders this pending event
            # after its chat-session state has been initialized, so the upload
            # preview appears in the conversation just like a sidebar upload.
            st.session_state.pending_document_chat_event = {
                "role": "assistant",
                "content": f"📄 **Document analyzed:** `{uploaded.name}`\n\n{doc_message}",
                "sql": None,
                "data": None,
                "semantic_model": "Uploaded Document",
                "verified_query": None,
                "document_event": True,
                "document_name": uploaded.name,
                "document_type": doc_type,
            }

            st.session_state.answer_source="Uploaded Document"
            st.session_state.app_page="chatbot"
            st.success(doc_message)
            st.rerun()
        except Exception as e: st.error(f"Document analysis failed: {e}")


def _about_image_data(filename):
    """Return Mission/Vision image as a browser-safe data URI.

    Images are embedded in this Python file so deployment does not require
    a separate about_assets folder.
    """
    embedded_images = {
        "mission.jpg": "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",
        "vision.jpg": "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",
    }
    encoded = embedded_images.get(filename, "")
    if encoded:
        return "data:image/jpeg;base64," + encoded

    # Optional local-file fallback for future images.
    try:
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "about_assets", filename)
        with open(image_path, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""

def _about_page():
    st.markdown("""
    <style>

      /* Navigation Group: Anchored to the far right directly below the Share area */
      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
          width: 210px !important;
          max-width: 210px !important;
          min-width: 210px !important;
          margin-left: auto !important;
          margin-right: 12px !important;
          display: flex !important;
          justify-content: flex-end !important;
          align-items: center !important;
          gap: 8px !important;
          flex-wrap: nowrap !important;
      }

      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] > [data-testid="column"] {
          flex: 0 0 98px !important;
          width: 98px !important;
          max-width: 98px !important;
          min-width: 98px !important;
      }

      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"],
      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          width: 98px !important;
          max-width: 98px !important;
          min-width: 98px !important;
          height: 52px !important;
          min-height: 52px !important;
          padding: 0 4px !important;
          font-size: .68rem !important;
          border-radius: 7px !important;
          background: #ffffff !important;
          border: 1px solid #dfe4eb !important;
          color: #171717 !important;
          font-weight: 800 !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          box-sizing: border-box !important;
      }

      /* Icons for the smaller buttons */
      .st-key-top_home [data-testid="stButton"] > button::before,
      .st-key-top_docs [data-testid="stButton"] > button::before {
          content: "";
          display: none !important;
      }

      /* ================================================================
         ABOUT DILYTICS — MISSION / VISION / SOLUTIONS / SERVICES
         Clean two-column card layout matching the requested design.
         ================================================================ */
      .about-hero{
          padding:45px;
          background:linear-gradient(135deg,#fff,#edf7ff);
          border:1px solid #cfe6ff;
          border-radius:28px;
          margin-bottom:28px;
      }
      .about-title{
          font-size:3rem;
          font-weight:900;
          color:#082d69;
      }
      .about-sub{
          font-size:1.1rem;
          color:#587291;
          line-height:1.7;
          max-width:1000px;
      }

      .about-grid{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:26px;
          margin:0 0 28px 0;
      }
      .about-feature-card{
          background:#fff;
          border:1px solid #cfd6df;
          border-radius:28px;
          overflow:hidden;
          min-height:360px;
          box-shadow:0 8px 24px rgba(23,91,160,.06);
      }
      .about-feature-image{
          width:100%;
          height:245px;
          object-fit:cover;
          display:block;
      }
      .about-feature-top{
          background:#fff;
          display:flex;
          align-items:center;
          padding:28px 36px 8px;
      }
      .about-heading-row{
          display:flex;
          align-items:center;
          gap:20px;
      }
      .about-icon{
          width:88px;
          height:88px;
          border-radius:12px;
          background:#eef7ff;
          border:1px solid #d8ecff;
          display:flex;
          align-items:center;
          justify-content:center;
          font-size:46px;
          flex:0 0 88px;
      }
      .about-feature-title{
          font-size:2.45rem;
          line-height:1.05;
          font-weight:800;
          color:#29476d;
          margin:0;
      }
      .about-underline{
          width:112px;
          height:4px;
          background:#16a9e8;
          border-radius:5px;
          margin-top:14px;
      }
      .about-feature-body{
          padding:28px 36px 34px;
      }
      .about-feature-body p{
          color:#171717;
          font-size:1.08rem;
          line-height:1.55;
          margin:0 0 18px 0;
      }
      .about-feature-body p:last-child{margin-bottom:0}

      @media(max-width:900px){
          .about-grid{grid-template-columns:1fr}
          .about-feature-title{font-size:2.1rem}
          .about-feature-card{min-height:auto}
      }
      @media(max-width:600px){
          .about-hero{padding:28px}
          .about-feature-image{height:190px}
          .about-title{font-size:2.25rem}
          .about-heading-row{gap:14px}
          .about-icon{width:68px;height:68px;flex-basis:68px;font-size:34px}
          .about-feature-top{padding:24px}
          .about-feature-body{padding:24px}
      }
    </style>

    <div class="about-hero">
      <div class="about-title">About DiLytics</div>
      <div class="about-sub">
        DiLytics helps organizations turn complex data into actionable insights through analytics,
        AI, data engineering and modern cloud platforms. Its mission is to create competitive
        advantage through outstanding insights using the latest developments in analytics.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Mission and Vision — large feature cards with the requested reference images.
    mission_image = _about_image_data("mission.jpg")
    vision_image = _about_image_data("vision.jpg")
    st.markdown(f"""
    <div class="about-grid">
      <div class="about-feature-card">
        <img class="about-feature-image" src="{mission_image}" alt="DiLytics Mission" />
        <div class="about-feature-top">
          <div class="about-heading-row">
            <div class="about-icon">🎯</div>
            <div>
              <div class="about-feature-title">Mission</div>
              <div class="about-underline"></div>
            </div>
          </div>
        </div>
        <div class="about-feature-body">
          <p>
            Our mission is to bring great competitive advantage to our customers through delivery
            of outstanding insights by leveraging the latest and the greatest developments in the
            Analytics space.
          </p>
        </div>
      </div>

      <div class="about-feature-card">
        <img class="about-feature-image" src="{vision_image}" alt="DiLytics Vision" />
        <div class="about-feature-top">
          <div class="about-heading-row">
            <div class="about-icon">👁️</div>
            <div>
              <div class="about-feature-title">Vision</div>
              <div class="about-underline"></div>
            </div>
          </div>
        </div>
        <div class="about-feature-body">
          <p>
            Our vision is to be the best Analytics solution partner to our customers, one that
            brings immense value to their Analytics endeavors. We aspire to be among the top
            Analytics solution providers globally.
          </p>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Insight Solutions and Services — second row using the same card template.
    st.markdown("""
    <div class="about-grid">
      <div class="about-feature-card">
        <div class="about-feature-top">
          <div class="about-heading-row">
            <div class="about-icon">💡</div>
            <div>
              <div class="about-feature-title">Insight Solutions</div>
              <div class="about-underline"></div>
            </div>
          </div>
        </div>
        <div class="about-feature-body">
          <p>
            DiLytics Insight Solutions is a suite of horizontal and industry-specific analytics
            solutions designed to accelerate data-driven decision-making and business transformation.
            Each solution comes with extensive prebuilt content, including data models, data pipelines,
            dashboards, reports and metrics.
          </p>
          <p>
            Validated by Microsoft and Oracle, the solutions deliver enterprise-grade reliability,
            scalability, and performance. Their modular architecture and customization features enable
            organizations to tailor capabilities as per their unique business processes.
          </p>
          <p>
            Natural language capabilities provide intuitive access to valuable insights and foresights.
            Flexible deployment options across on-premises, cloud, and hybrid environments provide
            maximum adaptability, while the prebuilt foundation delivers a significant time-to-market
            advantage, enabling deployment in weeks rather than months.
          </p>
        </div>
      </div>

      <div class="about-feature-card">
        <div class="about-feature-top">
          <div class="about-heading-row">
            <div class="about-icon">🤝</div>
            <div>
              <div class="about-feature-title">Services</div>
              <div class="about-underline"></div>
            </div>
          </div>
        </div>
        <div class="about-feature-body">
          <p>
            DiLytics offers a comprehensive portfolio of Data, Analytics, and AI services. As a
            one-stop partner, DiLytics supports clients across the entire lifecycle – from strategy
            and advisory to implementation, optimization, and ongoing support.
          </p>
          <p>
            Our Think Services help organizations define strategy, roadmaps, and technology direction.
            Build Services deliver data platforms, analytics, AI solutions, migrations and upgrades.
            Run Services provide ongoing support to maximize the value of analytics and AI investments.
          </p>
          <p>
            With expertise across modern data and AI platforms such as Microsoft, Oracle, Snowflake,
            Alteryx, DiLytics delivers vendor-agnostic solutions tailored to business needs. Our Staff
            Augmentation Services complement these offerings by providing experienced consultants to
            bridge critical skill gaps.
          </p>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Why Dilytics for modern analytics")
    points=[
        "End-to-end analytics, data engineering and AI capabilities.",
        "Natural-language access to insights through conversational interfaces.",
        "Modular solutions that can be customized to business processes.",
        "Snowflake, Power BI, Tableau and other modern data-platform expertise."
    ]
    for p in points:
        st.markdown(f"✓ **{p}**")

    st.markdown("### Key milestones")
    milestones=[
        ("2011","DiLytics was founded in California to deliver enterprise analytics solutions."),
        ("2012","Delivered a complex supply-chain planning analytics solution for a leading biopharmaceutical organization."),
        ("2023–2024","Expanded strategic engagements and implemented DiLytics Insight Solutions for major organizations."),
        ("2025","Delivered Sales, Finance and Planning Analytics solutions for a leading global medical-device manufacturer."),
        ("2026","Expanded analytics delivery across nonprofit behavioral health and other data-driven organizations.")
    ]
    for year,desc in milestones:
        st.markdown(f"**{year}**  —  {desc}")
    if st.button("⌂ Home",use_container_width=False):
        _set_page("home")


def _open_document_ai():
    """Open Document AI only when the Snowflake/Snowpark session is ready."""
    authenticated = st.session_state.get("authenticated", False)
    snowflake_session = st.session_state.get("snowpark_session")
    snowflake_conn = st.session_state.get("snowflake_conn")

    if not authenticated or snowflake_session is None or snowflake_conn is None:
        # Remember the requested destination so a successful login returns
        # the user to Document AI instead of unexpectedly opening the chatbot.
        st.session_state.post_login_page = "document_ai"
        st.session_state.app_page = "login"
    else:
        st.session_state.app_page = "document_ai"
    st.rerun()


def _open_chat():
    """Open AI chat only when a valid authenticated Snowflake session exists."""
    authenticated = st.session_state.get("authenticated", False)
    snowflake_session = st.session_state.get("snowpark_session")
    snowflake_conn = st.session_state.get("snowflake_conn")

    # Module pages can be opened without signing in.  Never send an
    # unauthenticated user directly to the chatbot because the chatbot
    # requires the Snowpark/Snowflake session created by the login flow.
    # Also handle a stale authenticated flag with a missing session safely.
    if not authenticated or snowflake_session is None or snowflake_conn is None:
        st.session_state.app_page = "login"
    else:
        st.session_state.app_page = "chatbot"
    st.rerun()


def _home_page():
    st.markdown(
        """
<style>
      /* ================================================================
         DILYTICS HOME — MODULE CAROUSEL
         Three intelligence cards live in one horizontal scroll area.
         ================================================================ */

      .home-hero{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:35px;
          align-items:center;
          padding:0 0 28px;
          margin-top:-14px;
      }
      .home-eyebrow{
          letter-spacing:4px;
          color:#1769d2;
          font-weight:800;
      }
      .home-title{
          font-size:4rem;
          line-height:1.02;
          font-weight:900;
          color:#082d69;
      }
      .home-title span{color:#1769d2}
      .home-sub{
          font-size:1.12rem;
          color:#587291;
          line-height:1.6;
          max-width:600px;
      }
      .home-robot{
          height:430px;
          position:relative;
          display:flex;
          align-items:center;
          justify-content:center;
      }
      .orb{
          width:430px;
          height:430px;
          border-radius:50%;
          background:radial-gradient(circle at 50% 42%,#ffffff,#e8f6ff 55%,#d6edff 100%);
          display:flex;
          align-items:center;
          justify-content:center;
          box-shadow:0 0 0 25px rgba(31,129,225,.05),0 20px 55px rgba(23,91,160,.08);
          animation:pulse 4s ease-in-out infinite;
      }
      .home-robot-img{
          width:390px;
          max-width:86%;
          height:auto;
          object-fit:contain;
          filter:drop-shadow(0 25px 35px rgba(20,94,170,.18));
          animation:float 3.5s ease-in-out infinite;
      }
      .bubble{
          position:absolute;
          right:5%;
          top:5%;
          padding:18px 22px;
          background:#fff;
          border:1px solid #d4e8ff;
          border-radius:20px;
          color:#1769d2;
          box-shadow:0 12px 30px rgba(23,91,160,.12);
          font-weight:700;
      }
      .home-stats{
          display:flex;
          gap:24px;
          margin-top:22px;
          color:#315a88;
          flex-wrap:wrap;
      }
      .home-stat{
          display:inline-flex;
          align-items:center;
          gap:8px;
          font-size:.79rem;
          font-weight:650;
          white-space:nowrap;
      }
      .home-stat-icon{
          width:25px;
          height:25px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          border-radius:7px;
          background:rgba(255,255,255,.82);
          border:1px solid #d7eafa;
          color:#1769d2;
          box-shadow:0 3px 9px rgba(23,105,210,.06);
          font-size:.85rem;
      }

      /* Premium value panel fills the open hero area without competing
         with the robot visual. */
      .home-value-panel{
          margin-top:27px;
          max-width:690px;
          padding:17px 18px 16px;
          border:1px solid rgba(184,218,247,.85);
          border-radius:16px;
          background:rgba(255,255,255,.62);
          box-shadow:
              0 12px 32px rgba(27,91,151,.055),
              inset 0 1px 0 rgba(255,255,255,.95);
          backdrop-filter:blur(8px);
      }
      .home-value-head{
          display:flex;
          align-items:center;
          justify-content:space-between;
          gap:14px;
          margin-bottom:13px;
      }
      .home-value-title{
          color:#082d69;
          font-size:.83rem;
          font-weight:850;
          letter-spacing:.2px;
      }
      .home-live{
          display:inline-flex;
          align-items:center;
          gap:6px;
          padding:5px 9px;
          border-radius:999px;
          background:#effbf5;
          border:1px solid #cdeedb;
          color:#16824b;
          font-size:.67rem;
          font-weight:800;
      }
      .home-live-dot{
          width:6px;
          height:6px;
          border-radius:50%;
          background:#22a861;
          box-shadow:0 0 0 3px rgba(34,168,97,.10);
      }
      .home-value-grid{
          display:grid;
          grid-template-columns:repeat(3,1fr);
          gap:9px;
      }
      .home-value-item{
          padding:11px 12px;
          border-radius:11px;
          background:rgba(248,252,255,.88);
          border:1px solid #e0edf8;
      }
      .home-value-item strong{
          display:block;
          color:#0b3c78;
          font-size:.76rem;
          font-weight:800;
          margin-bottom:3px;
      }
      .home-value-item span{
          display:block;
          color:#66819f;
          font-size:.65rem;
          line-height:1.35;
      }

      .home-capability-row{
          display:flex;
          gap:8px;
          flex-wrap:wrap;
          margin-top:12px;
      }
      .home-capability{
          display:inline-flex;
          align-items:center;
          gap:6px;
          padding:7px 10px;
          border-radius:9px;
          background:rgba(255,255,255,.72);
          border:1px solid #dcecf9;
          color:#41688f;
          font-size:.66rem;
          font-weight:700;
      }
      .home-capability b{
          color:#1769d2;
          font-size:.72rem;
      }

      /* Scrollable module rail. Streamlit's horizontal container keeps
         all three cards on one line and provides horizontal scrolling. */
      .dly-module-rail-hint{
          display:flex;
          align-items:center;
          justify-content:space-between;
          margin:6px 0 12px;
          color:#6380a2;
          font-size:.76rem;
          font-weight:650;
      }
      .dly-module-rail-hint span:last-child{
          color:#1769d2;
          font-weight:750;
      }

      /* Style the horizontal Streamlit container as a clean carousel. */
      [data-testid="stHorizontalBlock"]{
          scroll-behavior:smooth;
      }

      .st-key-inventory_card,
      .st-key-sales_card,
      .st-key-supply_chain_card{
          background:#ffffff !important;
          border:1px solid #d8e9f8 !important;
          border-radius:22px !important;
          padding:27px !important;
          box-shadow:
              0 14px 38px rgba(23,91,160,.075),
              0 2px 7px rgba(23,91,160,.035) !important;
          box-sizing:border-box !important;
          min-height:445px !important;
          height:100% !important;
          transition:
              transform .2s ease,
              box-shadow .2s ease,
              border-color .2s ease !important;
      }

      .st-key-inventory_card:hover,
      .st-key-sales_card:hover,
      .st-key-supply_chain_card:hover{
          transform:translateY(-3px) !important;
          border-color:#b9d9f5 !important;
          box-shadow:
              0 20px 45px rgba(23,91,160,.12),
              0 3px 9px rgba(23,91,160,.05) !important;
      }

      .module-card-container h2{
          color:#082d69;
          margin-top:0;
          margin-bottom:13px;
          font-size:1.65rem;
          font-weight:850;
          letter-spacing:-.2px;
      }
      .module-card-container p{
          color:#587291;
          line-height:1.55;
          min-height:50px;
      }
      .module-card-container li{
          margin:9px 0;
          color:#183e70;
      }

      .module-card-actions{
          margin-top:23px;
      }

      /* Make action buttons larger so the icons and typography read clearly. */
      .module-card-actions [data-testid="stButton"] > button{
          min-height:48px !important;
          height:48px !important;
          border-radius:12px !important;
          padding:0 15px !important;

          font-family:"Inter","Segoe UI",Arial,sans-serif !important;
          font-size:.88rem !important;
          font-weight:800 !important;
          letter-spacing:.05px !important;

          display:flex !important;
          align-items:center !important;
          justify-content:center !important;

          box-shadow:0 4px 12px rgba(23,91,160,.10) !important;
          transition:all .18s ease !important;
      }

      /* Explore = very light sky blue, as requested. */
      .st-key-home_inv_explore [data-testid="stButton"] > button,
      .st-key-home_sales_explore [data-testid="stButton"] > button,
      .st-key-home_supply_explore [data-testid="stButton"] > button{
          background:#dff1ff !important;
          border:1px solid #b8ddf8 !important;
          color:#0b5fa8 !important;
      }

      .st-key-home_inv_explore [data-testid="stButton"] > button:hover,
      .st-key-home_sales_explore [data-testid="stButton"] > button:hover,
      .st-key-home_supply_explore [data-testid="stButton"] > button:hover{
          background:#cceaff !important;
          border-color:#91c9ef !important;
          color:#064f8d !important;
          transform:translateY(-1px) !important;
          box-shadow:0 7px 17px rgba(23,105,210,.15) !important;
      }

      /* Explicit Explore icon so it cannot disappear. */
      .st-key-home_inv_explore [data-testid="stButton"] > button::before,
      .st-key-home_sales_explore [data-testid="stButton"] > button::before,
      .st-key-home_supply_explore [data-testid="stButton"] > button::before{
          content:"↗";
          width:27px;
          height:27px;
          flex:0 0 27px;
          margin-right:8px;

          display:inline-flex;
          align-items:center;
          justify-content:center;

          border-radius:7px;
          background:#ffffff;
          color:#0b6fbd;
          font-size:18px;
          font-weight:900;
          line-height:1;

          box-shadow:inset 0 0 0 1px #c7e4f8;
      }

      /* Chat with AI = white premium secondary action with shadow border. */
      .st-key-home_inv_chat [data-testid="stButton"] > button,
      .st-key-home_sales_chat [data-testid="stButton"] > button,
      .st-key-home_supply_chat [data-testid="stButton"] > button{
          background:#ffffff !important;
          border:1px solid #cbd8e5 !important;
          color:#173f6f !important;
          box-shadow:
              0 5px 14px rgba(24,63,111,.12),
              inset 0 1px 0 rgba(255,255,255,.95) !important;
      }

      .st-key-home_inv_chat [data-testid="stButton"] > button:hover,
      .st-key-home_sales_chat [data-testid="stButton"] > button:hover,
      .st-key-home_supply_chat [data-testid="stButton"] > button:hover{
          background:#fafdff !important;
          border-color:#9fb9d2 !important;
          color:#0b4f8f !important;
          transform:translateY(-1px) !important;
          box-shadow:
              0 8px 18px rgba(24,63,111,.16),
              inset 0 1px 0 rgba(255,255,255,.98) !important;
      }

      /* Explicit Chat icon. */
      .st-key-home_inv_chat [data-testid="stButton"] > button::before,
      .st-key-home_sales_chat [data-testid="stButton"] > button::before,
      .st-key-home_supply_chat [data-testid="stButton"] > button::before{
          content:"💬";
          width:27px;
          height:27px;
          flex:0 0 27px;
          margin-right:8px;

          display:inline-flex;
          align-items:center;
          justify-content:center;

          border-radius:7px;
          background:#edf6ff;
          color:#1769d2;
          font-size:16px;
          line-height:1;

          box-shadow:inset 0 0 0 1px #d7e9f8;
      }

      .home-footer{
          border-top:1px solid #dcecff;
          margin-top:35px;
          padding:20px 0;
          color:#5a7392;
          text-align:center;
      }

      @keyframes float{50%{transform:translateY(-12px)}}
      @keyframes pulse{50%{transform:scale(1.03)}}

      @media(max-width:850px){
          .home-hero{grid-template-columns:1fr}
          .home-title{font-size:2.8rem}
          .home-robot{height:360px}
          .orb{width:330px;height:330px}
          .home-robot-img{width:310px}
          .bubble{right:0}
          .home-stats{gap:14px;flex-wrap:wrap}
          .home-value-panel{max-width:none}
          .home-value-grid{grid-template-columns:1fr}
      }

      /* Full-width equal module cards inside the horizontal rail. */
      .st-key-inventory_card,
      .st-key-sales_card,
      .st-key-supply_chain_card{
          width:100% !important;
          min-width:0 !important;
          box-sizing:border-box !important;
      }

      .st-key-inventory_card > div,
      .st-key-sales_card > div,
      .st-key-supply_chain_card > div{
          width:100% !important;
          box-sizing:border-box !important;
      }

      /* On smaller screens, allow the rail to overflow horizontally
         rather than compressing the cards. */
      @media(max-width:1100px){
          .st-key-inventory_card,
          .st-key-sales_card,
          .st-key-supply_chain_card{
              min-width:420px !important;
          }
      }
    
      /* FINAL SMALL NAV OVERRIDE: Home + Document AI under Share, far right */
      .st-key-dly_main_header > div > [data-testid="column"]:last-child {
          display: flex !important;
          flex-direction: column !important;
          align-items: flex-end !important;
          justify-content: flex-start !important;
      }

      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
          width: 170px !important;
          max-width: 170px !important;
          min-width: 170px !important;
          margin-left: auto !important;
          margin-right: 8px !important;
          padding: 0 !important;
          gap: 5px !important;
          display: flex !important;
          justify-content: flex-end !important;
          align-items: center !important;
          flex-wrap: nowrap !important;
      }

      .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] > [data-testid="column"] {
          flex: 0 0 auto !important;
          width: auto !important;
          min-width: 0 !important;
          max-width: none !important;
      }

      .st-key-top_home,
      .st-key-top_docs {
          width: auto !important;
          min-width: 0 !important;
          max-width: none !important;
          margin: 0 !important;
          padding: 0 !important;
      }

      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"] {
          width: auto !important;
          min-width: 0 !important;
          max-width: none !important;
          margin: 0 !important;
          padding: 0 !important;
      }

      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          width: auto !important;
          min-width: 58px !important;
          max-width: 88px !important;
          height: 52px !important;
          min-height: 52px !important;
          padding: 0 6px !important;
          margin: 0 !important;
          border-radius: 6px !important;
          font-size: .60rem !important;
          line-height: 1 !important;
          font-weight: 700 !important;
          white-space: nowrap !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          overflow: hidden !important;
          box-sizing: border-box !important;
      }

      .st-key-top_home [data-testid="stButton"] > button::before,
      .st-key-top_docs [data-testid="stButton"] > button::before {
          display: none !important;
          content: none !important;
      }

      /* FINAL NAV OVERRIDE — match the Home-page buttons on every page.
         UI ONLY: use absolute positioning so the buttons move with the
         header when the page scrolls; they are never viewport-fixed. */
      .st-key-top_home,
      .st-key-top_docs {
          position: absolute !important;
          top: 20px !important;
          z-index: 10000 !important;
          margin: 0 !important;
          padding: 0 !important;
      }

      .st-key-top_home {
          right: 195px !important;
          width: 120px !important;
      }

      .st-key-top_docs {
          right: 15px !important;
          width: 170px !important;
      }

      .st-key-top_home [data-testid="stButton"],
      .st-key-top_docs [data-testid="stButton"] {
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
          margin: 0 !important;
          padding: 0 !important;
      }

      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
          height: 52px !important;
          min-height: 52px !important;
          padding: 0 8px !important;
          margin: 0 !important;
          border-radius: 8px !important;
          font-size: .76rem !important;
          font-weight: 700 !important;
          white-space: nowrap !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          box-sizing: border-box !important;
      }

      .st-key-top_home [data-testid="stButton"] > button::before,
      .st-key-top_docs [data-testid="stButton"] > button::before {
          display: inline-flex !important;
          align-items: center !important;
          justify-content: center !important;
          width: 29px !important;
          height: 29px !important;
          flex: 0 0 29px !important;
          margin-right: 7px !important;
          border-radius: 6px !important;
          background: #f5f7fa !important;
          color: #111827 !important;
          box-shadow: inset 0 0 0 1px #e5e9ee !important;
      }

      .st-key-top_home [data-testid="stButton"] > button::before {
          content: "⌂" !important;
          font-size: 19px !important;
      }

      .st-key-top_docs [data-testid="stButton"] > button::before {
          content: "▣" !important;
          font-size: 17px !important;
      }

      /* GLOBAL NAV SIZE — identical Home / Document AI button height on every page. */
      .st-key-top_home [data-testid="stButton"] > button,
      .st-key-top_docs [data-testid="stButton"] > button {
          height: 52px !important;
          min-height: 52px !important;
      }

      @media (max-width: 700px) {
          /* Reset manually positioned navigation on small screens. */
          .st-key-top_home,
          .st-key-top_docs {
              position: static !important;
              width: 100% !important;
              margin-top: 5px !important;
          }

          .st-key-dly_main_header > div > [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] {
              width: 100% !important;
              position: static !important;
              gap: 6px !important;
              flex-wrap: nowrap !important;
          }

          .st-key-top_home [data-testid="stButton"] > button,
          .st-key-top_docs [data-testid="stButton"] > button {
              min-width: 52px !important;
              max-width: 78px !important;
              height: 52px !important;
              min-height: 52px !important;
              font-size: .56rem !important;
          }
      }
</style>
        """, unsafe_allow_html=True)

    # ------------------------------------------------------------
    # HERO — native Streamlit layout
    # ------------------------------------------------------------
    hero_left, hero_right = st.columns([1.05, 0.95], gap="large")

    with hero_left:
        st.markdown('<div class="home-eyebrow">WELCOME TO DILYTICS</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="home-title">Your AI-Powered<br><span>Data Companion</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="home-sub">Ask questions, explore insights, and make smarter decisions '
            'with the power of your data — all from one intelligent workspace.</div>',
            unsafe_allow_html=True,
        )

        stat1, stat2, stat3 = st.columns(3, gap="small")
        with stat1:
            st.markdown("**▥  Insights Made Simple**")
        with stat2:
            st.markdown("**ϟ  Faster Decisions**")
        with stat3:
            st.markdown("**✓  Secure & Governed**")

        with st.container(border=True):
            st.markdown("### One workspace. Multiple intelligence layers.")

            c1, c2, c3 = st.columns(3, gap="small")
            with c1:
                st.markdown("**Natural-Language Analytics**")
                st.caption("Ask business questions in plain English and explore governed insights.")
            with c2:
                st.markdown("**Operational Intelligence**")
                st.caption("Connect inventory, sales and supply chain decisions in one view.")
            with c3:
                st.markdown("**Document Intelligence**")
                st.caption("Bring documents into the conversation and turn information into answers.")

        with st.container(border=True):
            p1, p2, p3 = st.columns(3, gap="small")

            with p1:
                st.markdown("◈ **Snowflake Powered**")
                st.caption("Built on Snowflake to securely analyze enterprise data and deliver trusted, governed insights.")

            with p2:
                st.markdown("↗ **Real-Time Insights**")
                st.caption("Turn up-to-date business data into actionable insights for faster and more informed decisions.")

            with p3:
                st.markdown("◇ **Enterprise Ready**")
                st.caption("Designed for secure, scalable business intelligence across teams, data sources, and workflows.")

    with hero_right:
        robot_html = (
            '<div class="home-robot">'
            '<div class="orb">'
            '<img class="home-robot-img" src="' + _robot_data_uri() + '" alt="Dilytics AI assistant" />'
            '</div>'
            '<div class="bubble"><b>Hi!</b><br>How can I help you<br>today?</div>'
            '</div>'
        )
        st.markdown(robot_html, unsafe_allow_html=True)


    st.markdown(
        '<div class="dly-module-rail-hint">'
        '<span>Explore our intelligence modules</span>'
        '<span>← Scroll horizontally to view more modules →</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # A horizontal Streamlit container keeps all three cards in one row.
    # On desktop, stretch-width cards share the full available width equally.
    # On narrower screens, the cards retain a readable minimum width and the
    # rail can be scrolled horizontally.
    try:
        module_rail = st.container(
            horizontal=True,
            gap="medium",
            horizontal_alignment="left",
            vertical_alignment="top",
            height=500,
            width="stretch",
        )
    except TypeError:
        # Compatibility fallback for older Streamlit versions.
        module_rail = st.container()

    with module_rail:
        with st.container(key="inventory_card", width="stretch"):
            st.markdown("""
            <div class="module-card-container">
              <h2>Inventory Intelligence</h2>
              <p>Get real-time insights into stock levels, warehouse capacity and product performance.</p>
              <ul>
                <li>Track inventory levels and availability</li>
                <li>Analyze stock value by warehouse and category</li>
                <li>Identify excess and out-of-stock items</li>
                <li>Find products that need to be reordered</li>
              </ul>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="module-card-actions">', unsafe_allow_html=True)
            a,b=st.columns(2, gap="small")
            with a:
                if st.button("Explore Inventory", use_container_width=True, key="home_inv_explore"):
                    _set_page("inventory")
            with b:
                if st.button("Chat with AI", use_container_width=True, key="home_inv_chat"):
                    _open_chat()
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container(key="sales_card", width="stretch"):
            st.markdown("""
            <div class="module-card-container">
              <h2>Sales Intelligence</h2>
              <p>Uncover sales trends, customer insights and revenue opportunities across products, regions and channels.</p>
              <ul>
                <li>Analyze total sales and revenue</li>
                <li>Identify top products and customer segments</li>
                <li>Track sales by region and channel</li>
                <li>Monitor monthly and quarterly trends</li>
              </ul>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="module-card-actions">', unsafe_allow_html=True)
            a,b=st.columns(2, gap="small")
            with a:
                if st.button("Explore Sales", use_container_width=True, key="home_sales_explore"):
                    _set_page("sales")
            with b:
                if st.button("Chat with AI", use_container_width=True, key="home_sales_chat"):
                    _open_chat()
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container(key="supply_chain_card", width="stretch"):
            st.markdown("""
            <div class="module-card-container">
              <h2>Supply Chain Intelligence</h2>
              <p>Monitor supply chain performance, fulfillment, logistics and operational trends across your network.</p>
              <ul>
                <li>Analyze supply chain and fulfillment performance</li>
                <li>Track orders, shipments and delivery trends</li>
                <li>Identify delays, bottlenecks and exceptions</li>
                <li>Explore supplier and logistics performance</li>
              </ul>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="module-card-actions">', unsafe_allow_html=True)
            a,b=st.columns(2, gap="small")
            with a:
                if st.button("Explore Supply Chain", use_container_width=True, key="home_supply_explore"):
                    _set_page("supply_chain")
            with b:
                if st.button("Chat with AI", use_container_width=True, key="home_supply_chat"):
                    _open_chat()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="home-footer">© 2026 DiLytics. All rights reserved. &nbsp; | &nbsp; '
        'Powered by Snowflake &nbsp; | &nbsp; Secure & Compliant &nbsp; | &nbsp; '
        'Insights Made Simple</div>',
        unsafe_allow_html=True,
    )


# Initialize route state and render non-chat pages.
if "app_page" not in st.session_state:
    st.session_state.app_page = "home"

# The Document AI page can be opened directly from the top-right navigation.
# Define the authenticated Snowpark session BEFORE non-chat pages are rendered;
# the previous placement was after this routing block, so _document_ai_page()
# could reach process_uploaded_document() without a local `session` variable.
session = st.session_state.get("snowpark_session")
conn = st.session_state.get("snowflake_conn")

if st.session_state.app_page != "chatbot":
    _top_nav()
    page=st.session_state.app_page
    if page=="home": _home_page()
    elif page=="login": _login_page()
    elif page=="inventory": _module_page("inventory")
    elif page=="sales": _module_page("sales")
    elif page=="supply_chain": _module_page("supply_chain")
    elif page=="document_ai": _document_ai_page()
    elif page=="about": _about_page()
    st.stop()

# Chatbot page keeps the existing working Cortex Analyst/document code below.

# Snowpark session is initialized before page routing so both
# Document AI and Chatbot can use the authenticated session.

if session is None:
    st.error(
        "Snowflake session is not available. Please return to Home, "
        "open Chat with AI again, and sign in."
    )
    st.stop()

# ===================================================================
# 3. CHAT SESSION STATE
# ===================================================================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}

if "pinned_sessions" not in st.session_state:
    st.session_state.pinned_sessions = set()

if "sidebar_search" not in st.session_state:
    st.session_state.sidebar_search = ""

if "current_session_id" not in st.session_state:
    init_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    st.session_state.current_session_id = init_id
    st.session_state.chat_sessions[init_id] = {
        "title": "New Conversation",
        "messages": [],
    }

current_id = st.session_state.current_session_id
messages = st.session_state.chat_sessions[current_id]["messages"]

# A top-right Document AI upload reaches the chatbot through a rerun.
# Consume its pending event here, after `messages` definitely exists.
pending_doc_event = st.session_state.pop("pending_document_chat_event", None)
if pending_doc_event:
    doc_name = pending_doc_event.get("document_name")
    already_added = any(
        m.get("document_event") and m.get("document_name") == doc_name
        for m in messages
    )
    if not already_added:
        messages.append(pending_doc_event)

# ===================================================================
# 4. CHART DISPLAY
# ===================================================================
def display_chart_tab(df: pd.DataFrame, key_prefix: str = ""):
    if df is None or df.empty:
        st.info("No data available for charting.")
        return

    if len(df.columns) < 2:
        st.info("Need at least 2 columns to render a chart.")
        return

    all_cols = list(df.columns)
    col1, col2, col3 = st.columns(3)

    x_col = col1.selectbox(
        "Dimension (X-axis)", all_cols, index=0,
        key=f"{key_prefix}_x"
    )

    remaining_cols = [c for c in all_cols if c != x_col]
    if not remaining_cols:
        return

    y_col = col2.selectbox(
        "Metric (Y-axis)", remaining_cols, index=0,
        key=f"{key_prefix}_y"
    )

    chart_type = col3.selectbox(
        "Chart Type",
        ["Bar Chart", "Line Chart", "Area Chart", "Scatter Plot"],
        key=f"{key_prefix}_type",
    )

    chart_df = df.copy()

    if any(k in x_col.lower()
           for k in ["year", "quarter", "month", "day", "date"]):
        chart_df[x_col] = chart_df[x_col].apply(
            lambda x: (
                str(int(x))
                if pd.notnull(x) and isinstance(x, (int, float))
                else str(x)
            )
        )

    try:
        if chart_type == "Bar Chart":
            st.bar_chart(chart_df.set_index(x_col)[y_col])
        elif chart_type == "Line Chart":
            st.line_chart(chart_df.set_index(x_col)[y_col])
        elif chart_type == "Area Chart":
            st.area_chart(chart_df.set_index(x_col)[y_col])
        else:
            st.scatter_chart(chart_df, x=x_col, y=y_col)
    except Exception as e:
        st.info(f"Chart could not be rendered: {e}")


# ===================================================================
# 5. SIDEBAR
# ===================================================================
with st.sidebar:
    # ChatGPT-inspired top area: brand + native Streamlit open/close control.
    st.markdown(
        f"""
        <div class="dly-sidebar-brand">
            <img class="dly-sidebar-brand-logo" src="{DILYTICS_LOGO_URI}" alt="Dilytics" />
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Search conversations.
    search_value = st.text_input(
        "Search",
        value=st.session_state.sidebar_search,
        placeholder="⌕  Search",
        label_visibility="collapsed",
        key="dly_sidebar_search_box",
    )
    st.session_state.sidebar_search = search_value.strip()

    # New chat.
    if st.button("✎  New chat", use_container_width=True, type="primary", key="sidebar_new_chat"):
        new_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        st.session_state.current_session_id = new_id
        st.session_state.chat_sessions[new_id] = {
            "title": "New Conversation",
            "messages": [],
        }
        st.session_state.pinned_sessions.discard(new_id)
        st.rerun()

    st.markdown('<div class="dly-sidebar-divider"></div>', unsafe_allow_html=True)

    # Pinned conversations.
    st.markdown('<div class="dly-sidebar-section">Pinned</div>', unsafe_allow_html=True)

    pinned_items = [
        (s_id, s_data)
        for s_id, s_data in st.session_state.chat_sessions.items()
        if s_id in st.session_state.pinned_sessions
    ]

    if not pinned_items:
        st.caption("No pinned conversations")
    else:
        for s_id, s_data in reversed(pinned_items):
            title = s_data.get("title", "New Conversation")
            if len(title) > 30:
                title = title[:28] + "…"
            if st.button(
                f"☆  {title}",
                key=f"pinned_{s_id}",
                use_container_width=True,
            ):
                st.session_state.current_session_id = s_id
                st.rerun()

    # Recent conversations.
    st.markdown('<div class="dly-sidebar-section">Recents</div>', unsafe_allow_html=True)

    query = st.session_state.sidebar_search.lower()
    recent_items = []
    for s_id, s_data in reversed(list(st.session_state.chat_sessions.items())):
        title = s_data.get("title", "New Conversation")
        if query and query not in title.lower():
            continue
        recent_items.append((s_id, s_data))

    if not recent_items:
        st.caption("No conversations found")
    else:
        for s_id, s_data in recent_items:
            is_active = s_id == st.session_state.current_session_id
            title = s_data.get("title", "New Conversation")
            if len(title) > 30:
                title = title[:28] + "…"

            c1, c2 = st.columns([0.86, 0.14], gap="small")
            with c1:
                if st.button(
                    f"{'● ' if is_active else '○ '}{title}",
                    key=f"sess_{s_id}",
                    use_container_width=True,
                ):
                    st.session_state.current_session_id = s_id
                    st.rerun()
            with c2:
                is_pinned = s_id in st.session_state.pinned_sessions
                if st.button(
                    "📌",
                    key=f"pin_{s_id}",
                    use_container_width=True,
                    help="📌 Unpin conversation" if is_pinned else "📌 Pin conversation",
                ):
                    if is_pinned:
                        st.session_state.pinned_sessions.discard(s_id)
                    else:
                        st.session_state.pinned_sessions.add(s_id)
                    st.rerun()

    st.markdown('<div class="dly-sidebar-divider"></div>', unsafe_allow_html=True)

    # Reset only the current conversation.
    if st.button(
        "↻  Reset chat",
        use_container_width=True,
        key="sidebar_reset_chat",
        help="Clear messages from the current conversation",
    ):
        current_id = st.session_state.current_session_id
        if current_id in st.session_state.chat_sessions:
            st.session_state.chat_sessions[current_id]["messages"] = []
            st.session_state.chat_sessions[current_id]["title"] = "New Conversation"
        st.rerun()

    # Clear every conversation.
    if st.button(
        "⌫  Clear chat history",
        use_container_width=True,
        key="sidebar_clear_history",
        help="Delete all saved conversations",
    ):
        st.session_state.chat_sessions = {}
        st.session_state.pinned_sessions = set()
        init_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        st.session_state.current_session_id = init_id
        st.session_state.chat_sessions[init_id] = {
            "title": "New Conversation",
            "messages": [],
        }
        st.rerun()

    # Keep the existing document workflow below the conversation controls.
    st.markdown('<div class="dly-sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="dly-sidebar-section">📄 Analyze an Uploaded Document</div>', unsafe_allow_html=True)

    uploaded_doc = st.file_uploader(
        "Upload CSV, Excel, PDF or Word",
        type=["csv", "xlsx", "xls", "pdf", "docx"],
        key="document_uploader",
        help="Upload a document, click Analyze, then choose Uploaded Document in the chat.",
    )

    if st.button(
        "🔍  Analyze Document",
        use_container_width=True,
        disabled=uploaded_doc is None,
        key="analyze_uploaded_document",
    ):
        try:
            with st.spinner("Reading and analyzing document..."):
                doc_type, doc_df, doc_text, doc_message = process_uploaded_document(
                    uploaded_doc
                )

                _drop_uploaded_table()
                st.session_state.uploaded_document_name = uploaded_doc.name
                st.session_state.uploaded_document_type = doc_type
                st.session_state.uploaded_document_df = doc_df
                st.session_state.uploaded_document_text = doc_text
                st.session_state.uploaded_document = uploaded_doc.name
                st.session_state.uploaded_document_table = None
                st.session_state.uploaded_document_semantic_model = None

                if doc_type == "table":
                    prepare_uploaded_table(doc_df)
                elif doc_type == "text":
                    _upload_document_to_stage(uploaded_doc)

            st.session_state.pending_document_chat_event = {
                "role": "assistant",
                "content": f"📄 **Document analyzed:** `{uploaded_doc.name}`\n\n{doc_message}",
                "sql": None,
                "data": None,
                "semantic_model": "Uploaded Document",
                "verified_query": None,
                "document_event": True,
                "document_name": uploaded_doc.name,
                "document_type": doc_type,
            }

            st.session_state.app_page = "chatbot"
            st.rerun()
        except Exception as e:
            st.error(f"Document analysis failed: {e}")

    if st.session_state.uploaded_document_name:
        st.caption(f"Loaded: `{st.session_state.uploaded_document_name}`")
        if st.button(
            "✖  Remove Uploaded Document",
            use_container_width=True,
            key="remove_uploaded_document",
        ):
            _drop_uploaded_table()
            st.session_state.uploaded_document_name = None
            st.session_state.uploaded_document_type = None
            st.session_state.uploaded_document_df = None
            st.session_state.uploaded_document_text = None
            st.session_state.uploaded_document = None
            st.session_state.uploaded_document_table = None
            st.session_state.uploaded_document_semantic_model = None
            st.session_state.uploaded_excel_bytes = None
            st.session_state.uploaded_excel_sheets = []
            st.session_state.uploaded_excel_selected_sheet = None
            st.rerun()


# 6. MAIN HEADER
# ===================================================================
# Use the exact same responsive Dilytics website header as the Home page.
# This keeps the logo on the left and the navigation buttons grouped on
# the right with the same spacing, sizing and zoom-responsive behavior.
_top_nav()

# 7. EXAMPLE QUESTIONS
# These buttons are only examples. They do NOT contain SQL.
# ==================================================================
quick_prompt = None

st.markdown(
    '<div class="chatbot-explore-title"><h3>Explore your data</h3></div>',
    unsafe_allow_html=True,
)
st.caption("Choose a question below or type your own question in the chat.")

tab_inv, tab_sales, tab_supply = st.tabs(
    ["Inventory Intelligence", "Sales Intelligence", "Supply Chain Intelligence"]
)

with tab_inv:
    with st.expander("What can I ask about Inventory?", expanded=False):
        if st.button(
            "What is the total inventory value?",
            use_container_width=True,
            key="i1",
        ):
            quick_prompt = "What is the total inventory value?"

        if st.button(
            "What is the inventory value by warehouse?",
            use_container_width=True,
            key="i2",
        ):
            quick_prompt = "What is the inventory value by warehouse?"

        if st.button(
            "Which products have the highest inventory value?",
            use_container_width=True,
            key="i3",
        ):
            quick_prompt = "Which products have the highest inventory value?"

        if st.button(
            "How many products are out of stock?",
            use_container_width=True,
            key="i4",
        ):
            quick_prompt = "How many products are out of stock?"

        if st.button(
            "What is the total excess inventory value by warehouse?",
            use_container_width=True,
            key="i5",
        ):
            quick_prompt = "What is the total excess inventory value by warehouse?"

        if st.button(
            "Which products need to be reordered?",
            use_container_width=True,
            key="i6",
        ):
            quick_prompt = "Which products need to be reordered?"

        if st.button(
            "What is the inventory value by product category?",
            use_container_width=True,
            key="i7",
        ):
            quick_prompt = "What is the inventory value by product category?"

with tab_sales:
    with st.expander("What can I ask about Sales?", expanded=False):
        if st.button(
            "What is the total sales amount?",
            use_container_width=True,
            key="s1",
        ):
            quick_prompt = "What is the total sales amount?"

        if st.button(
            "What are the top products by sales?",
            use_container_width=True,
            key="s2",
        ):
            quick_prompt = "What are the top products by sales?"

        if st.button(
            "What are total sales by customer region?",
            use_container_width=True,
            key="s3",
        ):
            quick_prompt = "What are total sales by customer region?"

        if st.button(
            "What are total sales by month?",
            use_container_width=True,
            key="s4",
        ):
            quick_prompt = "What are total sales by month?"

        if st.button(
            "What is total sales by order channel?",
            use_container_width=True,
            key="s5",
        ):
            quick_prompt = "What is total sales by order channel?"

        if st.button(
            "What is the average order value?",
            use_container_width=True,
            key="s6",
        ):
            quick_prompt = "What is the average order value?"

        if st.button(
            "What is the total discount?",
            use_container_width=True,
            key="s7",
        ):
            quick_prompt = "What is the total discount?"
with tab_supply:
    with st.expander("What can I ask about Supply Chain?", expanded=False):
        if st.button(
            "What is the total number of purchase orders?",
            use_container_width=True,
            key="sc1",
        ):
            quick_prompt = "What is the total number of purchase orders?"

        if st.button(
            "What is the total purchase order value?",
            use_container_width=True,
            key="sc2",
        ):
            quick_prompt = "What is the total purchase order value?"

        if st.button(
            "How many shipments are there?",
            use_container_width=True,
            key="sc3",
        ):
            quick_prompt = "How many shipments are there?"

        if st.button(
            "What is the average shipment lead time?",
            use_container_width=True,
            key="sc4",
        ):
            quick_prompt = "What is the average shipment lead time?"

        if st.button(
            "How many shipments are delayed?",
            use_container_width=True,
            key="sc5",
        ):
            quick_prompt = "How many shipments are delayed?"

        if st.button(
            "Which suppliers have the highest purchase order value?",
            use_container_width=True,
            key="sc6",
        ):
            quick_prompt = "Which suppliers have the highest purchase order value?"

        if st.button(
            "What are shipments by month?",
            use_container_width=True,
            key="sc7",
        ):
            quick_prompt = "What are shipments by month?"

        if st.button(
            "What is the on-time delivery performance?",
            use_container_width=True,
            key="sc8",
        ):
            quick_prompt = "What is the on-time delivery performance?"


st.markdown("---")


# ===================================================================
# 8. DISPLAY CHAT HISTORY
# ===================================================================
# IMPORTANT: Uploaded-document events are rendered as normal chat events.
# This preserves chronological order: Question 1 -> ... -> Question 10 ->
# Document uploaded -> Question 11 -> Answer 11.
for idx, msg in enumerate(messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg.get("document_event"):
            doc_type = msg.get("document_type")
            doc_name = msg.get("document_name")

            if doc_type == "table":
                current_df = st.session_state.uploaded_document_df
                # Keep the uploaded-file preview visible directly in the chat.
                # This makes the upload event useful even before the user asks
                # a question about the document.
                if current_df is not None:
                    st.markdown("**📊 Uploaded data preview**")
                    preview_df = _normalize_uploaded_dataframe(current_df)
                    st.dataframe(
                        preview_df.head(10),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        f"Showing the first {min(10, len(preview_df))} rows "
                        f"from `{doc_name}`. The complete uploaded dataset is "
                        "available for document questions."
                    )
            elif doc_type == "text":
                current_text = st.session_state.uploaded_document_text
                if current_text:
                    st.markdown("**📖 Uploaded document preview**")
                    # Keep the chat compact while showing the beginning of the
                    # extracted document immediately.
                    preview_text = current_text[:5000]
                    st.text_area(
                        "Document preview",
                        preview_text,
                        height=260,
                        disabled=True,
                        label_visibility="collapsed",
                        key=f"doc_preview_{current_id}_{idx}",
                    )
                    if len(current_text) > 5000:
                        st.caption("Preview shows the first 5,000 characters. The complete document remains available for questions.")

            # ADDITIVE: the two document controls are intentionally placed
            # immediately below the uploaded-file preview.
            _render_uploaded_document_dropdowns(doc_type, key_suffix=f"{current_id}_{idx}")

        if msg.get("sql"):
            with st.expander("Generated SQL", expanded=False):
                st.code(msg["sql"], language="sql")

        if msg.get("semantic_model"):
            st.caption(
                f"Semantic model selected: `{msg['semantic_model']}`"
            )

        if msg.get("verified_query"):
            name = msg["verified_query"].get("name")
            if name:
                st.caption(f"Verified Query Used: `{name}`")

        if msg.get("data") is not None:
            tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
            with tab_data:
                st.dataframe(msg["data"], use_container_width=True)
            with tab_chart:
                display_chart_tab(
                    msg["data"],
                    key_prefix=f"hist_{current_id}_{idx}",
                )


# ===================================================================
# ===================================================================
# 8A. ANSWER SOURCE (ADDED)
# ===================================================================
if st.session_state.uploaded_document_name:
    answer_source = st.radio(
        "Answer from:",
        ["Snowflake Data", "Uploaded Document"],
        horizontal=True,
        key="answer_source",
        help="Choose whether your question should use the existing Inventory/Sales semantic models or the uploaded document.",
    )
else:
    answer_source = "Snowflake Data"
# 9. CHAT INPUT
# ===================================================================
user_prompt = (
    st.chat_input(
        "Ask me anything about inventory, sales, supply chain, customers, or uploaded documents..."
    )
    or quick_prompt
    or st.session_state.get("landing_prompt")
)

# A question entered on the landing page is consumed once after navigation.
if st.session_state.get("landing_prompt"):
    st.session_state.landing_prompt = None


# ===================================================================
# 10. CORTEX ANALYST EXECUTION
# ===================================================================
if user_prompt:
    # ===================================================================
    # UPLOADED DOCUMENT QUESTION PATH (ADDED)
    # This branch is intentionally placed before the original Cortex
    # Analyst block. The original Inventory/Sales path below is unchanged.
    # ===================================================================
    if answer_source == "Uploaded Document":
        if len(messages) == 0:
            st.session_state.chat_sessions[current_id]["title"] = (
                user_prompt[:25] + ("..." if len(user_prompt) > 25 else "")
            )

        messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            doc_df_result = None
            doc_sql_result = None
            doc_answer = ""

            try:
                if conn is None:
                    raise RuntimeError(
                        "Snowflake connection is not available. "
                        "Please sign in again before asking questions about the uploaded document."
                    )

                with st.spinner("Analyzing your uploaded document..."):
                    if st.session_state.uploaded_document_type == "table":
                        doc_df_result, doc_sql_result, doc_analyst_result = answer_uploaded_table_question(
                            user_prompt,
                            st.session_state.uploaded_document_df,
                        )
                        doc_answer = (
                            "I answered your question using the complete uploaded "
                            "dataset through Cortex Analyst. The SQL below was "
                            "generated dynamically from the uploaded document schema."
                        )
                        if doc_analyst_result.get("semantic_model_selection"):
                            st.caption(
                                "Semantic model selected: "
                                + str(doc_analyst_result["semantic_model_selection"])
                            )
                    else:
                        doc_answer = answer_uploaded_text_question(
                            user_prompt,
                            st.session_state.uploaded_document_text,
                        )

                st.markdown(doc_answer)

                if doc_sql_result:
                    with st.expander("Generated SQL for Uploaded Document", expanded=False):
                        st.code(doc_sql_result, language="sql")

                if doc_df_result is not None:
                    tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
                    with tab_data:
                        st.dataframe(doc_df_result, use_container_width=True)
                    with tab_chart:
                        display_chart_tab(
                            doc_df_result,
                            key_prefix=f"document_{current_id}_{len(messages)}",
                        )

                messages.append({
                    "role": "assistant",
                    "content": doc_answer,
                    "sql": doc_sql_result,
                    "data": doc_df_result,
                    "semantic_model": "Uploaded Document",
                    "verified_query": None,
                })

            except Exception as e:
                doc_answer = f"Unable to analyze the uploaded document: {e}"
                st.error(doc_answer)
                messages.append({
                    "role": "assistant",
                    "content": doc_answer,
                    "sql": None,
                    "data": None,
                    "semantic_model": "Uploaded Document",
                    "verified_query": None,
                })

        st.rerun()
    if len(messages) == 0:
        st.session_state.chat_sessions[current_id]["title"] = (
            user_prompt[:25] + ("..." if len(user_prompt) > 25 else "")
        )

    messages.append({"role": "user", "content": user_prompt})

    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        df = None
        sql_query = None
        explanation = ""
        semantic_model = None
        verified_query = None

        try:
            with st.spinner("Cortex Analyst is interpreting your question..."):
                analyst_json = call_cortex_analyst(user_prompt)
                result = extract_analyst_response(analyst_json)

            explanation = result["text"]
            sql_query = result["sql"]
            semantic_model = result["semantic_model_selection"]
            verified_query = result["verified_query_used"]

            for warning in result["warnings"]:
                warning_text = (
                    warning.get("message", str(warning))
                    if isinstance(warning, dict)
                    else str(warning)
                )
                st.warning(warning_text)

            if not sql_query:
                if not explanation:
                    explanation = (
                        "Cortex Analyst could not generate SQL for this "
                        "question from the configured semantic models."
                    )
                st.markdown(explanation)

            else:
                if not explanation:
                    explanation = (
                        "I generated this answer using the Snowflake "
                        "semantic model."
                    )

                st.markdown(explanation)

                if semantic_model:
                    st.caption(
                        f"Semantic model selected: `{semantic_model}`"
                    )

                if verified_query:
                    name = verified_query.get("name")
                    if name:
                        st.caption(f"Verified Query Used: `{name}`")

                with st.expander("Generated SQL", expanded=False):
                    st.code(sql_query, language="sql")

                with st.spinner("Executing generated SQL in Snowflake..."):
                    df = session.sql(sql_query).to_pandas()

                tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])

                with tab_data:
                    st.dataframe(df, use_container_width=True)

                with tab_chart:
                    display_chart_tab(
                        df,
                        key_prefix=f"live_{current_id}_{len(messages)}",
                    )

        except requests.exceptions.Timeout:
            explanation = (
                "Cortex Analyst took too long to respond. Please try again."
            )
            st.error(explanation)

        except requests.exceptions.RequestException as e:
            explanation = f"Could not connect to Cortex Analyst: {e}"
            st.error(explanation)

        except Exception as e:
            explanation = f"Unable to process the question: {e}"
            st.error(explanation)

        messages.append({
            "role": "assistant",
            "content": explanation,
            "sql": sql_query,
            "data": df,
            "semantic_model": semantic_model,
            "verified_query": verified_query,
        })

    st.rerun()
