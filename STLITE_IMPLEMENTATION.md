# Running this app in the browser with stlite (second attempt)

A guide to adding an in-browser (stlite) build of this app, hosted as static files on GitHub Pages, **without
changing the Community Cloud version**. It records what was learned doing the same job for
`geographic_playground_mini` (written 2026-11-24), then lists what is specific to this repo, including why the
first attempt (`_ARCHIVE/`) was abandoned.

Status of this repo (2026-11-24): **built and tested locally; not committed or deployed.** `stlite/build.py`,
`stlite/index.html`, `stlite/stlite_shims.py`, `.github/workflows/stlite-pages.yml`, README sections and
`_site/` in `.gitignore`. Tested in headless Chrome over CDP: load, `st.navigation`, a default run, presets, the
animation playing and looping (frame 430 back to 8 after the pause), a second run replaying, the comparison tab
with two scenarios, 390 px width. Findings beyond the guide below:

- `pydantic` ships with Pyodide but is not loaded unless listed in `requirements` (`ModuleNotFoundError` otherwise).
- **The actual animation blocker was pandas 3 on wasm32**, not the iframe: vidigi's `generate_animation_df` merge
  failed with "putmask: output array is read-only" (pyarrow join indices are int32 = `np.intp` on wasm32, so
  `astype(np.intp, copy=False)` returns a read-only view). Fixed in the shims with
  `pd.set_option("future.infer_string", False)` (browser only). The local `.venv` has pandas 2.3.3, so this path
  is untested on CPython here.
- The loading overlay and progress bar did not appear until the copy got `await asyncio.sleep(0.05)` after each
  `my_bar` progress line (`yield_after_progress()` in `build.py`, with an assertion on the count).
- `components.html` (srcdoc iframe) works for the animation as is; no URL-page workaround needed.
- stlite shows "Deploy" in the toolbar, so the build sets `client.toolbarMode = "viewer"` (Community Cloud hides it anyway).
- The `queue_size_over_time` "did not occur in any run" warning also happens on CPython: not stlite-specific.
- Still open: enabling Pages and the `CNAME` question below, and timing on real hardware and networks.

The rest of this document is the original guide.

## Goal and the one rule

- Visitors' browsers run the whole app (Streamlit on Pyodide/WebAssembly). No server, so hosting is free and
  every visitor gets their own copy (no shared CPU, which matters for a simulation app).
- **The Community Cloud app must not change behaviour.** The stlite version is *built from* the existing source by
  a script that copies files into `_site/` and patches only the copies. Do not edit `app_model.py` etc. to suit
  stlite unless the user explicitly agrees.

## History: the `_ARCHIVE/` attempt, and what has changed since

`_ARCHIVE/pack.py` used **stlitepack** with stlite 1.8.1 (Streamlit 1.57, Pyodide 0.29.3). The README says it
"does not work with the app's automatic animation replay", which is why the app moved to Community Cloud. The
cause of that failure is **not recorded anywhere in the repo**. From git history, the fixes that attempt needed:

- `639b6bd`: `await asyncio.sleep(0.1)` added inside the run button's spinner, because stlitepack only auto-adds it
  for *embedded* files, not linked ones (a top-level `await` is a `SyntaxError` on Community Cloud).
- `32a022f`: CSS fixes for sidebar logo size, main-content top padding and the slider tick bar.
- `plotly==6.0.1` and `vidigi<2.0.0` pins, with a comment that micropip's resolver chose plotly 6.9.x and then
  could not use it.
- `60d0a1e`, `5b303ac`, `f4d34e1`: the page moved into `app_model.py` and markdown into the `.py` files "to avoid
  issues with embedding" (a stlitepack limitation).

All of that was on an older runtime. stlite is now **1.12.3 (2026-11-22): Streamlit 1.65.0 fork, Pyodide 314.0.3,
Python 3.14**. Re-test rather than assume the old problems persist. In particular, plotly 6.9.0 installed fine via
micropip on Pyodide 314 in the geographic app.

## Reference implementation (copy from here)

`C:\geographic_playground_mini` (committed on `main`: `de59a59`, `96ab608`):

