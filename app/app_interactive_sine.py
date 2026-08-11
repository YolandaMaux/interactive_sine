#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.py – Generic NiceGUI 3.0+ entry point for any single-payload app.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HOW TO ADAPT THIS FILE FOR A NEW APP
 (these are the ONLY lines you ever need to change — see “EDIT” markers)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1. _PAYLOAD_MODULE  – name of the feature module you wrote
                       (e.g. "sample_NB", "my_widget", "data_explorer")
 2. _APP_SLUG        – internal slug; also used for log filename suffix
                       and the standalone storage-secret default
 3. _APP_TITLE       – human-readable display name shown in the info bar
 4. _APP_VERSION     – semver string shown on the Startup tab
 5. _ENV_FILENAME    – name of the .env file next to app.py (or "" to skip)
 6. _STANDALONE_PORT – port for `python app.py` direct execution

Everything else is fully generic and follows the NiceGUI multi-tab
architecture template. The payload module is expected to expose:

    render_run_page(sb)               – REQUIRED. Renders the ▶ Run tab.

And MAY optionally expose any of:

    SESSION_DEFAULTS : dict           – merged into base session defaults
    DATA_KEYS        : list[str]      – keys cleared by 🗑 Clear Data
    refresh_all(sb)                   – called on Clear Data / Reset

If the payload omits the optionals, app.py falls back to safe defaults.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Standalone usage
----------------
    python app.py
    # or
    uvicorn app:app --port 8082

Embedded usage (from landing_home.py / render_app)
---------------------------------------------------
    landing_home.py calls  mod.main(username=..., tenant_id=...)
    from inside a ui.column.  main() must NOT create ui.header() or
    ui.left_drawer() — those are top-level layout elements and raise a
    RuntimeError when nested.  The standalone @ui.page('/') handler
    below provides the header for direct execution.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# ── Resolve project root & libs path ──────────────────────────────────────────
HERE = Path(__file__).parent.resolve()

# 1. Add the app's own directory so sibling modules are importable when
#    this file is loaded as a package (e.g. apps.<app_name>.app.app).
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# 2. Search parent directories for libs/sandbox.py.
_p = HERE.parent
for _ in range(5):
    if (_p / "libs" / "sandbox.py").exists():
        _lib_str = str(_p / "libs")
        if _lib_str not in sys.path:
            sys.path.insert(0, _lib_str)
        break
    _p = _p.parent

# ═════════════════════════════════════════════════════════════════════════════
# ❶ EDIT: app identity (the only block you normally need to change)
# ═════════════════════════════════════════════════════════════════════════════
_PAYLOAD_MODULE  = "interactive_sine"        # ← name of your feature module (no .py)
_APP_SLUG        = "interactive_sine"        # ← log/state namespace; lowercase, snake
_APP_TITLE       = "Interactive Sine Wave Notebook"  # ← shown in info bar + browser title
_APP_VERSION     = "1.0"              # ← shown on Startup tab
_ENV_FILENAME    = "interactive_sine.env"    # ← .env file next to app.py ("" to skip)
_STANDALONE_PORT = 8083               # ← used only by `python app.py`
# ═════════════════════════════════════════════════════════════════════════════

# ── Load .env (must happen BEFORE importing the payload, which may read env) ──
if _ENV_FILENAME:
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / _ENV_FILENAME, override=False)
    except ImportError:
        pass

# ── Core imports ──────────────────────────────────────────────────────────────
from loguru import logger
from nicegui import app as nicegui_app
from nicegui import ui

try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]

import logs
import startup_interactive_sine

# ── Dynamically import the payload module ─────────────────────────────────────
try:
    payload = importlib.import_module(_PAYLOAD_MODULE)
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        f"Payload module '{_PAYLOAD_MODULE}' not found next to app.py. "
        f"Set _PAYLOAD_MODULE at the top of app.py to your feature module's "
        f"name (without .py). Original error: {exc}"
    ) from exc

if not hasattr(payload, "render_run_page"):
    raise AttributeError(
        f"Payload module '{_PAYLOAD_MODULE}' must define "
        f"`render_run_page(sb)`. See the template contract at the top of app.py."
    )

