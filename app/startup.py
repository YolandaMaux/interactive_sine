#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""startup.py  –  Welcome / info tab for this app.

Drop this file unchanged into any app in the framework.
Customise the content inside render_startup_page() to match your app —
everything else (sandbox wiring, tab structure) stays the same.
"""

import streamlit as st
from loguru import logger

try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]


def render_startup_page(sb: Sandbox, app_name: str = "App", app_version: str = "1.0") -> None:
    """
    Render the Startup tab.

    Parameters
    ----------
    sb          : Sandbox bound to the current user session.
    app_name    : Human-readable name shown in the welcome header.
    app_version : Version string shown in the header.
    """
    logger.info(f"Rendering Startup page for {app_name}")

    welcome_tab, info_tab = st.tabs(["🏠 Welcome", "ℹ️ About"])

    with welcome_tab:
        st.markdown(f"## 🚀 {app_name} &nbsp; `v{app_version}`")
        st.markdown("---")

        # ── How to use ─────────────────────────────────────────────────────────
        # Edit this block to describe your specific app's workflow.
        st.subheader("Getting Started")
        st.markdown("""
1. Navigate to the **▶ Run** tab to use the application.
2. Fill in all required fields and press **Run**.
3. Results appear in the output tabs below the form.
4. Review activity and errors in the **📋 Logs** tab.
        """)

        st.markdown("---")

        # ── Session metrics ────────────────────────────────────────────────────
        st.subheader("📊 Session Status")
        runs = sb.state("_run_count") or 0

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Runs this session", runs)
        with col2:
            st.metric("Sandbox ID", sb.tenant_id)

        if runs:
            st.success(f"✅ {runs} run(s) completed this session.")
        else:
            st.info("📥 No runs yet. Head to the **▶ Run** tab to begin.")

    with info_tab:
        st.markdown(f"### {app_name}")
        # Edit these fields to describe your app.
        st.markdown("""
| Field       | Value                          |
|-------------|-------------------------------|
| Version     | see app.py `APP_VERSION`      |
| Framework   | Landing App Framework v1      |
| Log path    | set via `LOGS_PATH` in app.env |
        """)
        st.markdown("---")
        st.caption("Sandbox isolates all session state per user. "
                   "Multiple users can run this app simultaneously on the same server.")

    logger.info(f"Startup page rendered for {app_name}")
