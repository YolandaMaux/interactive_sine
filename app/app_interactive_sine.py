#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_interactive_sine.py – INTERACTIVE SINE framework launcher / entry point (NiceGUI 3.0+).

Derived from app_template.py (stock_chat_app.py lineage). Follows the generic
entry-point template: the ONLY lines you normally change are the EDIT block below.

INTEGRATION GUIDE (full walkthrough in README.md)
=================================================
STEPS 1-6 for the payload live in main_interactive_sine.py's docstring. This
launcher covers STEP 6 — running / hosting the app:

- Standalone: python app_interactive_sine.py (or uvicorn app_interactive_sine:app)
- Embedded: the landing page imports this module and calls main().
  The payload builds ui.header() / ui.left_drawer(), which raise
  RuntimeError when nested inside a ui.column — so embedding happens at
  page level, never inside a landing-page column (README.md §5).

The launcher intercepts the payload's @ui.page("/") registration (see
_capture_page below) so THIS module owns the "/" route and can wrap the
payload handler with Sandbox / logging / clear-reset scaffolding first.
No edits to main_interactive_sine.py are required, and running
`python main_interactive_sine.py` still works as before.

IMPORTANT: logger configuration is done BEFORE importing the payload
module, so main_interactive_sine and its helpers write to the configured sinks.

Requires: nicegui, loguru, python-dotenv (payload adds: openai, httpx,
numpy, matplotlib).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from loguru import logger

# ── Resolve project root & libs path ──────────────────────────────────────────
HERE = Path(__file__).parent.resolve()

# 1. Add the app's own directory so sibling modules are importable when this
# file is loaded as a package (e.g. apps.interactive_sine.app_interactive_sine).
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# 2. Search parent directories for libs/sandbox.py (same as the NB template).
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
_APP_SLUG = "interactive_sine"             # ← log/state namespace; lowercase, snake
_APP_TITLE = "Interactive Sine Wave App"   # ← shown in info bar + browser title
_APP_VERSION = "1.0"                       # ← shown as badge in the action bar
_ENV_FILENAME = "interactive_sine.env"    # ← .env file next to this file
_SECRETS_ENV_FILENAME = "interactive_sine.secrets.env"  # ← secrets .env ("" to skip)
_STANDALONE_PORT = 8083                    # ← used only by `python app_interactive_sine.py`
_PAYLOAD_MODULE = "main_interactive_sine"  # ← module that owns the whole frame (no .py)
ENV_PREFIX = "INTERACTIVE_SINE_"           # ← env var prefix; keep in sync with
                                           #   main_interactive_sine.py + endpointType_interactive_sine.py
# ═════════════════════════════════════════════════════════════════════════════

def _env(name: str, default: str = "") -> str:
    """Prefix-aware env lookup: _env("PORT") reads INTERACTIVE_SINE_PORT."""
    return os.environ.get(ENV_PREFIX + name, default)

# ── Load .env (must happen BEFORE importing app modules that may read env) ────
try:
    from dotenv import load_dotenv

    LOCAL_ENV_FILE = HERE / _ENV_FILENAME
    LOCAL_SECRETS_FILE = HERE / _SECRETS_ENV_FILENAME
    CONFIG_SOURCE = _env("CONFIG_SOURCE", "local").lower()
    if CONFIG_SOURCE != "compose":
        load_dotenv(LOCAL_ENV_FILE, override=False)
        load_dotenv(LOCAL_SECRETS_FILE, override=False)
        # Fallback to a plain ".env" next to the script.
        load_dotenv(HERE / ".env", override=False)
        logger.info(
            f"{_APP_SLUG} configuration source: local files: "
            f"{LOCAL_ENV_FILE}, {LOCAL_SECRETS_FILE}"
        )
    else:
        logger.info(f"{_APP_SLUG} configuration source: Docker Compose environment")
except ImportError:
    pass

# ── Loguru setup — MUST happen before any app-module imports ──────────────────
_LOCAL_LOG_DIR = HERE / "logs"
_LOCAL_LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="DEBUG")
logger.add(
    str(_LOCAL_LOG_DIR / f"{_APP_SLUG}_app.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file.name}:{function}:{line} | {message}",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    enqueue=True,
    catch=True,
    backtrace=True,
)

# Mark loguru as configured so future app utils don't replace these sinks
# with a simpler single-file setup when imported below.
# (If your utils check a marker attribute, keep this name in sync.)
logger._app_log_configured = True

logger.info(f"{_APP_SLUG} application initialized")
logger.info(f".env file {LOCAL_ENV_FILE}")

# ── Core imports ──────────────────────────────────────────────────────────────
from nicegui import app as nicegui_app
from nicegui import ui

try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]