# ── Session defaults ──────────────────────────────────────────────────────────
# Base defaults are framework-level. The payload may extend them via
# `SESSION_DEFAULTS` and may declare `DATA_KEYS` for selective Clear-Data.

_BASE_SESSION_DEFAULTS: dict = {
    "settings_saved": False,
    "log_messages":   [],
    "_run_count":     0,
}

_SESSION_DEFAULTS: dict = {
    **_BASE_SESSION_DEFAULTS,
    **getattr(payload, "SESSION_DEFAULTS", {}),
}

# Payload-declared keys cleared by 🗑 Clear Data. If the payload doesn't
# declare DATA_KEYS, fall back to "everything the payload added, plus run count".
_DATA_KEYS: list[str] = list(getattr(
    payload,
    "DATA_KEYS",
    list(getattr(payload, "SESSION_DEFAULTS", {}).keys()) + ["_run_count"],
))


def _init_session_state(sb: Sandbox) -> None:
    """Idempotent: only writes keys that are absent."""
    for key, default in _SESSION_DEFAULTS.items():
        if sb.state(key) is None:
            sb.set_state(key, default)


# ── Per-user log sink ─────────────────────────────────────────────────────────

def _ensure_user_log_sink(username: str, sb: Sandbox) -> None:
    if not hasattr(_ensure_user_log_sink, "_active_sinks"):
        _ensure_user_log_sink._active_sinks: set[str] = set()  # type: ignore[attr-defined]

    safe_user = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
    sink_key = f"{safe_user}_{sb.tenant_id}"
    if sink_key in _ensure_user_log_sink._active_sinks:  # type: ignore[attr-defined]
        return

    logs_root = Path(os.environ.get("LOGS_PATH", str(HERE / "logs"))).expanduser()
    logs_root.mkdir(parents=True, exist_ok=True)
    log_file = logs_root / f"{safe_user}_{_APP_SLUG}.log"

    logger.add(
        str(log_file),
        rotation="10 MB",
        retention="20 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
    )
    _ensure_user_log_sink._active_sinks.add(sink_key)  # type: ignore[attr-defined]
    sb.set_state("_user_log_file", str(log_file))
    logger.info(f"Log sink opened: {log_file} (user={username} tenant={sb.tenant_id})")


# ── Data management ───────────────────────────────────────────────────────────

def _payload_refresh(sb: Sandbox) -> None:
    """Call payload.refresh_all(sb) if the payload declares one."""
    fn = getattr(payload, "refresh_all", None)
    if callable(fn):
        try:
            fn(sb)
        except Exception as exc:
            logger.warning(f"payload.refresh_all raised: {exc}")


def _clear_data(sb: Sandbox) -> None:
    """Clear payload form/data only; keep session preferences intact."""
    for key in _DATA_KEYS:
        sb.set_state(key, _SESSION_DEFAULTS.get(key))
    _payload_refresh(sb)
    ui.notify("Data cleared.", type="warning")
    logger.info(f"_clear_data user={sb.username} keys={_DATA_KEYS}")


def _reset_everything(sb: Sandbox) -> None:
    """Full reset: re-apply every default."""
    for key, default in _SESSION_DEFAULTS.items():
        sb.set_state(key, default)
    _payload_refresh(sb)
    ui.notify("Session reset to defaults.", type="negative")
    logger.info(f"_reset_everything user={sb.username}")


# ── Source file downloads ─────────────────────────────────────────────────────
# Auto-discover .py / .env files in the app directory (excluding caches & logs).

_SOURCE_EXCLUDE_NAMES: set[str] = {"__init__.py"}
_SOURCE_EXCLUDE_DIRS:  set[str] = {"__pycache__", "logs", "tmp", "images", "icons"}



# ── Main content (no ui.header / ui.left_drawer — safe for embedded use) ─────

