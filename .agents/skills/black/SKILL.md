---
name: black
description: Format Python code with black.
---

# black

Matches CI's pre-commit hook.

```sh
source venv/bin/activate
black plugins/modules/{{ file }}.py
black plugins
black --check plugins
```

- Re-read a file if black rewrote it.
- black only formats — lint with `ruff`.

## Dependencies

- `virtualenv` skill
