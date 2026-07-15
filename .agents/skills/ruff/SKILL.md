---
name: ruff
description: Lint Python plugin code with ruff from the project virtualenv. Run after every edit to a file under plugins/.
---

# ruff

Lint Python with the venv's `ruff`. Run after every edit to a
`plugins/**/*.py` file, before the change is done.

```sh
venv/bin/ruff check plugins/modules/<file>.py         # or: venv/bin/ruff check plugins
venv/bin/ruff check --fix plugins/modules/<file>.py   # apply safe fixes
```

Clean run: `All checks passed!`. Fix by hand what `--fix` can't; re-read rewritten files. ruff
lints only — see `black` for formatting. Missing or wrong version → `virtualenv` skill.
