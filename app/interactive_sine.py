import io
import base64
import numpy as np
import matplotlib.pyplot as plt
from nicegui import ui

try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]

# ── ❶ EDIT: change app_name ─────────────────────────────────────────────────────

def render_run_page(sb: Sandbox) -> None:
    """Render the Run tab content (matches the render_run_page(sb) contract
    required by app_interactive_sine.py)."""

    # Title / header
    ui.link("Interactive Sine Wave", target="https:/www.cbc.ca", new_tab=True).classes("text-xl font-bold")
    ui.label("Play with amplitude and Frequency of a Sine wave!")
    ui.separator()

    # Create three columns: left margin, content, right margin
    with ui.row().classes("w-full"):
        left = ui.column().classes("flex-1")
        center = ui.column().classes("flex-[2]")
        right = ui.column().classes("flex-1")

    with center:
        plot_image = ui.image().classes("w-full")

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
            plot_image.set_source(f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}")

        ui.label("Sine Wave Plotter").classes("text-2xl font-bold")

        with ui.row().classes("w-full gap-4"):
            col1 = ui.column().classes("flex-1")
            col2 = ui.column().classes("flex-1")
        with col1:
            frequency = ui.slider(min=1.0, max=10.0, value=1.0, step=0.1).props("label-always")
        with col2:
            amplitude = ui.slider(min=0.1, max=1.0, value=0.1, step=0.1).props("label-always")

        update_plot(frequency.value, amplitude.value)

        def _on_slider_change() -> None:
            update_plot(frequency.value, amplitude.value)

        frequency.on("update:model-value", lambda _e: _on_slider_change())
        amplitude.on("update:model-value", lambda _e: _on_slider_change())

        ui.label("Range Slider").classes("text-2xl font-bold")
        range_slider = ui.range(min=0, max=30, value={"min": 10, "max": 15}, step=1).props("label-always")
        start_label = ui.label(f"Start Value: {range_slider.value['min']}")
        end_label = ui.label(f"End Value: {range_slider.value['max']}")

        def _on_range_change() -> None:
            start_label.text = f"Start Value: {range_slider.value['min']}"
            end_label.text = f"End Value: {range_slider.value['max']}"

        range_slider.on("update:model-value", lambda _e: _on_range_change())


if __name__ in {"__main__", "__mp_main__"}:
    @ui.page("/")
    def _standalone_page() -> None:
        sb = Sandbox(tenant_id="standalone", app_name="interactive_sine")
        render_run_page(sb)

    ui.run(title="The Wave!")