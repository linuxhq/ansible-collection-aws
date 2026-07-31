---
name: ruff
description: Lint Python code with ruff.
---

# ruff

```sh
source venv/bin/activate
ruff check plugins/modules/{{ file }}.py
ruff check plugins
ruff check --fix plugins/modules/{{ file }}.py
```

- Clean run: `All checks passed!`.
- Fix by hand what `--fix` can't; re-read rewritten files.
- ruff only lints — format with `black`.

## Dependencies

- `virtualenv` skill
