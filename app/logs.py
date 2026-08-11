#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""logs.py – Generic NiceGUI log viewer. (NiceGUI 3.0+, no Streamlit)

Reusable across all apps:
    from logs import render_logs_view
    render_logs_view(sb, app_name="my_app")

Log file resolution order:
  1. sb.state("_user_log_file")      — path set by the host app's entry point
  2. $LOGS_PATH/<username>_<app_name>.log
  3. <this file's dir>/logs/app.log  — final fallback
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from loguru import logger
from nicegui import ui

from sandbox import Sandbox


_HERE       = Path(__file__).parent.resolve()
_LOCAL_LOGS = _HERE / "logs"
_LOCAL_LOGS.mkdir(exist_ok=True)

_ALL_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_DEFAULT_LEVELS = ["INFO", "WARNING", "ERROR", "CRITICAL"]

# Worker thread limit for blocking file I/O
_WORKER_THREADS = int(os.getenv("CHAT_WORKER_THREADS", "4"))
_io_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the I/O semaphore in the running event loop."""
    global _io_semaphore
    if _io_semaphore is None:
        _io_semaphore = asyncio.Semaphore(_WORKER_THREADS)
    return _io_semaphore


# ── Log file resolution ────────────────────────────────────────────────────────

def _resolve_log_file(sb: Sandbox, app_name: str) -> Path:
    """Return the log file path to display, in priority order."""
    user_log = sb.state("_user_log_file")
    if user_log:
        p = Path(user_log)
        if p.exists():
            return p

    logs_root = Path(os.environ.get("LOGS_PATH", str(_LOCAL_LOGS))).expanduser()
    candidate = logs_root / f"{sb.username}_{app_name}.log"
    if candidate.exists():
        return candidate

    fallback = logs_root / "app.log"
    return fallback if fallback.exists() else (_LOCAL_LOGS / "app.log")


# ── Parsing ────────────────────────────────────────────────────────────────────

def _parse_line(line: str) -> dict[str, str]:
    """Parse a loguru-formatted line → {time, level, message}."""
    try:
        ts, level, _loc, msg = line.split(" | ", 3)
        return {"time": ts.strip(), "level": level.strip(), "message": msg.strip()}
    except ValueError:
        return {"time": "", "level": "INFO", "message": line.strip()}


def _load_records_sync(log_path: str) -> list[dict[str, str]]:
    """Load and parse all non-empty lines from log_path (blocking)."""
    p = Path(log_path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    return [_parse_line(ln) for ln in lines if ln.strip()]


def _filter_records(
    records: list[dict[str, str]],
    levels: list[str],
    query: str,
    tail_n: int,
) -> list[dict[str, str]]:
    """Apply tail / level / text filters; returns list newest-first."""
    if tail_n and len(records) > tail_n:
        records = records[-tail_n:]
    if levels:
        records = [r for r in records if r["level"] in levels]
    if query:
        q = query.lower()
        records = [r for r in records if q in r["message"].lower()]
    return list(reversed(records))


def _level_color(level: str) -> str:
    return {
        "DEBUG":    "text-gray-400",
        "INFO":     "text-blue-600",
        "WARNING":  "text-yellow-600",
        "ERROR":    "text-red-600",
        "CRITICAL": "text-red-800 font-bold",
    }.get(level.upper(), "")


# ── Main render ────────────────────────────────────────────────────────────────

def render_logs_view(
    sb: Sandbox,
    app_name: str = "app",
    title: str = "📋 Logs",
) -> None:
    """
    Render the log viewer into the current NiceGUI context.

    Parameters
    ----------
    sb        : Sandbox  – current user's sandbox (used for log file resolution
                           and persisting filter state across tab switches)
    app_name  : str      – used for fallback log file naming
    title     : str      – section heading
    """
    logger.info(f"Rendering Logs page app={app_name} user={sb.username}")

    log_file = _resolve_log_file(sb, app_name)

    # ── Controls ──────────────────────────────────────────────────────────────
    ui.label(title).classes("text-xl font-semibold")
    ui.label(f"File: {log_file}").classes("text-xs font-mono text-gray-500 mb-2")

    with ui.row().classes("w-full gap-3 items-end flex-wrap mb-3"):
        search_input = ui.input(
            label="Search",
            placeholder="Filter by text…",
            value=sb.state("log_search") or "",
        ).classes("flex-1 min-w-36")

        level_select = ui.select(
            options=_ALL_LEVELS,
            label="Levels",
            multiple=True,
            value=sb.state("log_levels") or _DEFAULT_LEVELS,
        ).classes("w-52")

        tail_input = ui.number(
            label="Tail last N",
            value=float(sb.state("log_tail") or 500),
            min=50, max=5000, step=50,
            format="%.0f",
        ).classes("w-28")

        refresh_btn = ui.button("🔄 Refresh")

    # Table container — cleared and rebuilt on each refresh
    table_col = ui.column().classes("w-full")

    # ── Refresh logic ─────────────────────────────────────────────────────────
    async def _do_refresh() -> None:
        # Persist filter preferences
        sb.set_state("log_search", search_input.value)
        sb.set_state("log_levels", level_select.value)
        sb.set_state("log_tail",   int(tail_input.value or 500))

        # Load file in thread pool to avoid blocking the event loop
        sem = _get_semaphore()
        async with sem:
            records = await asyncio.to_thread(_load_records_sync, str(log_file))

        filtered = _filter_records(
            records,
            levels=level_select.value or [],
            query=search_input.value.strip(),
            tail_n=int(tail_input.value or 500),
        )

        table_col.clear()
        with table_col:
            if not filtered:
                ui.label("No entries match the current filters.").classes(
                    "text-gray-400 italic mt-4"
                )
                return

            # Action row: count + CSV download
            with ui.row().classes("w-full items-center gap-3 mb-2"):
                ui.label(f"{len(filtered)} entries").classes("text-xs text-gray-500")

                csv_lines = ["time,level,message"]
                for r in filtered:
                    safe_msg = r["message"].replace('"', "'")
                    csv_lines.append(f'"{r["time"]}","{r["level"]}","{safe_msg}"')
                csv_bytes = "\n".join(csv_lines).encode("utf-8")

                ui.button(
                    "⬇ CSV",
                    on_click=lambda: ui.download(
                        csv_bytes, filename=f"{log_file.stem}.csv"
                    ),
                ).props("flat dense")

            # Table
            columns = [
                {
                    "name": "time", "label": "Time", "field": "time",
                    "sortable": True, "align": "left",
                    "style": "width:180px; font-family:monospace; font-size:0.8rem",
                },
                {
                    "name": "level", "label": "Level", "field": "level",
                    "sortable": True, "align": "center",
                    "style": "width:90px",
                },
                {
                    "name": "message", "label": "Message", "field": "message",
                    "sortable": False, "align": "left",
                },
            ]
            ui.table(
                columns=columns,
                rows=filtered,
                row_key="time",
                pagination={"rowsPerPage": 25},
            ).classes("w-full text-sm").props("dense flat")

    refresh_btn.on("click", _do_refresh)
    search_input.on("keydown.enter", _do_refresh)

    # Auto-load on render
    ui.timer(0.05, _do_refresh, once=True)