| File there | What to do with it |
|---|---|
| `stlite/build.py` | Copy, then adapt (see "What to change in build.py") |
| `stlite/index.html` | Copy as is. Placeholders `__STLITE_VERSION__`, `__MOUNT_OPTIONS__`, `__FONT_LINK__` |
| `stlite/stlite_shims.py` | Copy and change `STUBBED` to `{"ipycytoscape", "ipywidgets", "graphviz"}` (see "vidigi") |
| `.github/workflows/stlite-pages.yml` | Copy; swap `uv sync`/`uv run` for `pip install -r requirements.txt` / `python` if there is no `uv.lock` |
| its README "In-browser version" + "Limitations" sections and `HANDOVER.md` "stlite" section | Templates for this repo's docs |

Preview locally: `python stlite/build.py --serve` (builds, then serves `http://localhost:8599/`).

## Tooling decision

Use a hand-written `build.py`, not stlitepack: 0.4.5 (Aug 2025) defaults to stlite 0.80.5, cannot vendor packages,
and edits app code itself (which is exactly what caused the archive's `await` problem). The build writes an
`index.html` that calls `mount()` from `https://cdn.jsdelivr.net/npm/@stlite/browser@1.12.3/build/stlite.js`
(pin the version; check `https://registry.npmjs.org/@stlite/browser/latest` for anything newer).

## How the build works

1. Copy the needed files to `_site/` at the same relative paths. The app opens `style.css`, `resources/...` and
   `data/...` by path; `model_classes.py` uses `Path(__file__).parent.joinpath("data", ...)`, which works in
   stlite's virtual file system because files are written beside the entry script.
2. Prepend stlite-only imports to the *copy* of the entry script.
3. Write `index.html` with `mount({entrypoint, files: {path: {url: path}}, requirements, streamlitConfig}, root)`.
   Files load by relative URL, so it works under a GitHub Pages sub-path.
4. Write `.nojekyll`. Serve over HTTP; **`file://` cannot work**.

## Learnings that apply here (all hit on the geographic app)

**Debugging has no server log.** A failed app is a blank page. Capture the browser console over the DevTools
protocol: the Python traceback arrives as a console/log message. A working pattern is a ~30-line script that
launches headless Chrome with `--remote-debugging-port`, enables `Runtime`, `Log` and `Network`, navigates, and
prints `Runtime.consoleAPICalled`, `Runtime.exceptionThrown`, `Log.entryAdded` (level error/warning),
`Network.loadingFailed` and HTTP >= 400 for ~60 s. Strip `data:...;base64,` URLs from the output (each log line
carries a huge one). The geographic repo's `scripts/cdp_drive.py` (screenshots, clicks, JS evaluation) also works
against the built site; use an **absolute output prefix**, allow ~75 s for first load, and remember tab labels in
`innerText` are mixed case even if CSS shows capitals.

**`theme.font` with a font URL gives a blank page.** `.streamlit/config.toml` here has
`font = "Space Grotesk:https://fonts.googleapis.com/..."`. In stlite 1.12.3 that crashes the frontend
(`HelmetDispatcher.init`: "Cannot read properties of undefined (reading 'add')"), found by passing each config key
alone. Fix in `build.py`: pop `theme.font` and put `<link rel="stylesheet" href="<the font URL>">` in
`index.html` (works because `style.css` sets the family).

**Pass `config.toml` as `streamlitConfig`, not as a shipped file.** Streamlit still reads a mounted
`.streamlit/config.toml`, bringing the crash back. Flatten the TOML to dotted keys with `tomllib`. Theme, sidebar
colours and `toolbarMode` carried over on the geographic app.

**Sidebar markup differs.** Streamlit 1.66 marks an open sidebar `data-collapsed="false"`; stlite's 1.65 fork uses
`aria-expanded="true"`. This repo's `style.css` (line ~292) already targets `aria-expanded="true"`, so its sidebar
width rule should match in stlite as is. Verify at desktop and ~390 px width. (This repo pins Streamlit 1.63,
older than the fork, so CSS differences are less likely than on the 1.66 apps; still check the toolbar rules
around `[data-testid="stToolbar"]`.)

**Packages.** Pyodide 314 ships numpy 2.4.3, pandas 3.0.2, matplotlib 3.10.8, Pillow 12.2.0, scipy 1.18.0 and
pydantic 2.12.5. It does **not** ship plotly, simpy, webcolors, graphviz, ipywidgets or ipycytoscape. Pure-Python
wheels from PyPI go in `requirements` (installed with micropip at start-up). `simpy` 4.1.2 publishes a
`py3-none-any` wheel (checked on PyPI); plotly installed this way on the geographic app. Pin plotly to the
version installed in the build environment.

**Everything online stays online.** stlite and Pyodide come from jsDelivr, as do Google Fonts and the plotly.js
bundle that the animation HTML references. The first load downloads tens of MB; 20-60 s is an estimate, never
timed (only waited out). Not an offline stand build.

**`st.html(..., unsafe_allow_javascript=True)` works** (verified: the geographic app's dropdown script rendered).

**`st.navigation` / `st.Page` is unverified.** The geographic app has a single script. stlite's changelog says
`st.navigation().run()` works with pages containing top-level awaits (0.67.1, 2024), and its README documents the
older `pages/` directory. Test it early: this app's entry is `st.navigation([st.Page("app_model.py")])`, and
`app_model.py` must be in the mounted `files`.

## What is specific to this repo

### vidigi imports heavy optional packages eagerly (verified by reading the wheel)

`vidigi` 2.0.0's `__init__.py` does `from . import analysis, animation, ciw, logging, plots, prep, process_mapping,
resources, utils`, and `process_mapping.py` begins with `import ipycytoscape`, `import ipywidgets as widgets` and
`from graphviz import Digraph`. Those are declared dependencies, but this app never uses process mapping, and
Pyodide doesn't ship them. This is the same shape of problem as lokigi on the geographic app, solved the same way:

- Vendor vidigi (pure Python, `py3-none-any`) from the build environment into `_site/vidigi/` (see `vendor()` in
  the geographic `build.py`), or install it with micropip *without dependencies* (the kernel's `installs` option
  takes `{requirements, options: {deps: false}}`; this is read from stlite's types, **not tested**).
- Put the packages it really needs at runtime in `requirements`: `plotly`, `simpy`, `webcolors` (imported by
  `vidigi/utils.py`). numpy, pandas and pydantic are built in.
- Stub the three unavailable names with `stlite_shims.py` (a `sys.meta_path` finder, active only when
  `sys.platform == "emscripten"`), imported first in the copy of `streamlit_app.py`.
- `vidigi/utils.py` imports IPython and `streamlit_javascript` only inside functions, so they should not be needed.
  If the first run still fails at `import vidigi...`, the traceback names the next module: add it to `STUBBED`.
- Caveat: stubs shadow real modules for the whole session; only stub names the app does not use.

### The animation is the risk, and the likely reason the first attempt failed

`helper_functions.py:345` renders the vidigi animation with `components.html(html, height=height, scrolling=True)`
(an iframe `srcdoc`; a comment says to swap it for `st.iframe`). The README says "automatic animation replay"
broke in stlite. The cause was never recorded, so treat these as **hypotheses (inferred), not facts**:

- On the geographic app, a Plotly **map** page embedded as an iframe `srcdoc` stayed blank even though hover worked;
  loaded by URL it was fine. (Plotly frame autoplay on map subplots also stalls until the basemap loads; vidigi's
  animation is a non-map Plotly figure, so that part may not apply.)
- The animation page pulls plotly.js from a CDN and runs its own timers; something there may differ under stlite.

First step: build, run a simulation, and read the console while the animation plays. If `srcdoc` is the problem,
the options are (a) `st.iframe` with the HTML string (the fork supports `st.iframe`; same srcdoc mechanism, so it
may not help), or (b) a URL-loaded page. **stlite has no server, so a URL page must be a real file on the host**:
fine for a fixed set of pages (the geographic build pre-renders three at build time and rewrites the page-name
line in its copy of `animation.py`), but not for scenarios chosen at run time. (c) A `blob:` URL created from
JavaScript via `st.html` is a possibility; untested. If none works, decide with the user whether to ship stlite
without the animation or abandon it.

### Other things to handle

- **No `await` in the source.** `app_model.py` imports `asyncio` (line 13) but currently has no `st.spinner` or
  `await`. stlite documents that `st.spinner` doesn't show during blocking calls, and `time.sleep` is a no-op. If
  the run button's spinner or progress bar looks frozen, patch the **copy** (assert the exact text first), e.g.
  insert `await asyncio.sleep(0.1)` after the spinner line, exactly as `639b6bd` did in the source. Never put a
  top-level `await` in the original file: it is a `SyntaxError` on Community Cloud.
- **Speed.** SimPy replications run single-threaded in WebAssembly, so expect slower runs than on Community Cloud
  (inferred; time a default run). stlite has no threads or multiprocessing; this app uses neither (it calls
  `gc.collect()` in several places, which is harmless).
- **Network code.** `helper_functions.read_file_contents_web` calls `urllib.request.urlopen`, which does not work
  in Pyodide. It is unused today (only its definition exists). Don't reintroduce it; fetch with `pyodide.http` or
  ship the file.
- **Streamlit 1.63 vs the 1.65 fork.** Streamlit here is pinned to 1.63.0, older than the fork, so removed-API
  surprises are unlikely but possible: stlite's changelog notes Streamlit removed `add_rows()` and the
  `mapbox.token` option by 1.65. This app does not call `add_rows` (checked).

### What to ship

Explicit list (do not glob; `resources/` holds `.drawio` sources and `.ttf` fonts that are not used at runtime):
`streamlit_app.py`, `app_model.py`, `model_classes.py`, `distributions.py`, `helper_functions.py`, `style.css`,
`data/ed_arrivals.csv`, and from `resources/`: `Chalky HSMA-07-wide white logo tall with tagline - new tagline.png`,
`NIHR_APPLIED_RESEARCH_COLLABORATION_Logo_Horizontal_RGB_WHITE.png`, `hsma_qr.png`,
`fonts/hsma-display/HSMADisplay-Regular.woff2`. (The archive's `pack.py` also listed `hsma_logo*.png`; grep
`resources/` in the `.py` files and `style.css` to confirm what is actually referenced.) Do **not** ship `_ARCHIVE/`,
`__pycache__/`, `404.html`, `CNAME`, `README.md`.

## What to change in build.py (starting from the geographic one)

- `APP_PY`, `APP_DIRS`/files as above. Keep `style.css`.
- Keep: `vendor()` (for `vidigi` only; `simpy` and `plotly` come from `requirements`), `stlite_shims` with the new
  `STUBBED`, `flatten()`, the `theme.font` handling, `streamlit_config`, `index.html` templating, `.nojekyll`,
  `--serve`.
- Delete: the lokigi/sweetpareto vendoring, the `HASH_NAME` patch and `prerender_animations()` (unless the
  animation needs the pre-render route), and the sidebar `SIDEBAR_CSS` (this repo already targets `aria-expanded`).
- `requirements`: `plotly==<installed>`, `simpy`, `webcolors`. Drop seaborn.
- The build needs `vidigi` installed to vendor it (`pip install -r requirements.txt` in CI).

## Deployment (GitHub Pages), and a leftover to check

The reference workflow builds on push to `main` and deploys with `actions/upload-pages-artifact` +
`actions/deploy-pages`. One-off: **Settings -> Pages -> Source: GitHub Actions**; until then the deploy job fails.
A push to `main` also redeploys Community Cloud (if it deploys from `main`). Confirm with the user before pushing.

**Check before enabling Pages:** the repo root has a `CNAME` containing `playground.hsma.co.uk` and a `404.html`
that redirects to `https://hsma-programme.github.io/Teaching_DES_Concepts_Streamlit/`. The README says the *full*
DES Playground lives at `playground.hsma.co.uk`, so this repo should not claim that domain. With the Actions
deploy these root files are not published, but the repo's Pages **custom domain setting** may still point at the
other site. Open question for the user; use the default `github.io` URL unless told otherwise.

## Verify

1. `python stlite/build.py --serve`, open `http://localhost:8599/`, wait up to a minute. Console: no traceback.
2. Navigation works (`st.Page`), presets, a simulation run, the **animation plays and replays**, charts and the
   scenario comparison, at desktop and ~390 px width.
3. `git diff --stat` shows only new files plus docs and `.gitignore` (add `_site/`): Community Cloud is untouched.
4. State plainly what was checked. The geographic pass did **not** cover touch, real stand wifi, offline use or
   the Pages deploy.

## Handy things to know

- On Windows, generating Python source from a shell heredoc turned `\n` inside strings into real newlines more than
  once. Use the editor tool for edits with escapes, then run
  `python -c "import ast; ast.parse(open('stlite/build.py', encoding='utf8').read())"`.
- Stop test servers by port (`netstat -ano | grep :8599`), not `pkill -f` with a pattern that also matches the
  command doing the killing.
