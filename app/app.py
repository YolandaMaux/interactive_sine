#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.py  –  Entry point for the sample_NB app.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HOW TO ADAPT THIS FILE FOR A NEW APP
 (these are the ONLY lines you ever need to change)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1. APP_NAME     – human-readable display name
 2. APP_VERSION  – semver string
 3. APP_LOG_STEM – base name for the log file (no extension)
 4. The import line for your payload module
 5. The call to your payload's main() inside _render_run_tab()

Everything else (sandbox, logging, startup, logs tabs) is
boilerplate and should NOT be edited.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
from pathlib import Path


# ── sys.path setup ─────────────────────────────────────────────────────────────
# Must happen before any local imports.
#
# _HERE  = apps/sample_NB/app/          (for startup.py, logs.py, payload)
# _ROOT  = apps_catalog/                (for libs/sandbox.py)
#
# This works whether the file is run directly:
#     streamlit run apps/sample_NB/app/app.py
# or imported by landing_home.py from the project root:
#     import apps.sample_NB.app.app

_HERE = Path(__file__).parent.resolve()
_ROOT = _HERE.parent.parent.parent      # apps/sample_NB/app → apps/sample_NB → apps → apps_catalog

for _p in (str(_HERE), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from loguru import logger
from startup import render_startup_page
from logs    import render_logs_view

# ── Framework modules (do not edit) ───────────────────────────────────────────
# Prefer the shared catalog-level sandbox; fall back to the local copy so the
# app still works when run standalone outside the full catalog structure.
try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]



# ── ❶  EDIT: app identity ─────────────────────────────────────────────────────
APP_NAME     = "The Wave"
APP_VERSION  = "1.0"
APP_LOG_STEM = "the_wave"           # becomes <LOGS_PATH>/sample_nb_<tenant>.log

# ── ❷  EDIT: import your payload module ───────────────────────────────────────
import interactive_sine as payload          # ← change "sample_NB" to your module name


# ── Env / logging setup (do not edit) ─────────────────────────────────────────

def _load_env_file() -> None:
    """Load app.env from the same directory as app.py (if present)."""
    env_file = _HERE / "app.env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_env_file()

def _get_logs_path() -> Path:
    raw = os.environ.get("LOGS_PATH", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    local = _HERE / "logs"
    local.mkdir(exist_ok=True)
    return local

# Stdout sink always present
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} | {level} | {name}:{line} | {message}")

_log_sinks_added: set[str] = set()

def _ensure_log_sink(tenant_id: str) -> Path:
    """Add a per-sandbox file sink (once per tenant_id). Returns the log file path."""
    logs_dir = _get_logs_path()
    safe     = "".join(c if c.isalnum() or c in "-_." else "_" for c in tenant_id)
    log_file = logs_dir / f"{safe}_{APP_LOG_STEM}.log"
    if tenant_id not in _log_sinks_added:
        logger.add(
            str(log_file),
            level="INFO",
            rotation="10 MB",
            retention="20 days",
            format="{time} | {level} | {name}:{line} | {message}",
        )
        _log_sinks_added.add(tenant_id)
        logger.info(f"log_sink_created app={APP_NAME} tenant_id={tenant_id} file={log_file}")
    return log_file


# ── ❸  EDIT: render your payload inside this function ─────────────────────────

def _render_run_tab(sb: Sandbox) -> None:
    """
    Wrap your app's main() here.
    Pass username and tenant_id so the payload can build its own Sandbox.
    """
    payload.main(username=sb.username, tenant_id=sb.tenant_id)  # ← ❸ edit this line if your payload has a different entry-point or signature


# ── Main entry point (do not edit) ────────────────────────────────────────────

def main(username: str = "", tenant_id: str = "") -> None:
    # If called by landing_home with explicit args, push them into session_state
    # so Sandbox.__init__ can pick them up via the fallback path.
    if tenant_id:
        st.session_state.setdefault("_sb_tenant_id", tenant_id)
        st.session_state.setdefault("tenant_id",     tenant_id)
    if username:
        user = st.session_state.get("user") or {}
        if not user.get("tenant_id"):
            st.session_state["user"] = {**user, "username": username, "tenant_id": tenant_id}

    sb = Sandbox(tenant_id=tenant_id or "", app_name=APP_LOG_STEM)

    # Wire per-sandbox log file so the Logs tab can find it
    log_file = _ensure_log_sink(sb.tenant_id)
    sb.set_state("_user_log_file", str(log_file))

    logger.info(f"app_load app={APP_NAME} tenant_id={sb.tenant_id}")

    # ── Top-level navigation tabs ──────────────────────────────────────────────
    startup_tab, run_tab, logs_tab = st.tabs(["🏠 Startup", "▶ Run", "📋 Logs"])

    with startup_tab:
        render_startup_page(sb)

    with run_tab:
        _render_run_tab(sb)

    with logs_tab:
        render_logs_view(sb)


if __name__ == "__main__":
    main()
