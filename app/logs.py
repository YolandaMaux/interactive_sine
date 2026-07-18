#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""logs.py  –  Log viewer tab.

Log file priority:
  1. sb.state("_user_log_file")  — per-user file set by app.py
  2. LOGS_PATH env var / <app>/logs/app.log  — fallback

Drop this file unchanged into any app in the framework.
It is identical across all apps — never edit it directly.
"""

import os
from pathlib import Path
from typing import Dict

import pandas as pd
import streamlit as st
from loguru import logger

try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]

_HERE        = Path(__file__).parent.resolve()
_LOCAL_LOGS  = _HERE / "logs"
_LOCAL_LOGS.mkdir(exist_ok=True)
_FALLBACK_LOG = _LOCAL_LOGS / "app.log"


def _resolve_log_file(sb: Sandbox) -> Path:
    """Return the log file path to display, in priority order."""
    user_log = sb.state("_user_log_file")
    if user_log:
        p = Path(user_log)
        if p.exists():
            return p
    logs_root = Path(os.environ.get("LOGS_PATH", str(_LOCAL_LOGS))).expanduser()
    fallback  = logs_root / "app.log"
    return fallback if fallback.exists() else _FALLBACK_LOG


def _parse_line(line: str) -> Dict[str, str]:
    try:
        ts, level, _loc, msg = line.split(" | ", 3)
        return {"time": ts.strip(), "level": level.strip(), "message": msg.strip()}
    except ValueError:
        return {"time": "", "level": "", "message": line.strip()}


@st.cache_data(ttl=2, show_spinner=False)
def _load_df(log_path: str) -> pd.DataFrame:
    """Load and parse the log file at log_path (cached 2 s)."""
    p = Path(log_path)
    if not p.exists():
        return pd.DataFrame(columns=["time", "level", "message"])
    with p.open("r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    records = [_parse_line(ln) for ln in lines if ln.strip()]
    return pd.DataFrame.from_records(records)


@st.cache_data(ttl=2, show_spinner=False)
def _filter(df: pd.DataFrame, levels: tuple, query: str, tail: int) -> pd.DataFrame:
    if df.empty:
        return df
    if len(df) > tail:
        df = df.iloc[-tail:]
    if levels:
        df = df[df["level"].isin(levels)]
    if query:
        df = df[df["message"].str.contains(query, case=False, na=False)]
    return df


def render_logs_view(sb: Sandbox) -> None:
    """Render the Logs tab."""
    logger.info("Rendering Logs page")
    st.markdown("### 📋 Logs")

    log_file = _resolve_log_file(sb)
    st.caption(f"📄 Log file: `{log_file}`")

    c1, c2, c3, c4 = st.columns((2, 1, 1, 1))

    with c1:
        search = st.text_input(
            "Search", value="", placeholder="Filter by text…",
            key=sb._ns("log_search"),
        )
    with c2:
        levels = st.multiselect(
            "Level",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=["INFO", "WARNING", "ERROR", "CRITICAL"],
            key=sb._ns("log_level_filter"),
        )
    with c3:
        tail_n = st.number_input(
            "Tail last N", min_value=50, max_value=5000, value=500, step=50,
            key=sb._ns("log_tail_n"),
        )
    with c4:
        if st.button("🔄 Refresh", key=sb._ns("refresh_logs_btn"), width="stretch"):
            st.cache_data.clear()
            st.rerun()

    df = _load_df(str(log_file))
    if df.empty:
        st.info(f"No logs yet in `{log_file}`.")
        return

    filtered = _filter(df, tuple(levels), search, tail_n)
    filtered = filtered.iloc[::-1].reset_index(drop=True)

    dl_col, tbl_col = st.columns([1, 3])
    with dl_col:
        st.download_button(
            "⬇ Download CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"{log_file.stem}.csv",
            mime="text/csv",
            key=sb._ns("dl_logs_csv"),
            width="stretch",
        )
    with tbl_col:
        st.dataframe(
            filtered,
            use_container_width=True,
            height=440,
            column_config={
                "time":    st.column_config.TextColumn("Time",    width="small"),
                "level":   st.column_config.TextColumn("Level",   width="small"),
                "message": st.column_config.TextColumn("Message", width="large"),
            },
        )

    logger.info("Logs page rendered")
