---
name: ansible-lint
description: Lint roles and playbooks with ansible-lint.
---

# ansible-lint

Matches CI's pre-commit hook.

```sh
source venv/bin/activate
ansible-lint roles/{{ role }}
ansible-lint --fix roles/{{ role }}
ansible-lint
```

- Fix findings by hand, or with `--fix` where a rule offers it; re-read rewritten files.

## Dependencies

- `virtualenv` skill
