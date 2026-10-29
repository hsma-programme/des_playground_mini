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
    Show the HSMA logo at the top left of the sidebar.

    Uses ``st.logo`` (the built-in replacement for the old CSS
    ``[data-testid="stSidebarNav"]`` background-image hack). The image is the
    linked file from this repo's ``resources/`` folder, so it resolves both
    locally and on the stlite virtual filesystem.
    """
    st.logo(
        "resources/Chalky HSMA-07-wide white logo tall with tagline - new tagline.png",
        size="large",
        link="https://hsma.co.uk",
    )


def render_looping_plotly_animation(
    fig,
    height=None,
    frame_duration=400,
    transition_duration=600,
    pause_between_loops_ms=1200,
    transparent_background=True,
    margin=None,
    responsive=False,
    text_color=None,
    redraw=None,
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
    it reaches the final frame (with a short pause there), giving a continuous
    loop. Jumping to another frame with the slider does not restart it. The play/pause buttons and slider baked into ``fig`` still work.

    ``st.plotly_chart`` normally hands the figure to Streamlit's frontend, which
    forces a transparent paper/plot background (so the page colour shows through)
    and trims the plot margins. A standalone HTML export gets neither, so it is
    reproduced here: without it the figure renders on an opaque white card with
    wide default margins that squash the (domain-stretched) background image.

    Params:
    ------
    fig:
        A plotly.graph_objects.Figure containing animation frames, e.g. the
        output of ``vidigi.animation.generate_animation``. Modified in place.
    height: int or None
        Height in pixels of the embedded iframe. Defaults to the figure's own
        ``layout.height`` (plus a small allowance to avoid a scrollbar), or 850
        if the figure has no explicit height. The play button and slider that
        vidigi adds sit *inside* the figure height, so no extra headroom is
        needed.
    frame_duration, transition_duration: int
        Per-frame and transition durations in milliseconds. The defaults match
        vidigi's own defaults so autoplay runs at the same speed as the
        ``play`` button.
    pause_between_loops_ms: int
        How long to hold on the last frame before restarting each loop.
    transparent_background: bool
        If True (default), force a transparent paper/plot background and a
        transparent iframe body so the Streamlit page colour shows through, as
        ``st.plotly_chart`` does.
    margin: dict or None
        Plotly ``layout.margin`` to apply. Defaults to zero on every side;
        Plotly's ``autoexpand`` still reserves room for the slider and buttons.
    responsive: bool
        Passed through to Plotly's JS config. Left False so the figure keeps its
        own ``layout.width`` / ``layout.height`` (matching ``st.plotly_chart(...,
        width="content")``); when True, Plotly stretches the plot to the iframe
        width, which distorts the domain-stretched background image.
    text_color: str or None
        If given, applied to the figure font, the play/pause buttons and the
        slider (label and current-value). Streamlit's frontend normally adapts
        text colour to the app theme; a standalone HTML export does not, so on a
        dark theme the slider clock and tick labels would otherwise render dim.
    redraw: bool or None
        Whether autoplay and looping fully redraw each frame. Needed when the
        figure has traces Plotly can't simply restyle between frames, such as
        those added on a second subplot by vidigi's ``add_synchronised_trace``
        - without it they render on the first frame and then freeze. Defaults
        to whatever the figure's play button uses (vidigi's synchronised trace
        helpers switch that on when needed), or False if there is no play button.
    """
    if redraw is None:
        try:
            redraw = fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["redraw"]
        except (IndexError, KeyError, TypeError):
            redraw = False

    animation_opts = {
        "frame": {"duration": frame_duration, "redraw": redraw},
        "transition": {"duration": transition_duration},
        "mode": "immediate",
    }

    if height is None:
        fig_height = fig.layout.height
        height = int(fig_height) + 10 if fig_height is not None else 850

    layout_updates = {"margin": margin or dict(l=0, r=0, t=0, b=0)}
    if transparent_background:
        layout_updates["paper_bgcolor"] = "rgba(0,0,0,0)"
        layout_updates["plot_bgcolor"] = "rgba(0,0,0,0)"
    if text_color is not None:
        # Merged (not replaced) into the updatemenus/sliders vidigi already set.
        layout_updates["font"] = dict(color=text_color)
        layout_updates["updatemenus"] = [dict(font=dict(color=text_color))]
        layout_updates["sliders"] = [
            dict(
                font=dict(color=text_color),
                currentvalue=dict(font=dict(color=text_color)),
            )
        ]
    fig.update_layout(**layout_updates)

    # {plot_id} is substituted by plotly with the id of the figure's div.
    loop_script = """
    var gd = document.getElementById('{plot_id}');
    var _loopOpts = %s;
    var _lastFrame = null;
    function _vidigiLoop() { Plotly.animate(gd, null, _loopOpts); }
    gd.on('plotly_animatingframe', function (e) { _lastFrame = e.name; });
    gd.on('plotly_animated', function () {
        // Dragging the slider also fires plotly_animated (a one-frame
        // animation), so only restart when the animation has reached the end.
        var frames = gd._transitionData._frames;
        if (frames.length && _lastFrame === frames[frames.length - 1].name) {
            setTimeout(_vidigiLoop, %d);
        }
    });
    """ % (json.dumps(animation_opts), pause_between_loops_ms)

    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        auto_play=True,
        animation_opts=animation_opts,
        post_script=loop_script,
        config={"displayModeBar": False, "responsive": responsive},
    )

    if transparent_background:
        html = html.replace(
            "<body>",
            '<body style="margin:0;padding:0;background-color:transparent;">',
            1,
        )

    # The figure has a fixed pixel width. If the page is narrower than that
    # (narrow window, wide sidebar), shrink the whole figure to fit instead of
    # showing scrollbars, and resize the iframe to match.
    fig_width = fig.layout.width
    if fig_width is not None:
        fit_script = """
<script>
(function () {
    var figW = %d, figH = %d;
    function fit() {
        document.documentElement.style.overflow = 'hidden';
        var s = Math.min(1, window.innerWidth / figW);
        document.body.style.zoom = s;
        if (window.frameElement) {
            window.frameElement.style.height = Math.ceil(figH * s) + 10 + 'px';
        }
    }
    window.addEventListener('resize', fit);
    fit();
})();
</script>
""" % (int(fig_width), int(height) - 10)
        html = html.replace("</body>", fit_script + "</body>", 1)

    components.html(html, height=height, scrolling=True)


