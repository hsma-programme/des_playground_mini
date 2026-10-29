"""
A Streamlit application based on the open treatment centre simulation model from Monks.T, Harper.A, Anagnoustou. A, Allen.M, Taylor.S. (2022)

Original Model: https://github.com/TomMonks/treatment-centre-sim/tree/main

Allows users to interact with an increasingly complex treatment simulation
"""

import base64
import gc
import math
import time
import asyncio
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from helper_functions import (
    UTIL_LABELS,
    WAIT_LABELS,
    add_logo,
    add_util_bands,
    add_wait_band,
    describe_results,
    hide_running,
    metric_with_delta,
    render_looping_plotly_animation,
    summarise_results,
)
from model_classes import Scenario, multiple_replications
from vidigi.animation import (
    animate_activity_log,
    add_subplot_panels,
    add_synchronised_trace,
)
from vidigi.analysis import queue_size_over_time
from vidigi.utils import EventPosition, ExitPosition, create_event_position_df

EVERY_X_MINUTES = 10

# Where each step of the patient journey is drawn on the animation. Event names
# must match those logged in model_classes.py; `resource` names the Scenario
# attribute holding the number of rooms for that step.
EVENT_POSITION_DF = create_event_position_df(
    [
        EventPosition(
            event="triage_wait_begins", x=150, y=400, label="Waiting for<br>Triage"
        ),
        EventPosition(
            event="triage_begins",
            x=150,
            y=315,
            resource="n_triage",
            label="Being Triaged",
        ),
        # Minors (non-trauma) pathway
        EventPosition(
            event="MINORS_registration_wait_begins",
            x=290,
            y=140,
            label="Waiting for<br>Registration",
        ),
        EventPosition(
            event="MINORS_registration_begins",
            x=290,
            y=80,
            resource="n_reg",
            label="Being<br>Registered",
        ),
        EventPosition(
            event="MINORS_examination_wait_begins",
            x=460,
            y=140,
            label="Waiting for<br>Examination",
        ),
        EventPosition(
            event="MINORS_examination_begins",
            x=460,
            y=80,
            resource="n_exam",
            label="Being<br>Examined",
        ),
        EventPosition(
            event="MINORS_treatment_wait_begins",
            x=625,
            y=140,
            label="Waiting for<br>Treatment",
        ),
        EventPosition(
            event="MINORS_treatment_begins",
            x=625,
            y=80,
            resource="n_cubicles_1",
            label="Being<br>Treated",
        ),
        # Trauma pathway
        EventPosition(
            event="TRAUMA_stabilisation_wait_begins",
            x=295,
            y=540,
            label="Waiting for<br>Stabilisation",
        ),
        EventPosition(
            event="TRAUMA_stabilisation_begins",
            x=295,
            y=485,
            resource="n_trauma",
            label="Being<br>Stabilised",
        ),
        EventPosition(
            event="TRAUMA_treatment_wait_begins",
            x=620,
            y=540,
            label="Waiting for<br>Treatment",
        ),
        EventPosition(
            event="TRAUMA_treatment_begins",
            x=630,
            y=485,
            resource="n_cubicles_2",
            label="Being<br>Treated",
        ),
        ExitPosition(x=670, y=330),
    ]
)

