---
name: black
description: Format Python plugin code with black from the project virtualenv. Run after every edit to a file under plugins/ so it matches the black version CI enforces.
---

# black

Format Python with the venv's `black` (matches CI's pre-commit hook).
Run after every edit to a `plugins/**/*.py` file, before the change is done.

```sh
venv/bin/black plugins/modules/<file>.py   # or: venv/bin/black plugins
venv/bin/black --check plugins             # the exact check CI runs — "All done!" when clean
```

Re-read a file if black rewrote it. black formats only — see `ruff` for lint. Missing or wrong
version → set up the venv with the `virtualenv` skill.