# Targets used by the playground (and described in its explanatory text)
UTIL_IDEAL_RANGE = (0.65, 0.85)
WAIT_LIMIT_MINS = 120

# Colours of the shaded "how are we doing?" bands drawn behind the charts
BAND_GOOD = "#5DFDA0"
BAND_WARN = "#FDD049"
BAND_BAD = "#D45E5E"

# Friendly axis labels for the columns of the model's results
UTIL_LABELS = {
    "01b_triage_util": "Triage<br>Bays",
    "02b_registration_util": "Registration<br>Cubicles",
    "03b_examination_util": "Examination<br>Bays",
    "04b_treatment_util(non_trauma)": "Treatment<br>Bays<br>(non-trauma)",
    "06b_trauma_util": "Stabilisation<br>Bays",
    "07b_treatment_util(trauma)": "Treatment<br>Bays<br>(trauma)",
}

WAIT_LABELS = {
    "01a_triage_wait": "Triage",
    "02a_registration_wait": "Registration",
    "03a_examination_wait": "Examination",
    "04a_treatment_wait(non_trauma)": "Treatment<br>(non-trauma)",
    "06a_trauma_wait": "Stabilisation",
    "07a_treatment_wait(trauma)": "Treatment<br>(trauma)",
}


def add_util_bands(fig, orientation):
    """
    Shade a plotly figure by how good a utilisation level is.

    Green is the ideal range, amber is under-used, red is over-stretched or
    barely used.

    Params:
    ------
    fig: plotly.graph_objects.Figure
    orientation: str
        "h" for horizontal bands (utilisation on the y axis), "v" for vertical
        bands (utilisation on the x axis).
    """
    add_band = fig.add_hrect if orientation == "h" else fig.add_vrect
    start, end = ("y0", "y1") if orientation == "h" else ("x0", "x1")

    low, high = UTIL_IDEAL_RANGE
    for band_start, band_end, colour in [
        (low, high, BAND_GOOD),
        (high, 1, BAND_BAD),
        (0.4, low, BAND_WARN),
        (0, 0.4, BAND_BAD),
    ]:
        add_band(
            **{start: band_start, end: band_end},
            fillcolor=colour,
            opacity=0.25,
            line_width=0,
        )


def add_wait_band(fig, orientation):
    """
    Shade the waits that meet the target (under ``WAIT_LIMIT_MINS``) in green.

    Params:
    ------
    fig: plotly.graph_objects.Figure
    orientation: str
        "h" for a horizontal band (waits on the y axis), "v" for a vertical
        band (waits on the x axis).
    """
    add_band = fig.add_hrect if orientation == "h" else fig.add_vrect
    start, end = ("y0", "y1") if orientation == "h" else ("x0", "x1")

    add_band(
        **{start: 0, end: WAIT_LIMIT_MINS},
        fillcolor=BAND_GOOD,
        opacity=0.3,
        line_width=0,
    )


def summarise_results(results):
    """
    Boil a run's replication results down to the headline numbers.

    Params:
    ------
    results: pd.DataFrame
        One row per replication, as returned in ``summary_df`` by
        ``multiple_replications`` (columns containing "util", "wait",
        "00_arrivals" and "09_throughput").

    Returns:
    -------
    dict
        Counts of utilisation/wait metrics (averaged across replications) that
        fall within the ideal range, the longest average wait, the average
        number of patients seen per replication, and total arrivals.
    """
    means = results.mean()
    util = means.filter(like="util")
    wait = means.filter(like="wait")

    return {
        "util_in_range": int(
            ((util > UTIL_IDEAL_RANGE[0]) & (util < UTIL_IDEAL_RANGE[1])).sum()
        ),
        "n_util": len(util),
        "wait_in_range": int((wait < WAIT_LIMIT_MINS).sum()),
        "n_wait": len(wait),
        "longest_wait": wait.max(),
        "patients_seen": means["09_throughput"],
        "arrivals": int(results["00_arrivals"].sum()),
    }


