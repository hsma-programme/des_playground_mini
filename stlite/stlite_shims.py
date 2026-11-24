"""Runtime fixes for Pyodide (stlite build only). Does nothing anywhere else.

1. Import stubs so vidigi imports. vidigi's __init__ eagerly imports vidigi.process_mapping,
   which imports ipycytoscape, ipywidgets and graphviz. This app never uses process mapping,
   and Pyodide can't install those packages. A finder first on sys.meta_path answers for
   those names with empty stand-in modules. Stubs shadow the real modules for the whole
   session, so only list names the app doesn't use.

2. Object-dtype strings in pandas. pandas 3 stores strings in pyarrow, and on 32-bit
   WebAssembly its merge code ends up writing to a read-only numpy view of pyarrow's join
   indices (np.intp is int32 there, so `.astype(np.intp, copy=False)` doesn't copy). Any merge
   whose string key column has missing values then fails with "putmask: output array is
   read-only" (vidigi's animation prep does this). Turning off string inference gives the
   pandas 2 behaviour (object dtype), which the app was developed against.
"""

import importlib.abc
import importlib.machinery
import sys
import types

STUBBED = {"ipycytoscape", "ipywidgets", "graphviz"}


class _StubModule(types.ModuleType):
    __path__ = []  # lets submodules resolve

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        # Works for `from x import Y`, subclassing and `except Y`
        cls = type(name, (Exception,), {})
        setattr(self, name, cls)
        return cls


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in STUBBED:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        pass


if sys.platform == "emscripten":
    if not any(isinstance(f, _StubFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _StubFinder())

    import pandas as pd

    pd.set_option("future.infer_string", False)
