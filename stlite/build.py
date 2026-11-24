"""Build the stlite (in-browser) version of the app into a static folder.

    python stlite/build.py [--out _site] [--serve]
    python -m http.server 8600 -d _site

The Community Cloud app is not touched: this copies its files and patches only the copies
(an import of the stubs at the top of streamlit_app.py, and awaits after the progress-bar
updates in app_model.py). Needs the app's requirements
installed, because vidigi is copied from the build environment into the site.
"""

import argparse
import importlib.metadata as md
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

STLITE_VERSION = "1.12.3"
ROOT = Path(__file__).resolve().parent.parent

APP_PY = ["streamlit_app.py", "app_model.py", "model_classes.py", "distributions.py", "helper_functions.py"]
# Listed one by one: resources/ also holds .drawio sources, .ttf fonts and build scripts
APP_FILES = [
    "style.css",
    "data/ed_arrivals.csv",
    "resources/Chalky HSMA-07-wide white logo tall with tagline - new tagline.png",
    "resources/NIHR_APPLIED_RESEARCH_COLLABORATION_Logo_Horizontal_RGB_WHITE.png",
    "resources/hsma_qr.png",
    "resources/fonts/hsma-display/HSMADisplay-Regular.woff2",
]  # config.toml goes in via streamlitConfig instead


def copy_tree(src: Path, dst: Path):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def vendor(package: str, out: Path):
    """Copy an installed pure-Python package and its licence file(s) into the site."""
    dist = md.distribution(package)
    copy_tree(Path(dist.locate_file(package)), out / package)
    for f in dist.files or []:
        if "licen" in f.name.lower() and "dist-info" in str(f):
            (out / "licences").mkdir(exist_ok=True)
            shutil.copy(dist.locate_file(f), out / "licences" / f"{package}-{f.name}")


def flatten(d: dict, prefix="") -> dict:
    flat = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        flat.update(flatten(v, key + ".") if isinstance(v, dict) else {key: v})
    return flat


PROGRESS_LINE = re.compile(r"^(?P<indent>[ \t]*)my_bar(?: = st\.progress|\.progress)\(.*\)[ \t]*$", re.MULTILINE)
MIN_PROGRESS_LINES = 10  # the initial st.progress(0, ...) plus each my_bar.progress(...) update


def yield_after_progress(path: Path):
    """In stlite the script shares one event loop with the code that sends updates to the
    page, so nothing (the loading overlay, the progress bar) shows until the script yields.
    Add a short await after each progress line of the copy. A top-level await is fine in
    stlite but a SyntaxError on Community Cloud, which is why only the copy gets it."""
    src = path.read_text(encoding="utf8")
    found = len(PROGRESS_LINE.findall(src))
    assert found >= MIN_PROGRESS_LINES, (
        f"{path.name}: expected {MIN_PROGRESS_LINES}+ progress lines, found {found}; update stlite/build.py"
    )
    assert "import asyncio" in src, f"{path.name} no longer imports asyncio; update stlite/build.py"
    path.write_text(PROGRESS_LINE.sub(r"\g<0>\n\g<indent>await asyncio.sleep(0.05)", src), encoding="utf8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "_site"))
    ap.add_argument("--serve", action="store_true", help="after building, serve the site locally (Ctrl+C to stop)")
    # Not 8599, which the geographic playground's preview uses (same origin = shared browser cache)
    ap.add_argument("--port", type=int, default=8600)
    args = ap.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in APP_PY + APP_FILES:
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, out / name)

    # Only the copies are patched (the app's own files stay as they are).
    # The stubs must be in place before vidigi is imported.
    shutil.copy(ROOT / "stlite" / "stlite_shims.py", out / "stlite_shims.py")
    entry = out / "streamlit_app.py"
    entry.write_text("import stlite_shims  # noqa: F401  (stlite build only)\n" + entry.read_text(encoding="utf8"), encoding="utf8")
    yield_after_progress(out / "app_model.py")

    # vidigi is pure Python, but micropip would also try to install its declared
    # dependencies (ipycytoscape, ipywidgets, graphviz, ...), which Pyodide lacks
    vendor("vidigi", out)

    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    config = flatten(tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf8")))
    # stlite 1.12.3 crashes (react-helmet) on a theme.font that carries a font URL. style.css
    # already applies the family, so only the download is needed: load it from index.html.
    font = config.pop("theme.font", "")
    font_url = font.split(":", 1)[1].rsplit(",", 1)[0].strip() if ":http" in font else ""
    # Community Cloud hides the developer toolbar ("Deploy") from visitors; stlite doesn't
    config.setdefault("client.toolbarMode", "viewer")
    options = {
        "entrypoint": "streamlit_app.py",
        "files": {f: {"url": f} for f in files},
        # What vidigi needs at runtime. Pyodide ships pydantic but only loads it when asked
        # (unpinned, so its built-in build is used); the rest are pure-Python wheels from PyPI.
        "requirements": [
            "pydantic",
            f"plotly=={md.version('plotly')}",
            f"simpy=={md.version('simpy')}",
            f"webcolors=={md.version('webcolors')}",
        ],
        "streamlitConfig": config,
    }
    html = (ROOT / "stlite" / "index.html").read_text(encoding="utf8")
    html = html.replace("__STLITE_VERSION__", STLITE_VERSION).replace("__MOUNT_OPTIONS__", json.dumps(options, indent=2))
    html = html.replace("__FONT_LINK__", f'<link rel="stylesheet" href="{font_url}" />' if font_url else "")
    (out / "index.html").write_text(html, encoding="utf8")
    (out / ".nojekyll").write_text("")
    print(f"Built {len(files)} files into {out}")
    print(f"Preview: python -m http.server {args.port} -d {out}")
    if args.serve:
        serve(out, args.port)


def serve(out: Path, port: int):
    """Plain static server. stlite can't run from file://."""
    import functools
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class NoCacheHandler(SimpleHTTPRequestHandler):
        # stlite fetches the app's files through the browser cache, so without this a rebuild,
        # or another app previewed earlier on the same port, can be served stale
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    handler = functools.partial(NoCacheHandler, directory=str(out))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Serving http://localhost:{port}/ (first load takes 20-60 s; Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped")


if __name__ == "__main__":
    main()
