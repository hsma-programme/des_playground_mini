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
