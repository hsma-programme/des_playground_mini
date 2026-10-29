# DES Playground Mini

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://des-playground-mini.streamlit.app/)

A single-page Streamlit app that puts you in charge of staffing a virtual emergency department. It is a short, hands-on introduction to discrete event simulation (DES): change how many rooms of each type are open, run the simulation, and see how waits and utilisation respond.

It is a cut-down version of the HSMA [DES Playground](https://github.com/hsma-programme/Teaching_DES_Concepts_Streamlit). The full playground walks through DES concepts one page at a time. This version skips straight to the complete model so it can be picked up in a few minutes, for example at open days and events.

## What the app does

**Simulate tab**

- Use the sidebar sliders to set the number of triage cubicles, registration cubicles, examination rooms, non-trauma treatment cubicles, trauma stabilisation bays and trauma treatment cubicles. You can also set the share of arrivals who are trauma patients and the share of non-trauma patients who need treatment.
- Under **Advanced Parameters**, set the random seed, the number of replications (1-10) and the run length (1-30 days).
- Or press one of the four presets, which set the sliders and run the model in one click: 🏥 Current setup, 😰 Understaffed, ⚖️ Balanced and 💸 Throw money at it.
- After each run you get:
  - a results summary with headline metrics, compared with the previous run;
  - an animated floor plan of the first replication (built with [vidigi](https://github.com/Bergam0t/vidigi)), with queue lengths over time shown underneath;
  - simple and advanced charts of utilisation and waits across all replications.
- **The challenge:** get every metric into the green using as few rooms as possible. Green means average utilisation between 65% and 85%, and average waits under 120 minutes. The app keeps track of your best score so far.

**Compare Scenario Outputs tab**

Every run in a session is saved as a scenario, labelled with the preset it matches or "Custom". Here you can compare their parameters, utilisation, waits and throughput side by side. Runs with identical settings are not saved twice. The **Clear scenarios** button starts again.

## Notes for facilitators

### Before the session: warm the app up

Open the [app](https://des-playground-mini.streamlit.app/) well before attendees arrive and run one of the presets.

Community Cloud puts apps to sleep after a period with no visitors (currently 12 hours). A sleeping app shows a "wake up" button and takes a minute or two to start again. The first simulation after a restart is also slower than later ones. It is better that you wait through this than a room full of attendees.

As a backup, have a copy running locally on your own laptop (see [Running locally](#running-locally)).

### Concurrent users

Community Cloud has no fixed limit on the number of users. Everyone shares a single copy of the app, though, with limited memory (currently between about 690 MB and 2.7 GB, and Streamlit can change this without notice). Every simulation runs inside that shared copy, so many people running long simulations at the same moment can slow the app down for everyone. In the worst case the app goes over its resource limits and stops responding.

To reduce the risk with a large group:

- **Start everyone on the presets with the default Advanced Parameters.** Results are cached and shared between users, so a run with the same settings as an earlier one is returned straight away and does not repeat the simulation.
- **Discourage everyone from maxing out the Advanced Parameters at once.** 30 days x 10 replications is a lot more work than the default 4 days x 5 replications.
- **For big groups, work in pairs or small teams on one device each** rather than one device per person.
- **If the app falls over,** the app owner can reboot it from **Manage app** on Community Cloud. This clears its memory but disconnects everyone, and their saved scenarios are lost.

### Discussion points

**"Why can't I change the number of rooms during the day?"**

This is likely to come up once people look at the queue chart under the animation. Arrivals follow a strong daily pattern ([data/ed_arrivals.csv](data/ed_arrivals.csv)). Patients arrive from 6am until midnight, with about 2-3 an hour first thing and late at night, a big peak of about 45 an hour at 12-1pm, and a second peak of about 29 an hour at 5-6pm. The room numbers, though, stay the same for the whole run. Any fixed number of rooms is too many overnight and too few at the peaks, so there is a limit to how green you can get.

This is a good opening to talk about how the model could be extended, and about how flexible DES is in general:

- **Shift patterns:** rooms or staff could open and close at set times of day to follow demand. In SimPy this is a small extra process that changes the capacity available at set times.
- **Staff as well as rooms:** a cubicle is no use without a clinician. The model could treat staff as a separate resource with their own rotas, breaks and skill mix.
- **Flexible capacity:** staff could move between areas when one queue builds up, or extra capacity could be brought in once a queue passes a threshold.
- **The general point:** DES can model almost any rule that can be described clearly, such as priorities, rotas, patients giving up and leaving, or diverting patients elsewhere. The limits are usually the data you have to support those rules, and the time needed to build and check them, rather than the method itself. This app deliberately exposes only a handful of settings, to keep it quick to pick up.

**Other questions that may come up**

- **"Why not aim for 100% utilisation?"** Arrivals and treatment times vary, so queues grow very quickly as resources get close to full. Some slack is what keeps waits short. Comparing 😰 Understaffed with 💸 Throw money at it shows both extremes: one has long waits, the other has lots of idle rooms.
- **"Why do my results change when I change the random number?"** Each seed is a different possible run of the same department. This is why the simulation is repeated several times, and why it's worth looking at the spread across replications in the Advanced Graphs as well as the averages.
- **"Is the animation showing all the runs?"** No, it only shows the first replication. The charts and summary cover all of them.

## Running locally

You need Python 3.11 or later (pandas 3 requires it).

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Run the command from the repository root, as the app opens `style.css`, the fonts and images in `resources/`, and `data/` using relative paths.

## Deployment

The app is deployed on [Streamlit Community Cloud](https://des-playground-mini.streamlit.app/) with `streamlit_app.py` as the entry point.

### A note on `_ARCHIVE/`

[_ARCHIVE/](_ARCHIVE/) holds an earlier approach that ran the app entirely in the browser with [stlite](https://github.com/whitphx/stlite), packaged with stlitepack:

- `pack.py` - the stlitepack script that bundled the app.
- `docs/index.html` - the stlite page it generated.

This code does not work with the app's automatic animation replay, which is why the app moved to Streamlit Community Cloud. It is kept for reference only and is not used by the current app.

## Project structure

| Path | Contents |
| --- | --- |
| `streamlit_app.py` | Entry point. Sets up navigation and runs `app_model.py`. |
| `app_model.py` | The app page: sidebar, presets, challenge, animation, charts and scenario comparison. |
| `model_classes.py` | The SimPy model: `Scenario`, the trauma and non-trauma pathways, `TreatmentCentreModel` and `multiple_replications`. |
| `distributions.py` | Sampling distributions used by the model (exponential, lognormal, normal, Bernoulli, uniform). |
| `helper_functions.py` | Logo, the looping animation player, chart target bands, results summaries and metric cards. |
| `data/ed_arrivals.csv` | Hourly arrival rates (time-dependent arrival profile). |
| `style.css`, `.streamlit/config.toml` | Dark theme, fonts and custom styling. |
| `resources/` | Logos, animation background images and the HSMA Display font. `make_hospital_background.py` regenerates the floor plan background used in the animation. |

## Model info

The model is a modified version of the open treatment centre simulation model from Monks, T., Harper, A., Anagnostou, A., Allen, M. and Taylor, S. (2022). It is based on exercise 13 in Nelson (2013), *Foundations and Methods of Stochastic Simulation*.

[Treatment centre simulation repository](https://github.com/TomMonks/treatment-centre-sim/tree/main)

Patients arrive according to a time-dependent arrival profile and are triaged. Trauma patients are stabilised and then treated. Non-trauma patients are registered and examined, and some of them then go on to treatment.

All simulation logic uses [SimPy](https://simpy.readthedocs.io/). The animations are made with [vidigi](https://github.com/Bergam0t/vidigi).

## What is HSMA?

HSMA is a course for people in England working in health, social care and policing organisations. Over 15 months it trains participants in operational research and data science techniques to support service development and decision making.

More information about the course can be found [here](https://hsma.co.uk).

All of the course materials are open source - check out [our repositories](https://github.com/hsma-programme).
