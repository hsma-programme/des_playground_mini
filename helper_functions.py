import json
from numbers import Number
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


# Adds a <select> to the top-level tab bar, mirroring its tabs. style.css only
# shows it below 1320px wide, where it replaces the tab pills. Choosing an option
# clicks the matching tab; a MutationObserver keeps the selected option in step
# when the tab changes, and adds the select back if Streamlit redraws the bar.
MOBILE_NAV_SCRIPT = """
<script>
(function () {
    if (window.__mobileNavInstalled) return;
    window.__mobileNavInstalled = true;

    // Shorter names for tabs whose full label doesn't fit beside the title
    var shortLabels = __SHORT_LABELS__;

    function topTabList() {
        return Array.from(document.querySelectorAll('[role="tablist"]')).find(
            function (list) { return !list.closest('[data-testid="stTabPanel"]'); }
        );
    }

    function tabsOf(list) {
        return Array.from(list.querySelectorAll('[data-testid="stTab"]'));
    }

    function sync() {
        var list = topTabList();
        if (!list) return;
        var tabs = tabsOf(list);
        if (!tabs.length) return;

        var select = list.querySelector('select.mobile-nav');
        if (!select) {
            select = document.createElement('select');
            select.className = 'mobile-nav';
            select.setAttribute('aria-label', 'Page');
            select.addEventListener('change', function () {
                var tab = tabsOf(topTabList())[select.selectedIndex];
                if (tab) tab.click();
            });
            list.appendChild(select);
        }

        var labels = tabs.map(function (tab) {
            var label = tab.textContent.trim();
            return shortLabels[label] || label;
        });
        var current = Array.from(select.options).map(function (o) { return o.text; });
        if (labels.join('\\n') !== current.join('\\n')) {
            select.replaceChildren.apply(select, labels.map(function (label) {
                var option = document.createElement('option');
                option.text = label;
                return option;
            }));
        }

        var selected = tabs.findIndex(function (tab) {
            return tab.getAttribute('data-selected') === 'true';
        });
        if (selected >= 0 && select.selectedIndex !== selected) {
            select.selectedIndex = selected;
        }
    }

    var queued = false;
    new MutationObserver(function () {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () { queued = false; sync(); });
    }).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['data-selected'],
    });
    sync();
})();
</script>
"""