# Shared logs viewer (optional — the 📋 Logs button is skipped if unavailable).
# Copy logs.py (already app-agnostic) next to this file.
try:
    import logs as shared_logs
except ImportError:
    shared_logs = None

# ── Load the payload module (main_interactive_sine.py owns the whole frame) ───
# main_interactive_sine decorates index() with @ui.page("/"). Capture that handler
# instead of letting it register the route, so THIS module owns the "/" page
# and can wrap it with the Sandbox / logging scaffolding. The patch is
# reverted immediately after the import.
_ui_page = ui.page
_PAYLOAD_ROOT_PAGE: dict = {}

def _capture_page(path, *args, **kwargs):
    if path == "/":
        def _deco(fn):
            _PAYLOAD_ROOT_PAGE["handler"] = fn
            return fn
        return _deco
    return _ui_page(path, *args, **kwargs)

# Tell the payload whether it runs embedded in the landing page (its banner
# is suppressed there — the landing header shows the app name + info, and
# NiceGUI lays out only ONE header per page) or standalone (banner shown).
# Either way a single ~50px header sits above the toolbar, so its offset
# is the same in both modes.
os.environ.setdefault(
    ENV_PREFIX + "EMBEDDED",
    "1" if __name__ not in {"__main__", "__mp_main__"} else "0",
)
os.environ.setdefault(ENV_PREFIX + "TOOLBAR_TOP", "64")

ui.page = _capture_page
try:
    try:
        payload = importlib.import_module(_PAYLOAD_MODULE)
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Payload module '{_PAYLOAD_MODULE}' not found next to {Path(__file__).name}. "
            f"Original error: {exc}"
        ) from exc
finally:
    ui.page = _ui_page

_payload_root_handler = _PAYLOAD_ROOT_PAGE.get("handler")

# ── App icon ──────────────────────────────────────────────────────────────────
# Used as the browser favicon (the payload owns the header, so there is no
# launcher header to embed it in). Drop any png/jpg at this path to use it.
APP_ICON = HERE / "images" / "app-icon.png"

# ── Session defaults ──────────────────────────────────────────────────────────
_BASE_SESSION_DEFAULTS: dict = {
    "settings_saved": False,
    "log_messages": [],
    "_run_count": 0,
}

# Keys cleared by 🗑 Clear Data. Preferences (settings_saved, log filters)
# survive Clear Data — only Reset Everything clears them.
_DATA_KEYS: list[str] = ["log_messages"]

_SESSION_DEFAULTS: dict = dict(_BASE_SESSION_DEFAULTS)

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
    logs_root = Path(os.environ.get("LOGS_PATH", str(HERE / "logs"))).expanduser()
    logs_root.mkdir(parents=True, exist_ok=True)
    log_file = logs_root / f"{safe_user}_{_APP_SLUG}.log"

    sink_key = f"{safe_user}_{sb.tenant_id}"
    if sink_key not in _ensure_user_log_sink._active_sinks:  # type: ignore[attr-defined]
        logger.add(
            str(log_file),
            rotation="10 MB",
            retention="20 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
        )
        _ensure_user_log_sink._active_sinks.add(sink_key)  # type: ignore[attr-defined]

    # Re-asserted on every page load so Reset Everything (which wipes the
    # storage key) restores the pointer for the shared logs viewer.
    sb.set_state("_user_log_file", str(log_file))
    logger.info(f"Log sink opened: {log_file} (user={username} tenant={sb.tenant_id})")

# ── Data management ───────────────────────────────────────────────────────────

def _clear_data(sb: Sandbox) -> None:
    """Clear sandbox data keys only; keep session preferences intact.

    main_interactive_sine keeps chat state inside the page handler, so the page is
    also re-entered to drop that in-memory state."""
    sb.clear_app_state(keys=_DATA_KEYS)
    logger.info(f"_clear_data user={sb.username} keys={_DATA_KEYS}")
    ui.notify(f"🗑 {_APP_TITLE} data cleared.", type="warning")
    ui.navigate.to("/")

def _reset_everything(sb: Sandbox) -> None:
    """Full reset: wipe every sandbox key (and tmp dir) for this app."""
    removed = sb.clear_app_state(wipe_tmp=True)
    for key, default in _SESSION_DEFAULTS.items():
        sb.set_state(key, default)
    logger.info(f"_reset_everything user={sb.username} removed={removed} keys")
    ui.notify("Session reset to defaults.", type="negative")
    ui.navigate.to("/")

