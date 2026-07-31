---
name: virtualenv
description: Set up the project virtualenv.
---

# virtualenv

All tooling runs from a local `venv/` pinned by `requirements.txt`. Set it up and activate it before
using another repository skill:

```sh
make
source venv/bin/activate
```

Keep it activated — some tools spawn sibling executables that must be on `PATH`.

Sub-targets:

- `make venv` — create the venv.
- `make python` — install/repin Python deps.
- `make galaxy` — install collection deps.
- `make pre-commit` — install the pre-commit hook.
- `make clean` — remove the venv.

Re-run `make` (or `make python`) if a required tool is missing or the wrong version.
`venv/` is git-ignored.

## Dependencies

- `pyenv` skill (provides the pinned Python)