st.set_page_config(
    page_title="Simulation Playground",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialise session state
if "session_results" not in st.session_state:
    st.session_state["session_results"] = []

# Fewest rooms used so far in a run where every metric was in the green
if "best_rooms" not in st.session_state:
    st.session_state["best_rooms"] = None

# Starting values for the sidebar sliders (set once, so presets can overwrite them)
SLIDER_DEFAULTS = dict(
    n_triage=4,
    prob_trauma=0.3,
    n_trauma=6,
    n_cubicles_2=6,
    n_reg=3,
    n_exam=3,
    n_cubicles_1=3,
    non_trauma_treat_p=0.7,
)
for slider_key, slider_value in SLIDER_DEFAULTS.items():
    st.session_state.setdefault(slider_key, slider_value)

# Largest value each room slider can take
SLIDER_MAX = dict(
    n_triage=8,
    n_trauma=11,
    n_cubicles_2=11,
    n_reg=10,
    n_exam=10,
    n_cubicles_1=10,
)

# Slider values for the one-click presets. The keys are the sidebar slider keys.
PRESETS = {
    "🏥 Current setup": dict(SLIDER_DEFAULTS),
    "😰 Understaffed": dict(
        n_triage=1,
        n_reg=2,
        n_exam=2,
        n_trauma=2,
        n_cubicles_1=1,
        n_cubicles_2=2,
        prob_trauma=0.3,
        non_trauma_treat_p=0.7,
    ),
    "⚖️ Balanced": dict(
        n_triage=2,
        n_reg=2,
        n_exam=3,
        n_trauma=8,
        n_cubicles_1=2,
        n_cubicles_2=4,
        prob_trauma=0.3,
        non_trauma_treat_p=0.7,
    ),
    "💸 Throw money at it": dict(
        **SLIDER_MAX,
        prob_trauma=0.3,
        non_trauma_treat_p=0.7,
    ),
}


def preset_total_rooms(name):
    """Total rooms across all room sliders (the SLIDER_MAX keys) for a preset."""
    return sum(PRESETS[name][slider_key] for slider_key in SLIDER_MAX)


def apply_preset(name):
    """Button callback: set the sidebar sliders, then ask for a run."""
    for slider_key, slider_value in PRESETS[name].items():
        st.session_state[slider_key] = slider_value
    st.session_state["run_requested"] = True


# Result columns that record each slider, so a run can be matched to a preset
PARAM_COLUMNS = {
    "Triage\nCubicles": "n_triage",
    "Registration\nCubicles": "n_reg",
    "Examination\nRooms": "n_exam",
    "Non-Trauma\nTreatment Cubicles": "n_cubicles_1",
    "Trauma\nStabilisation Bays": "n_trauma",
    "Trauma\nTreatment Cubicles": "n_cubicles_2",
    "Probability patient\nis a trauma patient": "prob_trauma",
    "Probability non-trauma patients\nrequire treatment": "non_trauma_treat_p",
}


def matching_preset(run_params):
    """Name of the preset (without its emoji) matching these slider values, else None."""
    for preset_name, preset_values in PRESETS.items():
        if all(
            math.isclose(run_params[key], value, abs_tol=1e-9)
            for key, value in preset_values.items()
        ):
            # Drop the emoji prefix from the preset button name
            return preset_name.split(" ", 1)[1]
    return None


def scenario_label(run_number, params_row):
    """E.g. 'Scenario 2 (Balanced)', or 'Scenario 2 (Custom)' if no preset matches."""
    run_params = {key: params_row[col] for col, key in PARAM_COLUMNS.items()}
    return f"Scenario {run_number} ({matching_preset(run_params) or 'Custom'})"


SETTING_COLUMNS = list(PARAM_COLUMNS) + [
    "Random Seed",
    "Run Length\n(days)",
    "Replications",
]


def same_settings(row_a, row_b):
    """True if two runs used identical sliders, seed, run length and replications."""
    return all(
        math.isclose(row_a[col], row_b[col], abs_tol=1e-9) for col in SETTING_COLUMNS
    )


@st.cache_resource(max_entries=5, show_spinner=False)
def run_simulation(
    seed,
    n_triage,
    n_reg,
    n_exam,
    n_trauma,
    n_cubicles_1,
    n_cubicles_2,
    non_trauma_treat_p,
    prob_trauma,
    n_reps,
    run_time_days,
):
    """Run the model, returning the summary and the first replication's event log.

    Cached on the settings, so asking for the same run again doesn't repeat it.
    """
    # Only reached on a cache miss, so the caller can tell a fresh run from a cached one
    st.session_state["sim_was_run"] = True
    scenario = Scenario(
        random_number_set=seed,
        n_triage=n_triage,
        n_reg=n_reg,
        n_exam=n_exam,
        n_trauma=n_trauma,
        n_cubicles_1=n_cubicles_1,
        n_cubicles_2=n_cubicles_2,
        non_trauma_treat_p=non_trauma_treat_p,
        prob_trauma=prob_trauma,
    )
    detailed_outputs = multiple_replications(
        scenario, n_reps=n_reps, rc_period=run_time_days * 60 * 24, summary=False
    )
    event_log = detailed_outputs["trial_log"].to_dataframe()
    # run_number starts at 0, so this is the first replication
    return detailed_outputs["summary_df"], event_log[event_log["run_number"] == 0]


def clear_scenarios():
    """Button callback: forget the scenarios run so far (and the best score)."""
    st.session_state["session_results"] = []
    st.session_state["best_rooms"] = None


def challenge_message(total_rooms):
    message = (
        "🏆 **Your challenge:** get every utilisation and wait metric into the "
        "green, using as few rooms as you can."
    )
    if st.session_state["best_rooms"] is not None:
        message += f" Best so far: **{st.session_state['best_rooms']} rooms**."
    message += f"\n\nTotal rooms in use in your scenario: **{total_rooms}**"
    return message


add_logo()

hide_running()

with open("style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

# HSMA display font for the sidebar title. Embedded as base64 so it loads
# without needing static file serving.
with open("resources/fonts/hsma-display/HSMADisplay-Regular.woff2", "rb") as font:
    font_b64 = base64.b64encode(font.read()).decode()
st.markdown(
    f"""<style>
    @font-face {{
        font-family: "HSMA Display";
        src: url(data:font/woff2;base64,{font_b64}) format("woff2");
    }}
    </style>""",
    unsafe_allow_html=True,
)


gc.collect()

tab1, tab2 = st.tabs(["Simulate", "Compare Scenario Outputs"])

with st.sidebar:
    # NIHR logo, directly under the HSMA logo in the sidebar header
    st.image(
        "resources/NIHR_APPLIED_RESEARCH_COLLABORATION_Logo_Horizontal_RGB_WHITE.png",
        width="stretch",
    )

    # A user must press a streamlit button (or a preset) to run the model
    run_requested = st.session_state.pop("run_requested", False)
    button_run_pressed = (
        st.button(
            "Click to run the simulation",
            key="animate_button",
            width="stretch",
        )
        or run_requested
    )

    st.subheader("Triage")
    n_triage = st.slider(
        "🚦 Number of Triage Cubicles",
        1,
        SLIDER_MAX["n_triage"],
        step=1,
        key="n_triage",
    )

    st.subheader("Trauma Pathway")
    n_trauma = st.slider(
        "🛏️ Number of Trauma Bays for Stabilisation",
        1,
        SLIDER_MAX["n_trauma"],
        step=1,
        key="n_trauma",
    )
    n_cubicles_2 = st.slider(
        "🤕 Trauma Treatment Cubicles",
        1,
        SLIDER_MAX["n_cubicles_2"],
        step=1,
        key="n_cubicles_2",
    )

    st.subheader("Non-Trauma Pathway")
    n_reg = st.slider(
        "📝 Number of Registration Cubicles",
        1,
        SLIDER_MAX["n_reg"],
        step=1,
        key="n_reg",
    )
    n_exam = st.slider(
        "🔎 Number of Examination Rooms for non-trauma patients",
        1,
        SLIDER_MAX["n_exam"],
        step=1,
        key="n_exam",
    )
    n_cubicles_1 = st.slider(
        "💊 Non-Trauma Treatment Cubicles",
        1,
        SLIDER_MAX["n_cubicles_1"],
        step=1,
        key="n_cubicles_1",
    )

    st.divider()

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

    st.subheader("Patient Mix")
    prob_trauma = st.slider(
        "🚑 Probability that a new arrival is a trauma patient",
        0.0,
        1.0,
        step=0.01,
        help="""0 = No arrivals are trauma patients\n\n1 = All arrivals are trauma patients""",
        key="prob_trauma",
    )

    non_trauma_treat_p = st.slider(
        "🤒 Probability that a non-trauma patient will need treatment",
        0.0,
        1.0,
        step=0.01,
        help="""0 = No non-trauma patients need treatment\n\n1 = All non-trauma patients need treatment""",
        key="non_trauma_treat_p",
    )

    total_rooms = n_cubicles_1 + n_cubicles_2 + n_exam + n_trauma + n_triage + n_reg

    with st.expander("Advanced Parameters"):
        seed = st.slider(
            "🎲 Set a random number for the computer to start from",
            1,
            1000,
            step=1,
            value=42,
            help=(
                "Computers make 'random' numbers by following a recipe that starts "
                "from a number called a seed. The same seed gives exactly the same "
                "results every time - change it to see a different roll of the dice."
            ),
        )

        n_reps = st.slider(
            "🔁 How many times should the simulation run?",
            1,
            10,
            step=1,
            value=5,
            help=(
                "Patients arrive at random, so every run turns out a little "
                "different. Running the simulation several times shows how much of "
                "what you see is just chance. The animation only shows the first run."
            ),
        )

        run_time_days = st.slider(
            "🗓️ How many days should we run the simulation for each time?",
            1,
            30,
            step=1,
            value=4,
            help="How long each run lasts. Longer runs give steadier results but take longer to compute.",
        )

with tab1:
    args = Scenario(
        random_number_set=seed,
        n_triage=n_triage,
        n_reg=n_reg,
        n_exam=n_exam,
        n_trauma=n_trauma,
        n_cubicles_1=n_cubicles_1,
        n_cubicles_2=n_cubicles_2,
        non_trauma_treat_p=non_trauma_treat_p,
        prob_trauma=prob_trauma,
    )

    st.markdown(
        f"""
        This is a virtual emergency department, and **you're in charge of staffing it**.

        Choose how many rooms of each type to open in the sidebar, hit run, and watch
        {run_time_days} days in the ED pass in a few minutes.

        This uses *discrete event simulation* - a technique that allows us to
        <span style="color:#ffe600;font-weight:700">safely try out ideas on a computer before testing them on real patients</span>.
        The simulation is repeated {n_reps} times to see how performance might vary in reality.
        """,
        unsafe_allow_html=True,
    )

    challenge_box = st.empty()

    st.caption(
        "Not sure where to start? Try a preset - it sets the sliders and runs the simulation for you."
    )
    # Understaffed and Balanced are slightly narrower to leave room for the longer last label
    preset_cols = st.columns([1, 0.9, 0.9, 1.2])
    for preset_col, preset_name in zip(preset_cols, PRESETS):
        preset_col.button(
            f"{preset_name} ({preset_total_rooms(preset_name)} rooms)",
            key=f"preset_{preset_name}",
            on_click=apply_preset,
            args=(preset_name,),
            width="stretch",
        )

    if button_run_pressed:
        # Progress card shown in a full-screen overlay (styled in style.css) until
        # the animation has been built; cleared with loading_box.empty() below
        loading_box = st.empty()
        with (
            loading_box.container(key="loading_overlay"),
            st.container(key="loading_card"),
        ):
            st.markdown(
                '<div class="loading-spinner"></div><p class="loading-title">Running your scenario</p>',
                unsafe_allow_html=True,
            )
            my_bar = st.progress(0, text="Simulating the emergency department...")

        # run multiple replications of experment
        st.session_state["sim_was_run"] = False
        sim_start = time.perf_counter()
        # Identical settings are served from the cache rather than rerun
        results, single_log = run_simulation(
            seed=seed,
            n_triage=n_triage,
            n_reg=n_reg,
            n_exam=n_exam,
            n_trauma=n_trauma,
            n_cubicles_1=n_cubicles_1,
            n_cubicles_2=n_cubicles_2,
            non_trauma_treat_p=non_trauma_treat_p,
            prob_trauma=prob_trauma,
            n_reps=n_reps,
            run_time_days=run_time_days,
        )
        results = results.copy()
        sim_seconds = time.perf_counter() - sim_start

        my_bar.progress(40, text="Collating Simulation Outputs...")

        my_bar.progress(60, text="Logging Results...")

        # print(len(st.session_state['session_results']))
        # results_for_state = pd.DataFrame(results.median()).T.drop(['Rep'], axis=1)
        results_for_state = results
        original_cols = results_for_state.columns.values
        results_for_state["Triage\nCubicles"] = args.n_triage
        results_for_state["Registration\nCubicles"] = args.n_reg
        results_for_state["Examination\nRooms"] = args.n_exam
        results_for_state["Non-Trauma\nTreatment Cubicles"] = args.n_cubicles_1
        results_for_state["Trauma\nStabilisation Bays"] = args.n_trauma
        results_for_state["Trauma\nTreatment Cubicles"] = args.n_cubicles_2
        results_for_state["Probability patient\nis a trauma patient"] = args.prob_trauma
        results_for_state["Probability non-trauma patients\nrequire treatment"] = (
            args.non_trauma_treat_p
        )
        results_for_state["Model Run"] = len(st.session_state["session_results"]) + 1
        results_for_state["Random Seed"] = seed
        results_for_state["Run Length\n(days)"] = run_time_days
        results_for_state["Replications"] = n_reps

        # Reorder columns
        column_order = [
            "Model Run",
            "Triage\nCubicles",
            "Registration\nCubicles",
            "Examination\nRooms",
            "Non-Trauma\nTreatment Cubicles",
            "Trauma\nStabilisation Bays",
            "Trauma\nTreatment Cubicles",
            "Probability patient\nis a trauma patient",
            "Probability non-trauma patients\nrequire treatment",
            "Random Seed",
            "Run Length\n(days)",
            "Replications",
        ] + list(original_cols)

        results_for_state = results_for_state[column_order]

        current_state = st.session_state["session_results"]

        previous_summary = (
            summarise_results(current_state[-1]) if current_state else None
        )

        duplicate_of = (
            next(
                (
                    run
                    for run, rows in pd.concat(current_state).groupby("Model Run")
                    if same_settings(rows.iloc[0], results_for_state.iloc[0])
                ),
                None,
            )
            if current_state
            else None
        )

        # Identical settings would only add a duplicate column to the comparison
        if duplicate_of is None:
            current_state.append(results_for_state)

        del results_for_state
        gc.collect()

        st.session_state["session_results"] = current_state

        del current_state
        gc.collect()

        my_bar.progress(70, text="Creating animation frames...")

        gc.collect()

        if duplicate_of is not None:
            st.toast(
                f"These settings match Scenario {duplicate_of}, "
                "so nothing new was added to the scenario comparison tab.",
                icon="♻️",
                duration=3,
            )

        summary = summarise_results(results)

        def previous_value(key):
            return previous_summary[key] if previous_summary else None

        st.divider()

        # Recap of the choice that was run, and whether it was a preset
        chosen_preset = matching_preset(
            {key: st.session_state[key] for key in SLIDER_DEFAULTS}
        )
        st.markdown(
            f"**Run type:** {f'Preset - {chosen_preset}' if chosen_preset else 'Custom'}"
        )
        room_counts = {
            "🚦 Triage": n_triage,
            "📝 Registration": n_reg,
            "🔎 Examination": n_exam,
            "💊 Non-trauma treatment": n_cubicles_1,
            "🛏️ Trauma stabilisation": n_trauma,
            "🤕 Trauma treatment": n_cubicles_2,
        }
        for room_col, (room_label, room_count) in zip(
            st.columns(len(room_counts)), room_counts.items()
        ):
            with room_col.container(
                border=True, height=100, key=f"room_card_{room_label}"
            ):
                st.markdown(
                    f'<div class="room-label">{room_label}</div>'
                    f'<div class="room-count">{room_count}</div>',
                    unsafe_allow_html=True,
                )

        col_seen, col_util, col_wait, col_longest = st.columns(4)

        metric_with_delta(
            col_seen,
            ":hospital: **Patients seen**",
            f"{summary['patients_seen']:,.0f}",
            summary["patients_seen"],
            previous_value("patients_seen"),
            help="Average number of patients who got through the whole process in each run.",
        )
        metric_with_delta(
            col_util,
            ":bed: **Utilisation in ideal range**",
            f"{summary['util_in_range']} of {summary['n_util']}",
            summary["util_in_range"],
            previous_value("util_in_range"),
            help="How many resources were busy 65% to 85% of the time, on average.",
        )
        metric_with_delta(
            col_wait,
            ":clock2: **Waits under 2 hours**",
            f"{summary['wait_in_range']} of {summary['n_wait']}",
            summary["wait_in_range"],
            previous_value("wait_in_range"),
            help="How many stages kept the average wait under 120 minutes.",
        )
        metric_with_delta(
            col_longest,
            ":stopwatch: **Longest average wait**",
            f"{summary['longest_wait']:,.0f} min",
            summary["longest_wait"],
            previous_value("longest_wait"),
            unit=" min",
            inverse=True,
            help="The worst average wait at any stage of the process.",
        )

        run_word = "run" if n_reps == 1 else "runs"
        timing = (
            f" in {sim_seconds:.1f} seconds" if st.session_state["sim_was_run"] else ""
        )
        st.caption(
            f"Simulated {n_reps * run_time_days} days of emergency department activity "
            f"({n_reps} {run_word} of {run_time_days} days; "
            f"{summary['arrivals']:,} patient arrivals){timing}."
        )

        st.markdown(
            describe_results(
                results,
                room_counts={
                    "n_triage": n_triage,
                    "n_reg": n_reg,
                    "n_exam": n_exam,
                    "n_cubicles_1": n_cubicles_1,
                    "n_trauma": n_trauma,
                    "n_cubicles_2": n_cubicles_2,
                },
            ),
            unsafe_allow_html=True,
        )

        n_in_range = summary["util_in_range"] + summary["wait_in_range"]
        n_metrics = summary["n_util"] + summary["n_wait"]

        if n_in_range == n_metrics:
            st.balloons()
            best_rooms = st.session_state["best_rooms"]
            if best_rooms is None or total_rooms < best_rooms:
                st.session_state["best_rooms"] = total_rooms
                st.success(
                    f"🎉 Everything is in the green with {total_rooms} rooms - a new best!"
                )
            else:
                st.success(
                    f"Everything is in the green with {total_rooms} rooms. "
                    f"Your best is {best_rooms} - can you do it with fewer?"
                )

        with st.container():
            st.markdown(
                f"""
    The plot below shows a snapshot every {EVERY_X_MINUTES} minutes of the position of everyone in our emergency department model.
    """
            )

            animated_plot = animate_activity_log(
                event_log=single_log,
                event_position_df=EVENT_POSITION_DF,
                scenario=args,
                every_x_time_units=EVERY_X_MINUTES,
                limit_duration=min(run_time_days * 60 * 24, 60 * 24 * 5),
                step_snapshot_max=30,
                wrap_queues_at=10,
                gap_between_entities=10,
                gap_between_queue_rows=22,
                include_play_button=True,
                plotly_height=725,
                plotly_width=1150,
                override_x_max=700,
                override_y_max=675,
                entity_icon_size=14,
                # vidigi 2.0.0 sizes the bay markers by this (default 24); they
                # were a fixed 15 before
                resource_icon_size=12,
                display_stage_labels=False,
                setup_mode=False,
                time_display_units="dhm",
                add_background_image="https://raw.githubusercontent.com/hsma-programme/des_playground_mini/main/resources/Full%20Model%20Background%20Image%20-%20Hospital%20Layout.png",
            )

            my_bar.progress(80, text="Calculating queue lengths...")

            # Add a line chart of queue lengths beneath the animation, revealed in
            # step with the animation frames
            queue_events = {
                "triage_wait_begins": ("Triage", "#74c476"),
                "MINORS_registration_wait_begins": ("Registration", "#c6dbef"),
                "MINORS_examination_wait_begins": ("Examination", "#4eb3d3"),
                "MINORS_treatment_wait_begins": ("Non-trauma treatment", "#08519c"),
                "TRAUMA_stabilisation_wait_begins": ("Stabilisation", "#fcae91"),
                "TRAUMA_treatment_wait_begins": ("Trauma treatment", "#ef3b2c"),
            }

            # Sample hourly rather than every frame - each frame carries the whole
            # line revealed so far, so 5-minute samples would bloat the figure
            queue_sizes = queue_size_over_time(
                single_log,
                event_list=list(queue_events),
                limit_duration=60 * 24 * 5,
                every_x_time_units=60,
            ).pivot(index="snapshot_time", columns="event", values="count")

            # One frame per snapshot, starting at time 0
            frame_times = np.arange(len(animated_plot.frames)) * EVERY_X_MINUTES

            # Traces are returned as plain dicts rather than go.Scatter - plotly
            # validates them when they are attached to each frame anyway, and
            # building ~8,600 validated go.Scatter objects first is slow
            def queue_traces(frame_name, frame_index):
                current_time = frame_times[frame_index]
                revealed = queue_sizes[queue_sizes.index <= current_time]
                # Extend each line to the current frame time, holding the last
                # hourly value, so the line moves on every frame
                x = np.append(revealed.index.values, current_time) / (60 * 24)
                return [
                    dict(
                        type="scatter",
                        x=x,
                        y=np.append(revealed[event].values, revealed[event].iloc[-1]),
                        mode="lines",
                        line=dict(color=colour, shape="hv", width=2),
                        name=label,
                        showlegend=True,
                        hovertemplate="%{y} waiting<extra>" + label + "</extra>",
                        xaxis="x2",
                        yaxis="y2",
                    )
                    for event, (label, colour) in queue_events.items()
                ]

            my_bar.progress(85, text="Adding the queue chart panel...")

            animated_plot = add_subplot_panels(
                animated_plot,
                row_heights=[0.82, 0.18],
                hide_new_panel_axes=False,
            )

            # Keep vidigi's own traces out of the legend, which is switched on
            # below for the queue lines
            animated_plot.update_traces(showlegend=False)

            my_bar.progress(90, text="Syncing the queue chart to every frame...")

            animated_plot = add_synchronised_trace(animated_plot, queue_traces)

            my_bar.progress(95, text="Tidying up the charts...")

            # Ticks every 6 hours: day numbers at midnight, times of day between
            tick_labels = ["6am", "12pm", "6pm"]
            # The animation covers at most the first 5 days
            anim_days = min(run_time_days, 5)
            ticks = [
                (
                    d + h / 24,
                    ("" if d == anim_days else str(d + 1))
                    if h == 0
                    else tick_labels[h // 6 - 1],
                )
                for d in range(anim_days + 1)
                for h in (0, 6, 12, 18)
            ][:-3]
            animated_plot.update_xaxes(
                range=[0, anim_days],
                tickmode="array",
                tickvals=[t for t, _ in ticks],
                ticktext=[label for _, label in ticks],
                tickangle=0,
                tickfont=dict(size=10),
                row=2,
                col=1,
            )
            animated_plot.update_yaxes(
                range=[0, queue_sizes.values.max() + 1],
                title_text="Patients waiting",
                title_standoff=12,
                ticks="outside",
                showticklabels=True,
                showgrid=True,
                gridcolor="rgba(128,128,128,0.25)",
                nticks=4,
                tickformat="d",
                automargin=True,
                tickfont=dict(size=10),
                row=2,
                col=1,
            )
            animated_plot.update_layout(
                showlegend=True,
                legend=dict(
                    title_text="Patients waiting for:",
                    orientation="h",
                    x=0,
                    y=0.20,
                    xanchor="left",
                    yanchor="bottom",
                ),
                # Pull the play button and slider up closer to the queue chart
                sliders=[dict(pad=dict(t=16))],
                updatemenus=[dict(pad=dict(t=16))],
            )

            del queue_sizes
            gc.collect()

            my_bar.progress(98, text="Sending the animation to your browser...")

            render_looping_plotly_animation(animated_plot, text_color="white")

            my_bar.progress(100, text="Done")
            loading_box.empty()

            st.caption("""
                The chart beneath the animation shows how many patients are waiting in each queue, building up as the animation plays.
                The animation starts playing automatically and loops continuously, pausing briefly on the final frame before restarting.
                The buttons to the left of the slider below the plot can be used to pause and restart the animation.
                Clicking on the bar below the plot and dragging your cursor to the left or right allows you to rapidly jump through to a different time in the simulation.
                Only the first replication of the simulation is shown.
                """)

            # st.download_button(
            #     label="Download Plot as HTML",
            #     data=animated_plot.to_html(full_html=False, include_plotlyjs="cdn"),
            #     file_name="plot.html",
            #     mime="text/html",
            # )

        tab_playground_results_2, tab_playground_results_3 = st.tabs(
            ["Simple Graphs", "Advanced Graphs"]
        )

        with tab_playground_results_2:
            col_res_a, col_res_b = st.columns([1, 1])

            with col_res_a:
                # util_fig_simple = px.bar(results.mean().filter(like="util"), opacity=0.5)
                st.markdown(
                    """
                    The emergency department wants to aim for an average of 65% to 85% utilisation across all resources in the emergency department.

                    The green box shows this ideal range. If the bars overlap with the green box, utilisation is ideal.

                    If utilisation is below this, you might want to **reduce** the number of those resources available.

                    If utilisation is above this point, you may want to **increase** the number of that type of resource available.
                    """
                )
                util_fig_simple = go.Figure()
                add_util_bands(util_fig_simple, "h")

                util_fig_simple.add_bar(
                    x=results.mean().filter(like="util").index.tolist(),
                    y=results.mean().filter(like="util").tolist(),
                )

                util_fig_simple.update_layout(
                    yaxis_tickformat=".0%",
                    title=dict(
                        text="Utilisation of Resources - Average Across Simulation Runs",
                        automargin=True,
                        yref="paper",
                    ),
                )
                util_fig_simple.update_yaxes(
                    title_text="Resource Utilisation (%)", range=[-0.05, 1.1]
                )
                # util_fig_simple.data = util_fig_simple.data[::-1]
                util_fig_simple.update_xaxes(
                    labelalias=UTIL_LABELS,
                    tickangle=0,
                )
                st.plotly_chart(util_fig_simple, width="stretch")

            with col_res_b:
                st.markdown(
                    """
                    The emergency department wants to ensure people wait no longer than 2 hours (120 minutes) at any point in the process.

                    This needs to be balanced with the utilisation graphs on the left.

                    The green box shows waits of less than two hours. If the bars fall within this range, the number of resources does not need to be changed.
                    """
                )

                wait_fig_simple = go.Figure()
                add_wait_band(wait_fig_simple, "h")

                wait_fig_simple.add_bar(
                    x=results.mean().filter(like="wait").index.tolist(),
                    y=results.mean().filter(like="wait").tolist(),
                )

                wait_fig_simple.update_xaxes(
                    labelalias=WAIT_LABELS,
                    tickangle=0,
                )
                # wait_fig_simple.data = wait_fig_simple.data[::-1]
                wait_fig_simple.update_yaxes(
                    title_text="Wait for Treatment Stage<br>(Minutes)"
                )

                wait_fig_simple.update_layout(
                    title=dict(
                        text="Waits at Each Step - Average Across Simulation Runs",
                        automargin=True,
                        yref="paper",
                    )
                )

                st.plotly_chart(wait_fig_simple, width="stretch")

        with tab_playground_results_3:
            st.markdown("""
                        We can use box plots to explore the effect of the random variation within each model run.

                        This can give us a better idea of how robust the system is.

                        Each dot indicates a single model run. The number of runs can be increased under the advanced options.
                        """)

            col_res_1, col_res_2 = st.columns(2)

            with col_res_1:
                st.subheader("Average Utilisation")

                st.markdown(
                    """
                    The emergency department wants to aim for an average of 65% to 85% utilisation across all resources in the emergency department.

                    The green box shows this ideal range. If the bars overlap with the green box, utilisation is ideal.

                    If utilisation is below this, you might want to **reduce** the number of those resources available.

                    If utilisation is above this point, you may want to **increase** the number of that type of resource available.
                    """
                )

                utilisation_boxplot = px.box(
                    results.reset_index()
                    .melt(id_vars="rep")
                    .set_index("variable")
                    .filter(like="util", axis=0)
                    .reset_index(),
                    y="variable",
                    x="value",
                    points="all",
                    range_x=[0, 1],
                )

                add_util_bands(utilisation_boxplot, "v")

                utilisation_boxplot.update_yaxes(
                    labelalias=UTIL_LABELS,
                    tickangle=0,
                    title_text="",
                )

                utilisation_boxplot.update_xaxes(
                    title_text="Resource Utilisation (%)", range=[-0.05, 1.1]
                )

                utilisation_boxplot.update_layout(xaxis_tickformat=".0%")

                st.plotly_chart(utilisation_boxplot, width="stretch")

                st.write(
                    results.filter(like="util", axis=1)
                    .merge(
                        results.filter(like="throughput", axis=1),
                        left_index=True,
                        right_index=True,
                    )
                    .T.rename_axis("Metric", axis=0)
                )

            with col_res_2:
                st.subheader("Average Waits")

                st.markdown(
                    """
                    The emergency department wants to ensure people wait no longer than 2 hours (120 minutes) at any point in the process.

                    This needs to be balanced with the utilisation graphs on the left.

                    The green box shows waits of less than two hours. If the bars fall within this range, the number of resources does not need to be changed.
                    """
                )

                wait_boxplot = px.box(
                    results.reset_index()
                    .melt(id_vars="rep")
                    .set_index("variable")
                    .filter(like="wait", axis=0)
                    .reset_index(),
                    y="variable",
                    x="value",
                    points="all",
                )

                wait_boxplot.update_yaxes(
                    labelalias=WAIT_LABELS,
                    tickangle=0,
                    title_text="",
                )

                add_wait_band(wait_boxplot, "v")

                wait_boxplot.update_xaxes(
                    title_text="Wait for Treatment Stage (Minutes)"
                )

                # Add in a box plot showing waits
                st.plotly_chart(wait_boxplot, width="stretch")

                st.write(
                    results.filter(like="wait", axis=1)
                    .merge(
                        results.filter(like="throughput", axis=1),
                        left_index=True,
                        right_index=True,
                    )
                    .T.rename_axis("Metric", axis=0)
                )

    challenge_box.info(challenge_message(total_rooms))

#################################################
# Create area for exploring all session results
#################################################
with tab2:
    if len(st.session_state["session_results"]) > 0:
        all_run_results = pd.concat(st.session_state["session_results"])

        # "Scenario 2 (Balanced)" / "Scenario 3 (Custom)" for each model run
        scenario_labels = {
            run: scenario_label(run, rows.iloc[0])
            for run, rows in all_run_results.groupby("Model Run")
        }
        scenario_order = list(scenario_labels.values())

        st.button("Clear scenarios", key="clear_scenarios", on_click=clear_scenarios)

        st.subheader("Look at Average Results Across Replications")
        # col_a, col_b = st.columns(2)

        # with col_a:
        parameter_scenario_df = (
            all_run_results.groupby("Model Run").median().T.reset_index(drop=False)
        )
        parameter_scenario_df.columns = [
            scenario_labels.get(i, f"Scenario {i}")
            for i in parameter_scenario_df.columns
        ]
        parameter_scenario_df = parameter_scenario_df[
            ~parameter_scenario_df["Scenario index"].str.contains(r"\d", regex=True)
        ]

        st.dataframe(
            parameter_scenario_df.set_index(
                parameter_scenario_df.columns[0]
            ).rename_axis("Parameter", axis=0),
            hide_index=False,
            width="stretch",
        )
        del parameter_scenario_df

        scenario_tab_1, scenario_tab_2, scenario_tab_3 = st.tabs(
            ["Simple Metrics", "Advanced Metrics", "Detailed Breakdown"]
        )

        with scenario_tab_1:
            #             st.write(
            # all_run_results.groupby('Model Run').median().T.reset_index(drop=False).melt(id_vars="index", var_name="model_run"),                    x="variable",
            #             )
            col_x, col_y = st.columns(2)

            with col_x:
                st.subheader("Utilisation")

                all_run_util_bar = px.bar(
                    all_run_results.groupby("Model Run")
                    .median()
                    .T.filter(like="util", axis=0)
                    .reset_index(drop=False)
                    .melt(id_vars="index", var_name="model_run")
                    .assign(model_run=lambda d: d["model_run"].map(scenario_labels)),
                    x="value",
                    y="index",
                    barmode="group",
                    color="model_run",
                    category_orders={"model_run": scenario_order},
                    range_x=[0, 1],
                    height=800,
                )

                add_util_bands(all_run_util_bar, "v")

                all_run_util_bar.update_yaxes(
                    labelalias=UTIL_LABELS,
                    autorange="reversed",
                    tickangle=0,
                    title_text="",
                )
                all_run_util_bar.update_xaxes(title_text="Resource Utilisation (%)")

                all_run_util_bar.update_layout(
                    xaxis_tickformat=".0%", legend_title_text="Scenario"
                )

                st.plotly_chart(all_run_util_bar, width="stretch")

            with col_y:
                st.subheader("Waits")

                all_run_wait_bar = px.bar(
                    all_run_results.groupby("Model Run")
                    .median()
                    .T.filter(like="wait", axis=0)
                    .reset_index(drop=False)
                    .melt(id_vars="index", var_name="model_run")
                    .assign(model_run=lambda d: d["model_run"].map(scenario_labels)),
                    x="value",
                    y="index",
                    barmode="group",
                    color="model_run",
                    category_orders={"model_run": scenario_order},
                    height=800,
                )

                all_run_wait_bar.update_yaxes(
                    labelalias=WAIT_LABELS,
                    autorange="reversed",
                    tickangle=0,
                    title_text="",
                )

                all_run_wait_bar.update_xaxes(title_text="Wait for Stage (minutes)")

                all_run_wait_bar.update_layout(legend_title_text="Scenario")

                add_wait_band(all_run_wait_bar, "v")

                st.plotly_chart(all_run_wait_bar, width="stretch")

        # Repeat but with boxplots instead so variability within model runs can be
        # better explored
        with scenario_tab_2:
            col_res_1, col_res_2 = st.columns(2)

            with col_res_1:
                st.subheader("Utilisation")

                all_run_util_box = px.box(
                    all_run_results.reset_index()
                    .melt(id_vars=["Model Run", "rep"])
                    .set_index("variable")
                    .filter(like="util", axis=0)
                    .reset_index()
                    .assign(Scenario=lambda d: d["Model Run"].map(scenario_labels)),
                    y="variable",
                    x="value",
                    color="Scenario",
                    category_orders={"Scenario": scenario_order},
                    points="all",
                    range_x=[0, 1],
                    height=800,
                )

                add_util_bands(all_run_util_box, "v")

                all_run_util_box.update_yaxes(
                    labelalias=UTIL_LABELS,
                    autorange="reversed",
                    tickangle=0,
                    title_text="",
                )
                all_run_util_box.update_xaxes(title_text="Resource Utilisation (%)")

                all_run_util_box.update_layout(
                    xaxis_tickformat=".0%", legend_title_text="Scenario"
                )

                st.plotly_chart(all_run_util_box, width="stretch")

                # st.write(all_run_results.filter(like="util", axis=1).merge(all_run_results.filter(like="throughput", axis=1),left_index=True,right_index=True))

            with col_res_2:
                st.subheader("Waits")

                all_run_wait_box = px.box(
                    all_run_results.reset_index()
                    .melt(id_vars=["Model Run", "rep"])
                    .set_index("variable")
                    .filter(like="wait", axis=0)
                    .reset_index()
                    .assign(Scenario=lambda d: d["Model Run"].map(scenario_labels)),
                    y="variable",
                    x="value",
                    color="Scenario",
                    category_orders={"Scenario": scenario_order},
                    points="all",
                    height=800,
                )

                all_run_wait_box.update_yaxes(
                    labelalias=WAIT_LABELS,
                    autorange="reversed",
                    tickangle=0,
                    title_text="",
                )
                all_run_wait_box.update_xaxes(title_text="Wait for Stage (minutes)")

                add_wait_band(all_run_wait_box, "v")

                all_run_wait_box.update_layout(legend_title_text="Scenario")

                # Add in a box plot showing waits
                st.plotly_chart(all_run_wait_box, width="stretch")

            col_res_3, col_res_4 = st.columns(2)

            with col_res_3:
                st.subheader("Throughput")
                st.markdown(
                    """
                    This is the percentage of clients who entered the system
                    who had left by the time the model stopped running.
                    Higher values are better - low values suggest a big backlog of people getting stuck in the system
                    for a long time.
                    """
                )
                all_run_results["perc_throughput"] = (
                    all_run_results["09_throughput"] / all_run_results["00_arrivals"]
                )

                all_results_throughput_box = px.box(
                    all_run_results.reset_index()
                    .melt(id_vars=["Model Run", "rep"])
                    .set_index("variable")
                    .filter(like="perc_throughput", axis=0)
                    .reset_index()
                    .assign(Scenario=lambda d: d["Model Run"].map(scenario_labels)),
                    y="variable",
                    x="value",
                    color="Scenario",
                    category_orders={"Scenario": scenario_order},
                    points="all",
                    height=800,
                )

                all_results_throughput_box.update_layout(
                    xaxis_tickformat=".0%", legend_title_text="Scenario"
                )

                all_results_throughput_box.update_yaxes(
                    title_text="",
                    autorange="reversed",
                    labelalias={
                        "perc_throughput": "Throughput (% of arrivals<br>that exit before model end)"
                    },
                )
                all_results_throughput_box.update_xaxes(title_text="% Throughput")

                # Add in a box plot showing waits
                st.plotly_chart(all_results_throughput_box, width="stretch")

                # st.write(all_run_results.filter(like="wait", axis=1)
                #             .merge(all_run_results.filter(like="throughput", axis=1),
                #                 left_index=True, right_index=True))
        with scenario_tab_3:
            # df['Color'] = np.where(
            #     (df['Set'] == 'Z') & (df['Type'] == 'A'), 'yellow',
            #   np.where((df['Set'] == 'Z') & (df['Type'] == 'B'), 'blue',
            #   np.where((df['Type'] == 'B'), 'purple', 'black')))

            st.markdown(
                "This displays the median value for each metric across all model runs per scenario."
            )

            output_scenario_df = all_run_results.groupby("Model Run").median().T
            output_scenario_df = output_scenario_df.reset_index(drop=False).melt(
                id_vars="index"
            )
            # st.dataframe(output_scenario_df)

            output_scenario_df["formatted_value"] = np.where(
                output_scenario_df["index"].str.contains("wait|time"),
                (output_scenario_df["value"].round(1)).astype(str) + " minutes",
                np.where(
                    output_scenario_df["index"].str.contains("util|perc"),
                    ((output_scenario_df["value"] * 100).round(1)).astype(str) + "%",
                    np.where(
                        output_scenario_df["index"].str.contains("arrivals|throughput"),
                        (output_scenario_df["value"].astype(int)).astype(str),
                        output_scenario_df["value"],
                    ),
                ),
            )
            output_scenario_df = output_scenario_df.drop(columns=["value"])
            # st.dataframe(output_scenario_df)
            output_scenario_df = output_scenario_df.pivot(
                index="index", columns="Model Run", values="formatted_value"
            ).reset_index(drop=False)
            output_scenario_df.columns = [
                scenario_labels.get(i, f"Scenario {i}")
                for i in output_scenario_df.columns
            ]
            # st.dataframe(output_scenario_df)
            output_scenario_df = output_scenario_df[
                output_scenario_df["Scenario index"].str.contains(r"\d", regex=True)
            ]

            output_scenario_df["Scenario index"] = output_scenario_df[
                "Scenario index"
            ].apply(lambda x: (x.replace("_", " ")).title())

            st.dataframe(
                output_scenario_df.set_index(output_scenario_df.columns[0]).rename_axis(
                    "Metric", axis=0
                ),
                hide_index=False,
                width="stretch",
                height=700,
            )
            del output_scenario_df

            del all_run_results
            gc.collect()
    else:
        st.markdown(
            "No scenarios have been run yet. Go to the 'Simulate' tab and run the simulation."
        )

#################################################
# Take-away
#################################################
st.divider()

footer_qr, footer_text = st.columns([1, 5], vertical_alignment="center")

footer_qr.image("resources/hsma_qr.png", width=130)

footer_text.markdown(
    """
    **Want to learn how to build models like this?**

    HSMA trains people working in health and social care in simulation modelling
    and data science. Scan the code or visit the
    [HSMA website](https://hsma.co.uk) to find out more, or
    [explore the code for this app](https://github.com/hsma-programme/des_playground_mini).
    """
)
footer_text.caption(
    "Based on the open treatment centre simulation model by Monks T, Harper A, "
    "Anagnostou A, Allen M, Taylor S (2022)."
)

gc.collect()