def add_mobile_nav(short_labels=None):
    """
    Add a dropdown that replaces the navbar's tab pills below 1320px wide.

    Runs ``MOBILE_NAV_SCRIPT`` on the page. The script's own container is hidden
    (``.st-key-mobile_nav`` in style.css) so it takes up no space; the script
    still runs.

    Params:
    ------
    short_labels: dict or None
        Maps a tab's full label to the shorter name shown in the dropdown, for
        labels too long to fit beside the title on a phone.
    """
    script = MOBILE_NAV_SCRIPT.replace(
        "__SHORT_LABELS__", json.dumps(short_labels or {})
    )
    with st.container(key="mobile_nav"):
        st.html(script, unsafe_allow_javascript=True)


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

    # The iframe spans the full page width, so centre the fixed-width figure in
    # it (matters on ultrawide monitors, where it would otherwise hug the left).
    html = html.replace(
        "</head>",
        "<style>body{display:flex;justify-content:center;}</style></head>",
        1,
    )

    # The figure has a fixed pixel width. If the page is narrower than that
    # (narrow window, wide sidebar), shrink the whole figure to fit instead of
    # showing scrollbars, and resize the iframe to match. Streamlit also gives
    # the element container around the iframe a fixed height, as both `height`
    # and `flex-basis` (the one that counts in its flex column), so resize that
    # too, or the space below the shrunken figure stays empty.
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
        var frame = window.frameElement;
        if (frame) {
            var h = Math.ceil(figH * s) + 10 + 'px';
            frame.style.height = h;
            var box = frame.closest('[data-testid="stElementContainer"]');
            if (box) {
                box.style.height = h;
                box.style.flexBasis = h;
            }
        }
    }
    window.addEventListener('resize', fit);
    fit();
})();
</script>
""" % (int(fig_width), int(height) - 10)
        html = html.replace("</body>", fit_script + "</body>", 1)

    components.html(html, height=height, scrolling=True)
    # st.components.v1.html is deprecated in favour of st.iframe. Swap to this
    # once it has been checked in a browser (full height, no scrollbar, and
    # still shrinks to fit a narrow window):
    # st.iframe(html, height=height)


# Targets used by the playground (and described in its explanatory text)
UTIL_IDEAL_RANGE = (0.65, 0.85)
# Below this, a resource is barely used (red rather than amber)
UTIL_LOW_LIMIT = 0.4
WAIT_LIMIT_MINS = 120

# Colours of the shaded "how are we doing?" bands drawn behind the charts
BAND_GOOD = "#5DFDA0"
BAND_WARN = "#FDD049"
BAND_BAD = "#D45E5E"


def util_band_colour(value):
    """Band colour (BAND_GOOD/WARN/BAD) for a utilisation between 0 and 1."""
    low, high = UTIL_IDEAL_RANGE
    if low <= value <= high:
        return BAND_GOOD
    if UTIL_LOW_LIMIT <= value < low:
        return BAND_WARN
    return BAND_BAD


def wait_band_colour(value):
    """Band colour (BAND_GOOD/BAD) for an average wait in minutes."""
    return BAND_GOOD if value < WAIT_LIMIT_MINS else BAND_BAD


def _band_fill(colour, alpha=0.3):
    """``background-color`` CSS for a translucent band colour, for table cells."""
    r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"background-color: rgba({r}, {g}, {b}, {alpha})"

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


def per_run_table(results, metric):
    """
    Per-run table of the utilisation or wait results, for ``st.table``.

    One row per resource or stage, plus patients seen, and one column per run.
    Row names are the plot labels on one line, and values are formatted as
    percentages, minutes (the unit is in the corner header, to keep the
    columns narrow on a phone) or patient counts. Each utilisation or wait
    cell is shaded with the band colour the charts above use for that value.

    Params:
    ------
    results: pandas.DataFrame
        The model's summary results, one row per run (indexed by ``rep``).
    metric: str
        "util" or "wait".

    Returns:
    -------
    pandas.io.formats.style.Styler
    """
    labels = UTIL_LABELS if metric == "util" else WAIT_LABELS
    labels = {col: label.replace("<br>", " ") for col, label in labels.items()}
    table = results[list(labels) + ["09_throughput"]].T
    table.columns = [f"Run {rep}" for rep in table.columns]
    table = table.rename(index={**labels, "09_throughput": "Patients seen"})
    table = table.rename_axis(
        "Utilisation" if metric == "util" else "Average wait (minutes)", axis=0
    )

    stages = list(labels.values())
    band_colour = util_band_colour if metric == "util" else wait_band_colour
    return (
        table.style.format(
            "{:.0%}" if metric == "util" else "{:,.1f}",
            subset=(stages, table.columns),
        )
        .format("{:,.0f}", subset=(["Patients seen"], table.columns))
        .map(
            lambda value: _band_fill(band_colour(value)),
            subset=(stages, table.columns),
        )
    )


def scenario_breakdown_table(all_run_results, scenario_labels):
    """
    Median of every result for each scenario, for the comparison tab.

    One column per scenario and one row per measure, named in plain English
    and grouped as utilisation, waits, time in the department and patients.
    Utilisation and wait cells are shaded with the band colours the charts
    use, as in ``per_run_table``; the other rows have no target, so stay
    uncoloured.

    Params:
    ------
    all_run_results: pandas.DataFrame
        Every scenario's results, one row per run, with a "Model Run" column
        saying which scenario each row belongs to.
    scenario_labels: dict
        Column name for each model run, e.g. {2: "Scenario 2 (Balanced)"}.

    Returns:
    -------
    pandas.io.formats.style.Styler
    """
    results = all_run_results.assign(
        perc_seen=all_run_results["09_throughput"] / all_run_results["00_arrivals"]
    )
    medians = results.groupby("Model Run").median()

    util_rows = {
        col: f"Utilisation: {label.replace('<br>', ' ')}"
        for col, label in UTIL_LABELS.items()
    }
    wait_rows = {
        col: f"Average wait (min): {label.replace('<br>', ' ')}"
        for col, label in WAIT_LABELS.items()
    }
    time_rows = {
        "05_total_time(non-trauma)": "Average time in department (min): non-trauma patients",
        "08_total_time(trauma)": "Average time in department (min): trauma patients",
    }
    count_rows = {
        "00_arrivals": "Patients arriving",
        "09_throughput": "Patients seen",
    }
    perc_rows = {"perc_seen": "Patients seen (% of arrivals)"}

    labels = {**util_rows, **wait_rows, **time_rows, **count_rows, **perc_rows}
    table = medians[list(labels)].T.rename(index=labels).rename_axis("Measure")
    table.columns = [scenario_labels.get(run, f"Scenario {run}") for run in table.columns]

    def rows(group):
        return (list(group.values()), table.columns)

    return (
        table.style.format("{:.0%}", subset=rows(util_rows))
        .format("{:,.1f}", subset=rows({**wait_rows, **time_rows}))
        .format("{:,.0f}", subset=rows(count_rows))
        .format("{:.0%}", subset=rows(perc_rows))
        .map(lambda value: _band_fill(util_band_colour(value)), subset=rows(util_rows))
        .map(lambda value: _band_fill(wait_band_colour(value)), subset=rows(wait_rows))
    )


def scenario_settings_table(all_run_results, scenario_labels, setting_columns):
    """
    The settings each scenario was run with, for the comparison tab.

    Params:
    ------
    all_run_results: pandas.DataFrame
        As for ``scenario_breakdown_table``.
    scenario_labels: dict
        As for ``scenario_breakdown_table``.
    setting_columns: list of str
        The settings columns of ``all_run_results``, in display order. Names may
        contain line breaks, which are shown as spaces. Those starting
        "Probability" are shown as percentages, the rest as whole numbers.

    Returns:
    -------
    pandas.io.formats.style.Styler
    """
    table = all_run_results.groupby("Model Run").first()[setting_columns].T
    table.index = [col.replace("\n", " ") for col in table.index]
    table = table.rename_axis("Setting")
    table.columns = [scenario_labels.get(run, f"Scenario {run}") for run in table.columns]

    probabilities = [row for row in table.index if row.startswith("Probability")]
    counts = [row for row in table.index if row not in probabilities]
    return table.style.format("{:.0%}", subset=(probabilities, table.columns)).format(
        "{:,.0f}", subset=(counts, table.columns)
    )


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
        (UTIL_LOW_LIMIT, low, BAND_WARN),
        (0, UTIL_LOW_LIMIT, BAND_BAD),
    ]:
        add_band(
            **{start: band_start, end: band_end},
            fillcolor=colour,
            opacity=0.25,
            line_width=0,
        )


def add_wait_band(fig, orientation):
    """
    Shade the waits that meet the target (under ``WAIT_LIMIT_MINS``) in green
    and those that miss it in red.

    Call this after the traces are added: the red band runs to a little past
    the largest wait plotted. Plotly's autorange includes shapes, so the band
    fills to the end of the axis without stretching it.

    Params:
    ------
    fig: plotly.graph_objects.Figure
    orientation: str
        "h" for horizontal bands (waits on the y axis), "v" for vertical
        bands (waits on the x axis).
    """
    add_band = fig.add_hrect if orientation == "h" else fig.add_vrect
    start, end = ("y0", "y1") if orientation == "h" else ("x0", "x1")

    axis = "y" if orientation == "h" else "x"
    plotted = [WAIT_LIMIT_MINS]
    for trace in fig.data:
        values = getattr(trace, axis, None)
        if values is not None:
            plotted += [
                float(value)
                for value in values
                if isinstance(value, Number) and value == value  # skip NaN
            ]
    top = 1.1 * max(plotted)

    for band_start, band_end, colour in [
        (0, WAIT_LIMIT_MINS, BAND_GOOD),
        (WAIT_LIMIT_MINS, top, BAND_BAD),
    ]:
        add_band(
            **{start: band_start, end: band_end},
            fillcolor=colour,
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