# ── Main content ──────────────────────────────────────────────────────────────

def main(username: str = "user", tenant_id: str = "default") -> None:
    """Render the app content area.

    Standalone-only: the payload builds ui.header() / ui.left_drawer(), so
    this must NOT be called from inside a ui.column (raises RuntimeError,
    same as the payload's own @ui.page("/")).

    No authentication is performed here — the host framework (or the
    standalone page below) is responsible for resolving `username` /
    `tenant_id` before calling main().
    """
    nicegui_app.storage.user.setdefault(
        "user", {"username": username, "tenant_id": tenant_id}
    )

    sb = Sandbox(tenant_id=tenant_id, app_name=_APP_SLUG)
    _ensure_user_log_sink(username, sb)
    _init_session_state(sb)

    logger.info(
        f"app_load app={_APP_TITLE} slug={_APP_SLUG} "
        f"user={username} tenant={tenant_id}"
    )

    # ── Floating action bar (payload owns the header, so Clear / Reset /
    # Logs / version live in a small fixed bar bottom-right) ─────────
    with ui.element("div").classes("column items-center q-gutter-xs").style(
        "position: fixed; right: 12px; bottom: 12px; z-index: 5000;"
        " background: rgba(255, 255, 255, 0.9); border-radius: 12px; padding: 4px;"
    ):
        clear_btn = ui.button(
            icon="delete", on_click=lambda: _clear_data(sb)
        ).props("flat dense round")
        with clear_btn:
            ui.tooltip("clear data: drop sandbox data keys")
        reset_btn = ui.button(
            icon="restart_alt", on_click=lambda: _reset_everything(sb)
        ).props("flat dense round")
        with reset_btn:
            ui.tooltip("reset everything: wipe sandbox state and tmp")
        if shared_logs is not None:
            logs_btn = ui.button(
                icon="assignment", on_click=lambda: logs_dialog.open()
            ).props("flat dense round")
            with logs_btn:
                ui.tooltip("view app logs")
        ui.badge(f"v{_APP_VERSION}").props("outline")

    # ── Logs dialog (shared logs viewer) ────────────────────────────────
    if shared_logs is not None:
        with ui.dialog() as logs_dialog:
            with ui.card().classes("w-[820px] max-w-full"):
                shared_logs.render_logs_view(sb, app_name=_APP_SLUG)
                with ui.row().classes("w-full justify-end"):
                    ui.button("Close", on_click=logs_dialog.close).props("flat")

    # ── Payload frame: header, drawer, toolbar, main window ────────────
    if _payload_root_handler is not None:
        _payload_root_handler()
    else:
        with ui.column().classes("w-full p-4"):
            ui.label(_APP_TITLE).classes("text-xl font-bold")
            ui.label(
                f"Payload page handler not found — {_PAYLOAD_MODULE}.py must "
                "decorate its page function with @ui.page('/')."
            ).classes("text-negative")
        logger.error("payload root page handler was not captured")

# ── Standalone entry point ────────────────────────────────────────────────────
# IMPORTANT: @ui.page("/") is guarded by __name__ so that importing this module
# from landing_home.py does NOT register a "/" handler. The payload's own
# @ui.page("/") was captured at import (see _capture_page above) and is invoked
# by main() instead.

if __name__ in {"__main__", "__mp_main__"}:

    @ui.page("/")
    def _standalone_page() -> None:
        main(username="local_user", tenant_id="standalone")

    # Hand the launcher port to main_interactive_sine.py (its own ui.run reads
    # *_PORT when executed directly in this same process).
    os.environ.setdefault(
        ENV_PREFIX + "PORT", os.environ.get("PORT", str(_STANDALONE_PORT))
    )

    ui.run(
        storage_secret=(
            _env("NICEGUI_STORAGE_SECRET")
            or os.environ.get("NICEGUI_STORAGE_SECRET")
            or f"{_APP_SLUG}-secret-change-me"
        ),
        port=int(
            os.environ.get(
                ENV_PREFIX + "PORT",
                os.environ.get("PORT", str(_STANDALONE_PORT)),
            )
        ),
        title=f"🌊 {_APP_TITLE}",
        favicon=str(APP_ICON) if APP_ICON.exists() else "🌊",
        host="0.0.0.0",
        dark=False,
        reload=True,
    )
