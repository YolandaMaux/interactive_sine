#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""startup.py – Welcome / info tab for this app. (NiceGUI 3.0+ port)

Drop this file unchanged into any app in the framework.
Customise the content inside render_startup_page() to match your app —
everything else (sandbox wiring, tab structure) stays the same.
"""

from loguru import logger
from nicegui import ui

try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]


def render_startup_page(sb: Sandbox, app_name: str = "App", app_version: str = "1.0") -> None:
    """
    Render the Startup tab.

    Parameters
    ----------
    sb : Sandbox bound to the current user session.
    app_name : Human-readable name shown in the welcome header.
    app_version : Version string shown in the header.
    """
    logger.info(f"Rendering Startup page for {app_name}")

    with ui.tabs().classes("w-full") as sub_tabs:
        welcome_tab = ui.tab("🏠 Welcome")
        info_tab = ui.tab("ℹ️ About")

    with ui.tab_panels(sub_tabs, value=welcome_tab).classes("w-full"):
        with ui.tab_panel(welcome_tab):
            ui.markdown(f"## 🚀 {app_name} `v{app_version}`")
            ui.separator()

            # ── How to use ─────────────────────────────────────────────────────────
            # Edit this block to describe your specific app's workflow.
            ui.label("Getting Started").classes("text-xl font-semibold")
            ui.markdown("""
1. Navigate to the **▶ Run** tab to use the application.
2. Fill in all required fields and press **Run**.
3. Results appear in the output tabs below the form.
4. Review activity and errors in the **📋 Logs** tab.
""")

            ui.separator()

            # ── Session metrics ────────────────────────────────────────────────────
            ui.label("📊 Session Status").classes("text-xl font-semibold")
            runs = sb.state("_run_count") or 0

            with ui.row().classes("gap-6"):
                col1 = ui.column()
                col2 = ui.column()
            with col1:
                ui.label("Runs this session").classes("text-sm text-gray-500")
                ui.label(str(runs)).classes("text-3xl font-bold text-blue-600")
            with col2:
                ui.label("Sandbox ID").classes("text-sm text-gray-500")
                ui.label(str(sb.tenant_id)).classes("text-3xl font-bold text-blue-600")

            if runs:
                ui.label(f"✅ {runs} run(s) completed this session.").classes("text-green-700 font-semibold")
            else:
                ui.label("📥 No runs yet. Head to the **▶ Run** tab to begin.").classes("text-blue-700 font-semibold")

        with ui.tab_panel(info_tab):
            ui.markdown(f"### {app_name}")
            # Edit these fields to describe your app.
            ui.markdown("""
| Field | Value |
|-------------|-------------------------------|
| Version | see app.py `APP_VERSION` |
| Framework | Landing App Framework v1 |
| Log path | set via `LOGS_PATH` in app.env |
""")
            ui.separator()
            ui.label("Sandbox isolates all session state per user. "
                      "Multiple users can run this app simultaneously on the same server.").classes("text-xs text-gray-500")

    logger.info(f"Startup page rendered for {app_name}")