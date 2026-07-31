---
name: yamllint
description: Lint YAML files with yamllint.
---

# yamllint

Matches CI's `--strict` mode.

```sh
source venv/bin/activate
yamllint --strict roles/{{ role }}/tasks/main.yml
yamllint --strict .
```

- Clean run prints nothing; fix each line by hand.
- Checks raw YAML only — also run `ansible-lint` on role changes.

## Dependencies

- `virtualenv` skill
