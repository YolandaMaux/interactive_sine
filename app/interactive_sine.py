import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st



try:
    from libs.sandbox import Sandbox
except ImportError:
    from sandbox import Sandbox  # type: ignore[no-redef]

# ── ❶  EDIT: change app_name ─────────────────────────────────────────────────────

# Create widgets
def main(username: str = "", tenant_id: str = "") -> None:
    sb = Sandbox(tenant_id=tenant_id, app_name="the_wave")

    st.set_page_config(page_title="The Wave!")  # no wide layout

    # Title / header
    st.subheader("[Interactive Sine Wave](https:/www.cbc.ca)")
    st.text("Play with amplitude and Frequency of a Sine wave!")
    st.markdown("---")

    # Create three columns: left margin, content, right margin
    left, center, right = st.columns([1, 2, 1])

    with center:
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
            st.pyplot(fig)

        st.title("Sine Wave Plotter")

        col1, col2 = st.columns(2)
        with col1:
            frequency = st.slider("Frequency", min_value=1.0, max_value=10.0, value=1.0, step=0.1)
        with col2:
            amplitude = st.slider("Amplitude", min_value=0.1, max_value=1.0, value=0.1, step=0.1)

        update_plot(frequency, amplitude)

        st.title("Range Slider")
        range_slider = st.slider("Select a range", min_value=0, max_value=30, value=[10, 15], step=1)
        st.write(f"Start Value: {range_slider[0]}")
        st.write(f"End Value: {range_slider[1]}")

if __name__ == "__main__":
    main()
