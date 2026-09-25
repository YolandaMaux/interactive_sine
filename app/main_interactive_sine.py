#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_interactive_sine.py – INTERACTIVE SINE framework payload module (NiceGUI 3.0+).

Derived from main_template.py (stock_chat_main.py / Ticker Talk lineage). This
module owns the whole page frame: header, left drawer (side window), vertical
tool bar and the main window.

Framework layout
----------------
- ui.header .................. banner (suppressed when embedded)
- ui.left_drawer ............. side window; WIDTH configurable via .env
  (INTERACTIVE_SINE_SIDEBAR_WIDTH)
- vertical tool bar (fixed) ... core buttons + tool buttons
- main window ................. switchable views (chat / table / grid / plot)

INTERACTIVE SINE CUSTOMISATION (requirements 1-5 of the port)
-------------------------------------------------------------
1. The app info bubble renders the Getting Started text from
   startup_interactive_sine.py (GETTING_STARTED_MARKDOWN).
2. ALL controls (frequency / amplitude / range sliders, taken from
   interactive_sine.py) live in the tool 1 panel, renamed "Controls"
   with a "tune" icon in the vertical tool bar.
3. Placeholder tool 2 is removed.
4. The table view shows a live interactive text display of the Controls
   sliders (frequency / amplitude / range values, updated on the fly).
5. The plot view renders the interactive sine wave (matplotlib, base64
   PNG like interactive_sine.py) and is redrawn by the Controls sliders.

