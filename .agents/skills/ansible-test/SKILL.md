---
name: ansible-test
description: Run ansible-test sanity on module/plugin changes from the project virtualenv, including the collection checkout sanity requires. Run after modifying any file under plugins/.
---

# ansible-test

Run sanity after any change under `plugins/` — it catches `DOCUMENTATION`/`RETURN`/`EXAMPLES`
drift, argspec mismatches, and import errors (CI runs the same suite). Also run `black` and
`ruff` on the file. Needs the `virtualenv` skill.

## The checkout

Sanity only runs where the collection physically lives at `ansible_collections/<namespace>/<name>/`
(from `galaxy.yml`) — not the primary checkout, and **not via symlink**. This repo keeps it under
`venv/ansible_collections/<namespace>/<name>`, a git-ignored, on-demand checkout. Create it once
(if `git worktree list` / `ls` doesn't show it) as a detached worktree — it already holds the
committed tree, and must be detached since the branch is checked out in the primary tree:

```sh
git worktree add --detach venv/ansible_collections/<namespace>/<name>
```

A plain copy works too (sanity doesn't need git), but then sync the full tree, not just `plugins/`.

## Run

Sync your edits in (always `--delete` so removed/renamed files don't linger), then run from
inside the checkout (interpreter from `.python-version`):

```sh
rsync -a --delete plugins/ venv/ansible_collections/<namespace>/<name>/plugins/
cd venv/ansible_collections/<namespace>/<name>
../../../bin/ansible-test sanity --python "$(cat .python-version)" plugins/modules/<file>.py
```

- Add `--test validate-modules` for just doc/argspec checks.
- Drop the path argument for the full suite (what CI runs).

Fix failures in the **primary checkout**, re-sync, re-run — the checkout is a scratch copy. A
clean run exits `0`. Quick extras from the primary checkout: `git diff --check`, `venv/bin/python
-m compileall -q plugins`.
