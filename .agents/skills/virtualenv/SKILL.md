---
name: virtualenv
description: Set up and use the project's virtualenv. Run make to bootstrap venv/ from pinned requirements; every other skill's tooling lives here.
---

# virtualenv

All tooling runs from a local `venv/` pinned by `requirements.txt`. Every other skill calls
`venv/bin/<tool>` and assumes it exists — set it up first.

```sh
make                       # venv + python deps + galaxy deps + pre-commit hook
source venv/bin/activate   # optional; or call tools as venv/bin/<tool>
```

Sub-targets: `make venv`, `make python` (repin Python deps), `make galaxy` (collection deps),
`make pre-commit`, `make clean`. If a `venv/bin/<tool>` is missing or the wrong version, re-run
`make` (or `make python`). `venv/` is git-ignored.