Run standalone (for testing): python main_interactive_sine.py
"""

from __future__ import annotations

import base64
import io
import os
import re
from datetime import datetime

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from nicegui import ui

# Load interactive_sine.env directly too, so defaults resolve even when launched
# without app_interactive_sine.py (`python main_interactive_sine.py`).
try:
    from dotenv import load_dotenv

    load_dotenv(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "interactive_sine.env"),
        override=False,
    )
except ImportError:
    pass

# Endpoint routing: llama.cpp OpenAI-compatible vs Perplexity Agent API,
# chosen automatically from INTERACTIVE_SINE_LLM_ENGINE_URL.
import endpointType_interactive_sine as endpointType

# Getting Started text rendered inside the info bubble (requirement 1).
import startup_interactive_sine

# ── Config ───────────────────────────────────────────────────────────────────
# All env vars share this prefix. Renamed from TEMPLATE_ when forking the
# template; keep it in sync with app_interactive_sine.py and
# endpointType_interactive_sine.py.
ENV_PREFIX = "INTERACTIVE_SINE_"

def _env(name: str, default: str = "") -> str:
    return os.environ.get(ENV_PREFIX + name, default)

# Side window (left drawer) width, configurable via .env.
# Falls back to 600 — the same width the original Ticker Talk drawer used.
_SIDEBAR_WIDTH = int(_env("SIDEBAR_WIDTH", "600"))

# Embedded mode flag — set by app_interactive_sine.py (INTERACTIVE_SINE_EMBEDDED)
# before this module is imported. Embedded in the landing page, the banner below
# is suppressed: the landing header shows the app name + info instead, and
# NiceGUI lays out only ONE header per page.
_EMBEDDED = _env("EMBEDDED", "0") == "1"

# Vertical toolbar top offset: 64px standalone, 114px embedded
# (set by the launcher before importing this module).
_TOOLBAR_TOP = _env("TOOLBAR_TOP", "64")

DEFAULT_PARAMS = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 40,
    "max_tokens": 1024,
    "system_prompt": (
        _env("CHAT_DEFAULT_SYSTEM_PROMPT") or "You are a helpful assistant."
    ).strip('"'),
}

DEFAULT_MODEL = _env("CHAT_DEFAULT_MODEL", "local-model")

# ── Local model discovery (OpenAI-compatible /v1/models) ────────────────────

try:
    from openai import OpenAI
except ImportError:  # pip install openai
    OpenAI = None  # type: ignore[assignment]

_LLM_BASE_URL = _env("LLM_ENGINE_URL", "http://localhost:8080").rstrip("/") + "/v1"

def _build_llm_client():
    return (
        OpenAI(
            base_url=_LLM_BASE_URL,
            api_key=_env("LLM_API_KEY", "not-needed"),
        )
        if OpenAI is not None
        else None
    )

_llm_client = _build_llm_client()

def fetch_models() -> list:
    """Model ids for the settings dropdown: local llama.cpp /v1/models, or the
    Perplexity sonar family when *_LLM_ENGINE_URL points at the cloud."""
    if endpointType.is_perplexity(endpointType.get_base_url("llm")):
        return ["sonar", "sonar-pro", "sonar-reasoning-pro"]
    if _llm_client is None:
        ui.notify("openai package not installed (pip install openai).", type="warning")
        return ["local-model"]
    try:
        return sorted(md.id for md in _llm_client.models.list().data)
    except Exception as exc:
        ui.notify(f"Could not read models from {_LLM_BASE_URL}: {exc}", type="warning")
        return ["local-model"]

try:
    import httpx
except ImportError:  # pip install httpx
    httpx = None  # type: ignore[assignment]

@ui.page("/")
def index():

    messages = []  # full history, ready for a real backend later
    params = dict(DEFAULT_PARAMS)
    model_name = {"value": DEFAULT_MODEL}
    dark = {"on": False}
    active_panel = {"name": None}
    current_view = {"name": "chat"}

    # ── Interactive sine state (shared: Controls panel ↔ table view ↔ plot view) ──
    # Requirement 4 + 5: the sliders live in the Controls panel; their values
    # drive the table-view text display and the plot-view sine wave.
    sine_state = {
        "frequency": 1.0,
        "amplitude": 0.1,
        "range_min": 10,
        "range_max": 15,
    }
    plot_image = {"element": None}
    # Live label elements of the table view (None when the table view is not
    # on screen). Same pattern as plot_image above.
    slider_text_labels = {"frequency": None, "amplitude": None, "range": None}

    # ── Chat / streaming framework (unchanged behaviour from Ticker Talk) ──

    async def stream_completion(payload: dict):
        """Stream assistant deltas via endpointType_interactive_sine: OpenAI-compatible
        llama.cpp when *_LLM_ENGINE_URL is local, Perplexity Agent API when
        it points at api.perplexity.ai (uses *_LLM_API_KEY)."""
        if httpx is None:
            yield "httpx package not installed (pip install httpx)."
            return

        base = endpointType.get_base_url("llm")
        conv = {
            "model": payload["model"],
            "messages": payload["messages"],
            "system_prompt": "",
            "temperature": payload["temperature"],
            "max_tokens": payload["max_tokens"],
        }
        url = endpointType.endpoint("chat")
        body = endpointType.build_chat_payload_for(conv, base)
        api_key = _env("LLM_API_KEY", "not-needed")
        headers = {"Authorization": f"Bearer {api_key}"}

        async with httpx.AsyncClient(
            timeout=float(_env("HTTPX_TIMEOUT_CHAT", "600"))
        ) as client:
            async with client.stream(
                "POST", url, json=body, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    delta, done = endpointType.parse_stream_chunk_for(line, base)
                    if delta:
                        yield delta
                    if done:
                        break

    async def send() -> None:
        prompt = input_box.value.strip()
        if not prompt:
            return
        input_box.value = ""
        messages.append({"role": "user", "content": prompt})
        with chat_container:
            ui.chat_message(text=prompt, sent=True)
            with ui.chat_message(name=model_name["value"], sent=False):
                send_spinner = ui.spinner(size="lg")
                result = ui.markdown("")
                copy_row = ui.row().classes("q-gutter-xs")
        scroll_to_end()

        payload = {
            "model": model_name["value"],
            "messages": (
                [{"role": "system", "content": params["system_prompt"]}]
                if params["system_prompt"]
                else []
            )
            + messages,
            "temperature": params["temperature"],
            "top_p": params["top_p"],
            "top_k": params["top_k"],
            "max_tokens": params["max_tokens"],
            "stream": True,
        }

        acc = ""
        first_token = True
        try:
            async for delta in stream_completion(payload):
                if first_token:
                    send_spinner.set_visibility(False)
                    first_token = False
                acc += delta
                result.set_content(acc)
                scroll_to_end()
        except Exception as e:
            send_spinner.set_visibility(False)
            result.set_content(f"**Error:** {e}")
        else:
            messages.append({"role": "assistant", "content": acc})
            # multi-output: every assistant answer gets its own copy buttons
            with copy_row:
                copy_text_button = ui.button(
                    icon="content_copy",
                    on_click=lambda t=_strip_markdown(acc): _copy_to_clipboard(t, "text"),
                ).props("flat dense round size=sm")
                with copy_text_button:
                    ui.tooltip("copy as plain text")
                copy_md_button = ui.button(
                    icon="code",
                    on_click=lambda t=acc: _copy_to_clipboard(t, "markdown"),
                ).props("flat dense round size=sm")
                with copy_md_button:
                    ui.tooltip("copy as markdown (.md)")

    def scroll_to_end() -> None:
        chat_scroll.scroll_to(percent=1.0)

    def _strip_markdown(md_text: str) -> str:
        """Crude markdown -> plain text for the copy-as-text button."""
        text = re.sub(r"```", "", md_text)
        text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
        text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        return text

    def _copy_to_clipboard(text: str, kind: str) -> None:
        ui.clipboard.write(text)
        ui.notify(f"Copied as {kind}.")

    def download_chat() -> None:
        if not messages:
            ui.notify("No chat history to download yet.", type="warning")
            return
        lines = ["# Interactive Sine Wave App Session", ""]
        for msg in messages:
            heading = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(msg["content"])
            lines.append("")
        ui.download(
            "\n".join(lines).encode("utf-8"),
            filename=f"app_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        )

    def clear_chat() -> None:
        global _llm_client
        messages.clear()
        chat_container.clear()
        with chat_container:
            ui.chat_message(
                text="what would you like to know?",
                name=model_name["value"],
                sent=False,
            )
        # rebuild the LLM client so any cached connection state is dropped
        _llm_client = _build_llm_client()

    def toggle_dark() -> None:
        dark["on"] = not dark["on"]
        ui.dark_mode().enable() if dark["on"] else ui.dark_mode().disable()

    # ── Interactive sine plot (from interactive_sine.py, requirement 5) ──
    # Same matplotlib + base64 PNG approach as the original run page; the
    # image element now lives in the plot view instead of next to the sliders.
    def update_plot(frequency, amplitude):
        fig, ax = plt.subplots()
        x = np.linspace(0, 2 * np.pi, 100)
        y = amplitude * np.sin(frequency * x)
        ax.plot(x, y)
        ax.set_title(f"Sine Wave with amplitude:{amplitude}, Frequency: {frequency}")
        ax.set_xlabel("x")
        ax.set_ylabel("sin(frequency * x)")
        ax.set_ylim(-1.5, 1.5)
        ax.grid()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        if plot_image["element"] is not None:
            plot_image["element"].set_source(
                f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}"
            )

    # ── Banner: title, app info, dark mode (tools live in the vertical bar) ──
    # Suppressed when embedded: the landing header carries the app name + info.
    if not _EMBEDDED:
        with ui.header().classes("items-center"):
            ui.label("Interactive Sine Wave App").classes("text-h6 q-mx-sm")
            info_button = ui.button(
                icon="info", on_click=lambda: toggle_info()
            ).props("flat color=white")
            with info_button:
                ui.tooltip("app info")

            ui.space()

            ui.button(icon="dark_mode", on_click=toggle_dark).props("flat color=white")

    # ── Left drawer (side window) — width configurable via .env ─────────────
    with ui.left_drawer(bordered=True, value=False).props(
        f"width={_SIDEBAR_WIDTH}"
    ) as left_drawer:
        panel_container = ui.column().classes("w-full").style("padding-left: 56px")

    # ═══════════════════════════════════════════════════════════════════════════
    # ❶ TOOL BUTTONS (left vertical bar) — requirements 2 and 3

    # Every entry below renders ONE button in the vertical toolbar.
    # icon → Material icon name
    # tooltip → hover text
    # handler → function called on click; it opens a panel in the side
    # window and you add UI elements inside it
    # Requirement 2: tool 1 is the Controls panel holding ALL the
    # interactive sine controls (frequency / amplitude / range sliders).
    # Requirement 3: placeholder tool 2 is removed.
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Controls panel implementation (from interactive_sine.py) ────────────
    def show_tool_placeholder_1() -> None:
        """CONTROLS tool panel — frequency / amplitude / range sliders."""
        if active_panel["name"] == "tool_placeholder_1" and left_drawer.value:
            left_drawer.toggle()
            return
        active_panel["name"] = "tool_placeholder_1"
        clear_panel()
        with panel_container:
            ui.label("Controls").classes("text-subtitle1 text-bold q-mt-sm")
            ui.label(
                "Play with amplitude and Frequency of a Sine wave!"
            ).classes("text-caption text-gray-500")
            ui.separator()

            ui.label("Sine Wave Plotter").classes("text-2xl font-bold")
            with ui.row().classes("w-full gap-4"):
                col1 = ui.column().classes("flex-1")
                col2 = ui.column().classes("flex-1")
                with col1:
                    frequency = ui.slider(
                        min=1.0, max=10.0, value=sine_state["frequency"], step=0.1
                    ).props("label-always")
                with col2:
                    amplitude = ui.slider(
                        min=0.1, max=1.0, value=sine_state["amplitude"], step=0.1
                    ).props("label-always")

            ui.label("Range Slider").classes("text-2xl font-bold")
            range_slider = ui.range(
                min=0,
                max=30,
                value={"min": sine_state["range_min"], "max": sine_state["range_max"]},
                step=1,
            ).props("label-always")
            start_label = ui.label(f"Start Value: {range_slider.value['min']}")
            end_label = ui.label(f"End Value: {range_slider.value['max']}")

            def _on_slider_change() -> None:
                sine_state["frequency"] = frequency.value
                sine_state["amplitude"] = amplitude.value
                _update_slider_text()
                _refresh_plot_if_visible()

            frequency.on("update:model-value", lambda _e: _on_slider_change())
            amplitude.on("update:model-value", lambda _e: _on_slider_change())

            def _on_range_change() -> None:
                start_label.text = f"Start Value: {range_slider.value['min']}"
                end_label.text = f"End Value: {range_slider.value['max']}"
                sine_state["range_min"] = range_slider.value["min"]
                sine_state["range_max"] = range_slider.value["max"]
                _update_slider_text()

            range_slider.on("update:model-value", lambda _e: _on_range_change())
        if not left_drawer.value:
            left_drawer.toggle()

    TOOLBAR_BUTTONS = [
        {"icon": "tune",
         "tooltip": "controls — frequency, amplitude and range sliders",
         "handler": lambda: show_tool_placeholder_1()},
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # ❷ MAIN-WINDOW VIEW BUTTONS (left vertical bar)

    # Every entry renders one button that switches the MAIN window between
    # registered views. "chat" is built in (scrolling, streaming
    # multi-output, copy); the table view carries the interactive slider
    # text display (requirement 4); the others are renderers registered
    # in MAIN_VIEWS below.
    # ═══════════════════════════════════════════════════════════════════════════

    VIEW_TOOLBAR_BUTTONS = [
        {"icon": "chat", "tooltip": "show chat view", "view": "chat"},
        {"icon": "table_chart", "tooltip": "show table view", "view": "table"},
        {"icon": "grid_view", "tooltip": "show grid view", "view": "grid"},
        {"icon": "show_chart", "tooltip": "show plot view", "view": "plot"},
    ]

    # ── Vertical tool bar (left edge, under the banner) ──────────────────────
    with ui.element("div").classes("column items-center q-gutter-sm q-pt-md").style(
        f"position: fixed; left: 0; top: {_TOOLBAR_TOP}px; bottom: 0; width: 56px;"
        # Theme 1: Deep teal + amber
        " z-index: 4000; background: #f0fdfa; border-right: 1px solid #99f6e4;"
        # Theme 2: Indigo + gold
        # " z-index: 4000; background: #eef2ff; border-right: 1px solid #c7d2fe;"
    ):
        new_chat_button = ui.button(
            icon="add_comment", on_click=lambda: clear_chat()
        ).props("flat dense")
        with new_chat_button:
            ui.tooltip("new chat: clear session and LLM context")

        download_chat_button = ui.button(
            icon="download", on_click=lambda: download_chat()
        ).props("flat dense")
        with download_chat_button:
            ui.tooltip("download chat history (.md)")

        settings_button = ui.button(
            icon="settings", on_click=lambda: show_settings()
        ).props("flat dense")
        with settings_button:
            ui.tooltip("system settings")

        ui.separator()

        # Controls tool button (requirement 2) — driven by the list above
        for spec in TOOLBAR_BUTTONS:
            tool_button = ui.button(
                icon=spec["icon"], on_click=spec["handler"]
            ).props("flat dense")
            with tool_button:
                ui.tooltip(spec["tooltip"])

        ui.separator()

        # Main-window view switcher
        for spec in VIEW_TOOLBAR_BUTTONS:
            view_button = ui.button(
                icon=spec["icon"],
                on_click=lambda v=spec["view"]: show_view(v),
            ).props("flat dense")
            with view_button:
                ui.tooltip(spec["tooltip"])

        ui.separator()

        collapse_button = ui.button(
            icon="menu_open", on_click=lambda: left_drawer.toggle()
        ).props("flat dense")
        with collapse_button:
            ui.tooltip("collapse the side panel")

    # ---- app info bubble (fixed position, scrollable, stays on screen) ----
    # Requirement 1: includes the Getting Started text from
    # startup_interactive_sine.py.
    with ui.card().classes("w-96").style(
        f"position: fixed; left: 72px; top: {int(_TOOLBAR_TOP) + 8}px; z-index: 5000;"
    ) as chat_info_panel:
        ui.label("About Interactive Sine Wave App").classes("text-subtitle1 text-bold")
        with ui.scroll_area().classes("max-h-96 w-full"):
            ui.label("Getting Started").classes("text-xl font-semibold")
            ui.markdown(startup_interactive_sine.GETTING_STARTED_MARKDOWN)
            ui.separator()
            ui.markdown(
                "In this app: use the **Controls** tool in the left toolbar "
                "to move the frequency, amplitude and range sliders. The "
                "**table view** shows the current slider values and the "
                "**plot view** shows the live sine wave."
            )
    chat_info_panel.visible = False

    def toggle_info() -> None:
        chat_info_panel.visible = not chat_info_panel.visible

    def clear_panel() -> None:
        panel_container.clear()

    # ── Settings panel (framework: model + sampling parameters) ─────────────
    def show_settings() -> None:
        if active_panel["name"] == "settings" and left_drawer.value:
            left_drawer.toggle()
            return
        active_panel["name"] = "settings"
        clear_panel()
        with panel_container:
            ui.label("Settings").classes("text-subtitle1 text-bold q-mt-sm")

            model_options = fetch_models()
            if model_name["value"] not in model_options:
                model_options.append(model_name["value"])
            model_select = ui.select(
                options=model_options,
                label="model",
                value=model_name["value"],
            ).on_value_change(
                lambda e: model_name.update(value=e.value)
            ).props("dense outlined").classes("w-full")

            def refresh_models() -> None:
                fresh = fetch_models()
                if model_name["value"] not in fresh:
                    fresh.append(model_name["value"])
                model_select.options = fresh
                ui.notify("Models refreshed.", type="positive")

            ui.button(
                "Refresh models", icon="refresh", on_click=refresh_models
            ).props("flat dense")

            ui.textarea(
                label="System prompt",
                value=params["system_prompt"],
            ).on_value_change(
                lambda e: params.update(system_prompt=e.value)
            ).classes("w-full")

            ui.label("temperature")
            ui.slider(
                min=0.0, max=2.0, step=0.05, value=params["temperature"]
            ).on_value_change(
                lambda e: params.update(temperature=e.value)
            ).props("label-always")
            ui.label("top_p")
            ui.slider(
                min=0.0, max=1.0, step=0.05, value=params["top_p"]
            ).on_value_change(
                lambda e: params.update(top_p=e.value)
            ).props("label-always")
            ui.label("top_k")
            ui.slider(
                min=1, max=100, step=1, value=params["top_k"]
            ).on_value_change(
                lambda e: params.update(top_k=int(e.value))
            ).props("label-always")
            ui.number(
                label="max tokens", min=16, max=8192, step=16, value=params["max_tokens"]
            ).on_value_change(lambda e: params.update(max_tokens=int(e.value)))

        if not left_drawer.value:
            left_drawer.toggle()

    # ── Main window (fills the screen; input box ~10% above the bottom) ─────
    # The chat area and the alternate-view container are siblings; show_view()
    # toggles between them. The chat view keeps its scroll_area, streaming
    # multi-output and copy buttons; alternate views (table / grid / plot)
    # get their own scroll_area. The interactive slider text display lives
    # in the table view (requirement 4).
    with ui.column().classes("w-[80%] mx-auto").style(
        "height: calc(90vh - 64px);"
    ):
        with ui.scroll_area().classes("w-full flex-grow") as chat_scroll:
            chat_container = ui.column().classes("w-full")
        with ui.row().classes("w-full") as input_row:
            input_box = (
                ui.input(placeholder="Ask the app …")
                .props("outlined")
                .classes("flex-grow")
                .on("keydown.enter", lambda: ui.timer(0.01, send, once=True))
            )
            ui.button(icon="send", on_click=lambda: ui.timer(0.01, send, once=True))
        with ui.scroll_area().classes("w-full flex-grow") as alt_view_scroll:
            alt_view_container = ui.column().classes("w-full")
        alt_view_scroll.visible = False

    # ── Live slider text + plot refresh (table view / plot view wiring) ──────

    def _update_slider_text() -> None:
        """Interactive text display of the Controls sliders (table view)."""
        if slider_text_labels["frequency"] is not None:
            slider_text_labels["frequency"].text = f"Frequency: {sine_state['frequency']}"
        if slider_text_labels["amplitude"] is not None:
            slider_text_labels["amplitude"].text = f"Amplitude: {sine_state['amplitude']}"
        if slider_text_labels["range"] is not None:
            slider_text_labels["range"].text = (
                f"Range: {sine_state['range_min']} - {sine_state['range_max']}"
            )

    def _refresh_plot_if_visible() -> None:
        """Redraw the sine wave when the plot view is on screen."""
        if current_view["name"] == "plot" and plot_image["element"] is not None:
            update_plot(sine_state["frequency"], sine_state["amplitude"])

    # ═══════════════════════════════════════════════════════════════════════════
    # ❸ MAIN-WINDOW VIEW RENDERERS

    # Each renderer runs inside alt_view_container (already wrapped in a
    # scroll_area, so scrolling is preserved). Add ANY UI elements you
    # need: tables, grids, plots, cards, images, markdown…
    # Reuse _copy_to_clipboard(text, kind) to give any view a copy button.
    # ═══════════════════════════════════════════════════════════════════════════

    def render_table_view() -> None:
        """INTERACTIVE main-window view: table with the live Controls slider
        values (requirement 4).

        The labels are registered in slider_text_labels so the Controls
        sliders update them live via _update_slider_text()."""
        ui.label("Table view").classes("text-h6")
        with ui.row().classes("w-full items-center gap-6 q-px-sm"):
            frequency_text_label = ui.label(
                f"Frequency: {sine_state['frequency']}"
            ).classes("text-subtitle1 font-bold text-blue-600")
            amplitude_text_label = ui.label(
                f"Amplitude: {sine_state['amplitude']}"
            ).classes("text-subtitle1 font-bold text-blue-600")
            range_text_label = ui.label(
                f"Range: {sine_state['range_min']} - {sine_state['range_max']}"
            ).classes("text-subtitle1 font-bold text-blue-600")
        slider_text_labels["frequency"] = frequency_text_label
        slider_text_labels["amplitude"] = amplitude_text_label
        slider_text_labels["range"] = range_text_label

    def render_grid_view() -> None:
        """PLACEHOLDER main-window view: grid of cards."""
        ui.label("Grid view").classes("text-h6")
        # ── ADD YOUR UI ELEMENTS HERE ────────────────────────────────────────
        # Example:
        # with ui.grid(columns=3).classes("w-full gap-2"):
        #     for i in range(9):
        #         with ui.card().classes("items-center"):
        #             ui.label(f"card {i}")
        ui.label(
            "(placeholder — add your UI elements here)"
        ).classes("text-caption text-gray-500")

    def render_plot_view() -> None:
        """INTERACTIVE main-window view: sine wave plot (requirement 5).

        The image element is registered in plot_image so the Controls
        sliders redraw it live via update_plot()."""
        ui.label("Plot view").classes("text-h6")
        plot_image["element"] = ui.image().classes("w-full")
        update_plot(sine_state["frequency"], sine_state["amplitude"])

    # Registered main-window views. "chat" is handled natively by show_view;
    # add new views here + a button in VIEW_TOOLBAR_BUTTONS to expose them.
    MAIN_VIEWS = {
        "table": render_table_view,
        "grid": render_grid_view,
        "plot": render_plot_view,
    }

    def show_view(view_name: str) -> None:
        """Switch the main window between chat and registered views.

        Keeps the chat framework intact: switching back to "chat" restores
        the scroll position handling (scroll_to_end on the next message)
        and chat state (messages) is never touched by other views. The
        slider text display lives in the table view (requirement 4), so it
        is rebuilt from sine_state every time the table view is shown."""
        if view_name == "chat":
            current_view["name"] = "chat"
            chat_scroll.visible = True
            input_row.visible = True
            alt_view_scroll.visible = False
            scroll_to_end()
            return
        renderer = MAIN_VIEWS.get(view_name)
        if renderer is None:
            ui.notify(f"View '{view_name}' is not registered in MAIN_VIEWS.",
                      type="warning")
            return
        current_view["name"] = view_name
        chat_scroll.visible = False
        input_row.visible = False
        alt_view_scroll.visible = True
        plot_image["element"] = None
        slider_text_labels["frequency"] = None
        slider_text_labels["amplitude"] = None
        slider_text_labels["range"] = None
        alt_view_container.clear()
        with alt_view_container:
            renderer()

    # ── Startup state ────────────────────────────────────────────────────────
    with chat_container:
        ui.chat_message(
            text="what would you like to know?",
            name=model_name["value"],
            sent=False,
        )

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Interactive Sine Wave App",
        host="0.0.0.0",
        port=int(_env("PORT", "8888")),
        reload=True,
    )
