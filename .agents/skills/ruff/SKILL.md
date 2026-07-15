---
name: ruff
description: Lint Python plugin code with ruff from the project virtualenv. Run after every modification to a file under plugins/ to catch lint errors as the change is made.
---

# ruff

Lint Python code with `ruff` using the project's virtualenv, not a system or global install.
The venv pins `ruff==0.15.21` (see `requirements.txt`); using the pinned version keeps
results reproducible, since ruff's default rule set changes between releases.

## When to run

Run ruff after **every** modification to a file under `plugins/` — every `Edit` or `Write`
to a `plugins/**/*.py` file — before considering the change complete. Do not batch it to the
end of a multi-file task; lint each plugin file as you finish editing it.

## How to run

Lint the file(s) you just changed:

```sh
venv/bin/ruff check plugins/modules/<file>.py
```

Or lint the whole plugins tree:

```sh
venv/bin/ruff check plugins
```

Apply the fixes ruff can make automatically, then re-run to see what remains:

```sh
venv/bin/ruff check --fix plugins/modules/<file>.py
```

A clean run reports `All checks passed!`. Anything ruff cannot auto-fix must be resolved by
hand before the edit is done. If `--fix` rewrote a file, re-read it before making further
edits.

## Notes

- If `venv/bin/ruff` is missing or reports a version other than the pinned one, sync the
  venv first: `venv/bin/pip install -r requirements.txt` (or `make python`).
- Linting only — ruff does not format. Python formatting stays with the `black` skill; run
  black as well after editing a plugin file.
