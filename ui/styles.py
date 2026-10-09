"""Page styling and the static tips page."""
import streamlit as st

CSS = """
<style>
    .main-header {
        text-align: center;
        padding: 1.2rem 0 0.4rem 0;
    }
    .main-header h1 { font-size: 2.6rem; margin-bottom: 0.2rem; }
    .main-header p { color: #666; font-size: 1.05rem; }
    .stButton > button { width: 100%; }
</style>
"""


def apply_styles() -> None:
    """Add our small amount of CSS to the page."""
    st.markdown(CSS, unsafe_allow_html=True)


def render_header() -> None:
    """The title at the top of the page."""
    st.markdown(
        '<div class="main-header"><h1>🌍 TripGenie</h1>'
        "<p>Your AI travel planner with real web research</p></div>",
        unsafe_allow_html=True,
    )


def render_tips() -> None:
    """The 'Tips' tab."""
    st.subheader("How to get the best plan")
    st.markdown(
        """
- **Pick places from the list.** The app needs the exact place to check the weather and the map.
- **Choose a start date.** Dates inside the next 2 weeks use a real weather forecast.
- **Set a total budget** if you have one. TripGenie will warn you when the plan goes over it.
- **Use the notes box** for special needs (wheelchair access, travelling with kids, festivals ...).
- **Ask for changes** under the plan: *"make day 2 cheaper"*, *"add a day trip"*, *"replace the museum"*.
- **Look at the badges.** ✅ means the price comes from a web page (see Sources).
  ⚠️ means it is only an estimate. Always confirm prices before you book.
        """
    )
    st.info("TripGenie is a student project. It can make mistakes, so double-check important details.")