def main(username: str = "user", tenant_id: str = "default") -> None:
    """
    Render the app content area.

    Safe to call from landing_home.py's render_app() which runs inside a
    ui.column — no top-level layout elements (header/drawer) are created here.
    Those are created only by the standalone @ui.page('/') handler below.
    """
    nicegui_app.storage.user.setdefault(
        "user", {"username": username, "tenant_id": tenant_id}
    )

    sb = Sandbox(tenant_id=tenant_id, app_name=_APP_SLUG)
    _ensure_user_log_sink(username, sb)
    _init_session_state(sb)

    logger.info(
        f"app_load app={_APP_TITLE} slug={_APP_SLUG} "
        f"payload={_PAYLOAD_MODULE} user={username} tenant={tenant_id}"
    )

    # ── Compact info / action bar ────────────────────────────────────────────
    with ui.row().classes(
        "w-full items-center gap-3 px-4 py-2 border-b flex-wrap"
    ):
        # Show "← Apps" only when embedded inside the apps catalog
        if nicegui_app.storage.user.get("active_app"):
            def _go_to_catalog() -> None:
                nicegui_app.storage.user["active_app"]   = None
                nicegui_app.storage.user["show_catalog"] = True
                ui.navigate.to("/")

            ui.button(
                "← Apps",
                on_click=_go_to_catalog,
            ).props("flat dense no-caps color=primary").tooltip("Back to Apps Catalog")

        ui.label(f"📓 {_APP_TITLE}").classes("font-semibold text-base")
        ui.badge(f"v{_APP_VERSION}", color="primary").classes("text-xs")
        ui.space()
        ui.button(
            "🗑 Clear Data",
            on_click=lambda: _clear_data(sb),
        ).props("flat dense no-caps color=warning")
        ui.button(
            "🔄 Reset Everything",
            on_click=lambda: _reset_everything(sb),
        ).props("flat dense no-caps color=negative")

    # ── Tabs ─────────────────────────────────────────────────────────────────
    with ui.tabs().classes("w-full") as main_tabs:
        tab_startup = ui.tab("🏠 Startup")
        tab_run     = ui.tab("▶ Run")
        tab_logs    = ui.tab("📋 Logs")

    with ui.tab_panels(main_tabs, value=tab_startup).classes("w-full"):
        with ui.tab_panel(tab_startup):
            with ui.column().classes("w-full max-w-3xl p-4"):
                startup_interactive_sine.render_startup_page(sb)

        with ui.tab_panel(tab_run):
            with ui.column().classes("w-full p-4"):
                payload.render_run_page(sb)

        with ui.tab_panel(tab_logs):
            with ui.column().classes("w-full p-4"):
                logs.render_logs_view(sb, app_name=_APP_SLUG)


# ── Standalone entry point ────────────────────────────────────────────────────
# IMPORTANT: @ui.page("/") is guarded by __name__ so that importing this module
# from landing_home.py does NOT register a second "/" handler.

if __name__ in {"__main__", "__mp_main__"}:
    @ui.page("/")
    def _standalone_page() -> None:
        username  = "local_user"
        tenant_id = "standalone"
        nicegui_app.storage.user.setdefault(
            "user", {"username": username, "tenant_id": tenant_id}
        )

        is_dark = [bool(nicegui_app.storage.user.get("dark_mode", False))]
        dark    = ui.dark_mode(value=is_dark[0])

        def _toggle_dark() -> None:
            is_dark[0] = not is_dark[0]
            dark.enable() if is_dark[0] else dark.disable()
            nicegui_app.storage.user["dark_mode"] = is_dark[0]
            dark_btn.props(f'icon={"light_mode" if is_dark[0] else "dark_mode"}')

        with ui.header().classes("items-center px-4 py-2"):
            ui.label(f"📓 {_APP_TITLE}").classes("text-xl font-bold")
            ui.space()
            dark_btn = (
                ui.button(
                    icon="light_mode" if is_dark[0] else "dark_mode",
                    on_click=_toggle_dark,
                )
                .props("flat round dense")
                .tooltip("Toggle dark / light mode")
            )

        main(username=username, tenant_id=tenant_id)

    ui.run(
        storage_secret=os.environ.get(
            "NICEGUI_STORAGE_SECRET", f"{_APP_SLUG}-secret-change-me"
        ),
        port=int(os.environ.get("PORT", str(_STANDALONE_PORT))),
        title=_APP_TITLE,
        dark=False,
        reload=False,
    )
