---
name: ansible-test
description: Run ansible-test sanity on modules and plugins.
---

# ansible-test

Catches `DOCUMENTATION`/`RETURN`/`EXAMPLES` drift, argspec mismatches, and import errors. It is a
required local check; the current GitHub Actions workflow does not run it.

## Pre-checks

Quick checks from the primary checkout, before running sanity:

```sh
source venv/bin/activate
git diff --check
python -m compileall -q plugins
```

## The checkout

Sanity only runs from a real checkout of the collection at
`ansible_collections/{{ namespace }}/{{ name }}/` (from `galaxy.yml`):

- Not the primary checkout, and **not via symlink**.
- This repo uses a git-ignored, on-demand checkout at
  `venv/ansible_collections/{{ namespace }}/{{ name }}`.

Create it once, if `git worktree list` / `ls` doesn't show it, as a detached worktree — it must
be detached since the branch is checked out in the primary tree:

```sh
git worktree add --detach venv/ansible_collections/{{ namespace }}/{{ name }}
```

## Run

Sync your edits in (always `--delete`, so removed/renamed files don't linger), then run from
inside the checkout:

```sh
rsync -a --delete plugins/ venv/ansible_collections/{{ namespace }}/{{ name }}/plugins/
cd venv/ansible_collections/{{ namespace }}/{{ name }}
ansible-test sanity --python "$(cat .python-version)" plugins/modules/{{ file }}.py
```

- Add `--test validate-modules` for just doc/argspec checks.
- Drop the path argument for the full local suite.
- A clean run exits `0`.
- Fix failures in the **primary checkout**, then re-sync and re-run — the checkout is a scratch
  copy.

## Dependencies

- `virtualenv` skill
