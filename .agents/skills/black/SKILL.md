---
name: black
description: Format Python plugin code with black from the project virtualenv. Run after every modification to a file under plugins/ so the change matches the black version CI enforces.
---

# black

Format Python code with `black` using the project's virtualenv, not a system or global
install. The venv pins `black==26.3.1` (see `requirements.txt`), matching the
`black-pre-commit-mirror` rev in `.pre-commit-config.yaml`, so local formatting agrees with
what the pre-commit CI job enforces. A different black version can produce different
formatting and a passing local run that still fails CI.

## When to run

Run black after **every** modification to a file under `plugins/` — every `Edit` or `Write`
to a `plugins/**/*.py` file — before considering the change complete. Do not batch it to the
end of a multi-file task; format each plugin file as you finish editing it.

## How to run

Format the file(s) you just changed:

```sh
venv/bin/black plugins/modules/<file>.py
```

Or format the whole plugins tree (safe; only rewrites files that need it):

```sh
venv/bin/black plugins
```

Then confirm nothing is left unformatted — this is the exact check CI runs:

```sh
venv/bin/black --check plugins
```

A clean run reports `All done!` with every file left unchanged. If `black` rewrote a file,
re-read it before making further edits.

## Notes

- If `venv/bin/black` is missing or reports a version other than the pinned one, sync the
  venv first: `venv/bin/pip install -r requirements.txt` (or `make python`).
- Formatting only — black does not lint. Style/lint for YAML and playbooks is handled
  separately by `ansible-lint` and `yamllint`.