# The stages of the model: their results columns, what to call the resource
# used there, and the sidebar slider (key) that sets how many there are.
STAGES = {
    "triage": dict(
        wait="01a_triage_wait",
        util="01b_triage_util",
        resource="triage cubicle",
        slider="n_triage",
    ),
    "registration": dict(
        wait="02a_registration_wait",
        util="02b_registration_util",
        resource="registration cubicle",
        slider="n_reg",
    ),
    "examination": dict(
        wait="03a_examination_wait",
        util="03b_examination_util",
        resource="examination room",
        slider="n_exam",
    ),
    "non-trauma treatment": dict(
        wait="04a_treatment_wait(non_trauma)",
        util="04b_treatment_util(non_trauma)",
        resource="non-trauma treatment cubicle",
        slider="n_cubicles_1",
    ),
    "stabilisation": dict(
        wait="06a_trauma_wait",
        util="06b_trauma_util",
        resource="stabilisation bay",
        slider="n_trauma",
    ),
    "trauma treatment": dict(
        wait="07a_treatment_wait(trauma)",
        util="07b_treatment_util(trauma)",
        resource="trauma treatment cubicle",
        slider="n_cubicles_2",
    ),
}


def format_minutes(minutes):
    """Format minutes for people, e.g. 45 -> "45 min", 133 -> "2h 13m", 3120 -> "2d 4h"."""
    minutes = round(minutes)
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 24 * 60:
        return f"{minutes // 60}h {minutes % 60:02d}m"
    return f"{minutes // (24 * 60)}d {minutes % (24 * 60) // 60}h"


def hint_pill(text):
    """A small rounded "hint" pill (styled by ``.hint-pill`` in style.css)."""
    return f'<span class="hint-pill">💡 {text}</span>'


def describe_results(results, room_counts):
    """
    Describe a run in a couple of plain-English lines.

    Points at the stage with the longest queue (if any is over the target) and
    at the quietest resource (if it is under-used and could lose a room). Each
    finding is its own box, side by side, with a suggestion shown as a hint pill.

    Params:
    ------
    results: pd.DataFrame
        As for ``summarise_results``.
    room_counts: dict
        How many of each resource were available, keyed by slider key (the
        ``slider`` entries of ``STAGES``).

    Returns:
    -------
    str
        HTML, so render it with ``st.markdown(..., unsafe_allow_html=True)``.
    """
    means = results.mean()

    lines = []

    waits = [
        (means[stage["wait"]], name, stage)
        for name, stage in STAGES.items()
        if means[stage["wait"]] > WAIT_LIMIT_MINS
    ]
    if waits:
        wait, name, stage = max(waits, key=lambda w: w[0])
        lines.append(
            f"The longest queue was for <strong>{name}</strong>:<br>patients waited "
            f"{format_minutes(wait)} on average. "
            + hint_pill(f"Try adding a {stage['resource']}")
        )

    # Only suggest closing something if there is more than one of it
    quiet = [
        (means[stage["util"]], stage)
        for stage in STAGES.values()
        if means[stage["util"]] < UTIL_IDEAL_RANGE[0]
        and room_counts[stage["slider"]] > 1
    ]
    if quiet:
        util, stage = min(quiet, key=lambda q: q[0])
        lines.append(
            f"The {stage['resource']}s were only in use {util:.0%} of the time. "
            + hint_pill("Could you manage with one fewer?")
        )

    if not waits and not quiet:
        lines.append("Nothing is queueing for long and nothing is sitting idle.")

    items = "".join(f'<div class="result-line">{line}</div>' for line in lines)
    return f'<div class="result-box">{items}</div>'


def metric_with_delta(
    col, label, value, current, previous=None, unit="", inverse=False, help=None
):
    """
    Show an ``st.metric`` in ``col`` with its change since the previous run.

    Params:
    ------
    col: streamlit container
        Where to draw the metric (e.g. a column).
    label, value: str
        Passed to ``st.metric``.
    current, previous: float
        The numbers to compare. If ``previous`` is None (first run) no delta is
        shown.
    unit: str
        Appended to the delta, e.g. " min".
    inverse: bool
        True where lower is better, so a drop is shown in green.
    help: str or None
        Tooltip text.
    """
    delta, colour = None, "normal"
    if previous is not None:
        diff = current - previous
        if round(diff) == 0:
            delta, colour = "no change", "off"
        else:
            delta = f"{diff:+,.0f}{unit}"
            colour = "inverse" if inverse else "normal"

    col.metric(label, value, delta=delta, delta_color=colour, help=help)


def hide_running():
    """
    Hide the "running man" status widget; progress is shown in the loading overlay instead.
    """
    st.markdown(
        """
<style>

div[class*="StatusWidget"]{
    display: none;
}

</style>
""",
        unsafe_allow_html=True,
    )
