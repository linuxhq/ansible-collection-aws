---
name: molecule
description: Run a role's molecule scenario from the project virtualenv. Scenarios hit real AWS and double as the role's example playbook; run from the role directory.
---

# molecule

Test a role with its `molecule/default/` scenario, run from the role's own directory. Scenarios
hit **real AWS**. Needs the `virtualenv` skill.

```sh
cd roles/<role>
../../venv/bin/molecule test -s default       # full create / converge / verify / destroy
../../venv/bin/molecule converge -s default   # present path only, no teardown
```

The scenario doubles as an example playbook for the role.
