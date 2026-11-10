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
- **The challenge:** get every metric into the green using as few rooms as possible. Green means each type of room is in use for 50% to 85% of the day (all 24 hours) on average, and average waits are under 120 minutes. The app keeps track of your best score so far.

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

**If you need lots of people using it at the same time, use the full DES Playground instead.** The [full DES Playground](https://playground.hsma.co.uk) runs on stlite, so each person's copy runs in their own browser, on their own computer, with nothing to download or install. Nobody shares memory or processing power with anyone else, so it copes with large groups much better than this app. It covers the concepts step by step rather than jumping straight to the challenge, so plan the session around that.

### Discussion points

**"Why can't I change the number of rooms during the day?"**

This is likely to come up once people look at the queue chart under the animation. Arrivals follow a strong daily pattern ([data/ed_arrivals.csv](data/ed_arrivals.csv)). The department is open 24 hours. About 2 patients an hour arrive overnight, from midnight to 6am, and 3-4 an hour late in the evening. There's a big peak of about 45 an hour at 12-1pm, and a second peak of about 29 an hour at 5-6pm. The room numbers, though, stay the same for the whole run. Any fixed number of rooms is too many overnight and too few at the peaks, so there is a limit to how green you can get. It's also why the green utilisation band starts as low as 50%: nobody can keep a room busy through a quiet night.

This is a good opening to talk about how the model could be extended, and about how flexible DES is in general:

- **Shift patterns:** rooms or staff could open and close at set times of day to follow demand. In SimPy this is a small extra process that changes the capacity available at set times.
- **Staff as well as rooms:** a cubicle is no use without a clinician. The model could treat staff as a separate resource with their own rotas, breaks and skill mix.
- **Flexible capacity:** staff could move between areas when one queue builds up, or extra capacity could be brought in once a queue passes a threshold.
- **The general point:** DES can model almost any rule that can be described clearly, such as priorities, rotas, patients giving up and leaving, or diverting patients elsewhere. The limits are usually the data you have to support those rules, and the time needed to build and check them, rather than the method itself. This app deliberately exposes only a handful of settings, to keep it quick to pick up.

The "perfect" answer below makes this concrete. Its single triage cubicle is busy 100% of the time from 1pm to 2pm, but only 6% of the time from 2am to 3am. A second triage cubicle open only for the busiest hours might do more good than a permanent one. That's a decision the model can't test as it stands.

**The "perfect" answer, and what the averages hide**

*Spoiler: this gives away an answer to the challenge.*

With the default Advanced Parameters (random number 42, 5 runs of 4 days), the fewest rooms that get all 12 measures into the green is **16**:

| Triage | Registration | Examination | Non-trauma treatment | Trauma stabilisation | Trauma treatment |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 3 | 2 | 7 | 2 |

This was found by changing one room type at a time, starting from the ⚖️ Balanced preset, then trimming the result. Triage and registration are already at the sliders' minimum of one. Taking a room away from any of the other four stages loses at least one green measure.

Once a group finds it (or gets close), a good question to ask is: *"So is this a good emergency department?"* Every number the challenge scores is an average, and the event logs from the same runs show what the averages smooth over:

- **A green wait can sit on top of a long queue.** The average triage wait is just under an hour, comfortably green. But the single triage cubicle can't keep up in the early afternoon. The queue peaked at between 49 and 72 people in each of the five runs, 15% of patients waited over two hours to be triaged, and the longest wait was nearly three and a half hours. Patients who arrived between 2pm and 3pm waited about two hours on average. The queue chart under the animation shows this building up.
- **A green average can have a long tail.** Trauma patients wait 98 minutes on average for a stabilisation bay, just inside the target. But 1 in 3 waited over two hours, and the longest wait was more than nine hours.
- **Utilisation is averaged over the whole day.** The triage cubicle's 56% (in the ideal range) is made up of being flat out after lunch and almost idle overnight.
- **Each stage is judged on its own, but patients go through all of them.** Waits add up along the way. Non-trauma patients spent 2 hours 45 minutes in the department on average, and a quarter were there for more than four hours. Trauma patients spent almost six hours on average, and two thirds were there for more than four hours. None of this shows up in the stage-by-stage targets.
- **Patients still waiting when a run stops are left out.** An average wait only includes patients whose wait has finished. Runs end at 6am after a quiet night, so the non-trauma side has emptied by then. The trauma side hasn't: 47 trauma patients were still waiting for a stabilisation bay or trauma treatment when the runs ended. These are the people who have waited longest, so the worse the queues, the more this flatters the average.
- **The answer depends partly on luck.** With the same 16 rooms, five of six other random numbers kept everything green. In the sixth, trauma treatment tipped just over 85% utilisation. Trauma treatment is at 82% even with the default random number, close to the edge of the green band.
- **The box plots show the spread between runs, not between patients.** Each dot in the Advanced Graphs is one run's average. So even those charts can't show that some patients waited hours while most waited minutes.

None of this means the model is wrong. The summary measures were chosen to keep the challenge simple, and real performance reporting faces the same trade-offs. It's a good way to get people asking which measures they'd want to see before trusting a result: percentiles, the share of patients over a threshold, waits by time of day, or the whole patient journey.

**Is a two-hour wait the right target for every stage?**

The challenge uses the same targets everywhere: an average wait under two hours, and each type of room in use for 50% to 85% of the day. It's worth asking whether that makes sense.

- **Trauma stabilisation is time-critical.** For a seriously injured patient, an hour's wait for stabilisation matters far more than an hour's wait for registration. The "perfect" answer leaves trauma patients waiting 98 minutes on average for a stabilisation bay. Adding three stabilisation bays and one trauma treatment cubicle (20 rooms in all) keeps everything green, cuts that wait to about 20 minutes, and cuts trauma patients' average time in the department from almost six hours to under four. An 11th bay cuts the wait to 12 minutes, but the bays' utilisation then drops to 46%, which the app shows as amber. Most departments would happily pay for idle bays here. Should the "ideal" utilisation be lower for resources where delay is dangerous?
- **Trauma patients queue for triage with everyone else.** Every queue in this model is first come, first served. A trauma patient arriving in the early afternoon joins the back of the same triage queue as everyone else, before they even reach a stabilisation bay. Real departments prioritise by clinical need, and DES can model that too.
- **One room can't run as hot as a pool of rooms.** In the "perfect" answer, the single triage cubicle is in use 56% of the day, yet patients wait nearly an hour on average. The three examination rooms are busier, at 70%, but the average wait for examination is only 20 minutes. A larger pool absorbs the ups and downs of arrivals better, so the same utilisation band isn't equally safe for every resource.
- **Stage targets or journey targets?** Targets like the four-hour A&E standard cover the whole visit, not each step. Would you rather have every stage under two hours, or most patients through the whole department in four? The two can point to different solutions.

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
| `data/ed_arrivals.csv` | Hourly arrival rates for each hour of the day, starting at 6am (time-dependent arrival profile). |
| `style.css`, `.streamlit/config.toml` | Dark theme, fonts and custom styling. |
| `resources/` | Logos, animation background images and the HSMA Display font. `make_hospital_background.py` regenerates the floor plan background used in the animation. |

## Model info

The model is a modified version of the open treatment centre simulation model from Monks, T., Harper, A., Anagnostou, A., Allen, M. and Taylor, S. (2022). It is based on exercise 13 in Nelson (2013), *Foundations and Methods of Stochastic Simulation*.

[Treatment centre simulation repository](https://github.com/TomMonks/treatment-centre-sim/tree/main)

Patients arrive according to a time-dependent arrival profile and are triaged. Nelson's clinic only took patients from 6am to midnight. This version is open 24 hours: it uses Nelson's hourly arrival rates from 6am to 10pm, slightly higher rates from 10pm to midnight, and a low rate of 2 an hour from midnight to 6am. Each run starts at 6am. Trauma patients are stabilised and then treated. Non-trauma patients are registered and examined, and some of them then go on to treatment.

All simulation logic uses [SimPy](https://simpy.readthedocs.io/). The animations are made with [vidigi](https://github.com/Bergam0t/vidigi).

## What is HSMA?

HSMA is a course for people in England working in health and social care organisations. Over 15 months it trains participants in operational research and data science techniques to support service development and decision making.

More information about the course can be found [here](https://hsma.co.uk).

All of the course materials are open source - check out [our repositories](https://github.com/hsma-programme).
