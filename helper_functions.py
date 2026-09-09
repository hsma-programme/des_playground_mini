import json
import urllib.request as request
import streamlit as st
import streamlit.components.v1 as components


def read_file_contents(file_name):
    """'
    Read the contents of a file.

    Params:
    ------
    file_name: str
        Path to file.

    Returns:
    -------
    str
    """
    with open(file_name) as f:
        return f.read()


def read_file_contents_web(path):
    """
    Download the content of a file from the GitHub Repo and return as a utf-8 string

    Notes:
    -------
        adapted from 'https://github.com/streamlit/demo-self-driving'

    Parameters:
    ----------
    path: str
        e.g. file_name.md

    Returns:
    --------
    utf-8 str

    """
    response = request.urlopen(path)
    return response.read().decode("utf-8")


def add_logo():
    """
    Add a logo at the top of the page navigation sidebar

    Approach written by blackary on
    https://discuss.streamlit.io/t/put-logo-and-title-above-on-top-of-page-navigation-in-sidebar-of-multipage-app/28213/5

    """
    st.markdown(
        """
        <style>
            [data-testid="stSidebarNav"] {
                background-image: url(https://raw.githubusercontent.com/hsma-programme/Teaching_DES_Concepts_Streamlit/main/resources/hsma_logo_transparent_background_small.png);
                background-repeat: no-repeat;
                padding-top: 175px;
                background-position: 40px 30px;
            }
            [data-testid="stSidebarNav"]::before {
                content: "The DES Playground";
                padding-left: 20px;
                margin-top: 50px;
                font-size: 30px;
                position: relative;
                top: 100px;
            }

        </style>
        """,
        unsafe_allow_html=True,
    )


def render_looping_plotly_animation(
    fig,
    height=850,
    frame_duration=400,
    transition_duration=600,
    pause_between_loops_ms=1200,
):
    """
    Render an animated Plotly figure so that it starts playing on load and loops.

    Streamlit's ``st.plotly_chart`` cannot autoplay (or loop) a Plotly frame
    animation, so instead the figure is exported to a self-contained HTML
    document (plotly.js pulled from the CDN) and embedded via
    ``st.components.v1.html``. This keeps working under stlite because the
    iframe only needs the browser plus a CDN - no Pyodide involvement.

    Plotly's own ``auto_play=True`` starts the animation once ``newPlot``
    resolves. A small ``post_script`` then re-triggers the animation each time
    it finishes (with a short pause on the final frame), giving a continuous
    loop. The play/pause buttons and slider baked into ``fig`` still work.

    Params:
    ------
    fig:
        A plotly.graph_objects.Figure containing animation frames, e.g. the
        output of ``vidigi.animation.generate_animation``.
    height: int
        Height in pixels of the embedded iframe (leave headroom above the
        figure's own height for the play button / slider strip).
    frame_duration, transition_duration: int
        Per-frame and transition durations in milliseconds. The defaults match
        vidigi's own defaults so autoplay runs at the same speed as the
        ``play`` button.
    pause_between_loops_ms: int
        How long to hold on the last frame before restarting each loop.
    """
    animation_opts = {
        "frame": {"duration": frame_duration, "redraw": False},
        "transition": {"duration": transition_duration},
        "mode": "immediate",
    }

    # {plot_id} is substituted by plotly with the id of the figure's div.
    loop_script = """
    var gd = document.getElementById('{plot_id}');
    var _loopOpts = %s;
    function _vidigiLoop() { Plotly.animate(gd, null, _loopOpts); }
    gd.on('plotly_animated', function () {
        setTimeout(_vidigiLoop, %d);
    });
    """ % (json.dumps(animation_opts), pause_between_loops_ms)

    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        auto_play=True,
        animation_opts=animation_opts,
        post_script=loop_script,
        config={"displayModeBar": False},
    )

    components.html(html, height=height, scrolling=True)


def center_running():
    """
    Have the "running man" animation in the center of the screen instead of the top right corner.
    """
    st.markdown(
        """
<style>

div[class*="StatusWidget"]{

    position: fixed;
    margin: auto;
    top: 50%;
    left: 50%;
    marginRight: "0px"
    width: 50%;
    scale: 2.75;
    opacity: 1
}

</style>
""",
        unsafe_allow_html=True,
    )
