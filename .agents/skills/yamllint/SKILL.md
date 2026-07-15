---
name: yamllint
description: Strict-lint YAML with yamllint from the project virtualenv. Run after every change to a .yml/.yaml file.
---

# yamllint

Lint YAML with the venv's `yamllint`. CI runs it `--strict`; match that. Run after every change
to a `.yml`/`.yaml` file.

```sh
venv/bin/yamllint --strict .                          # whole tree (CI runs this)
venv/bin/yamllint --strict roles/<role>/tasks/main.yml
```

Clean run prints nothing. Fix each line by hand — yamllint checks raw YAML only; run
`ansible-lint` too on role changes. Missing or wrong version → `virtualenv` skill.
