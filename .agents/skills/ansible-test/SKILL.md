---
name: ansible-test
description: Run ansible-test sanity on module/plugin changes from the project virtualenv. Run after modifying any file under plugins/ to catch the sanity failures CI enforces on the collection.
---

# ansible-test

Run `ansible-test sanity` with the project's virtualenv, not a system or global install. The
venv pins `ansible>13,<14` (see `requirements.txt`), which provides `ansible-test`; using the
pinned version keeps results reproducible, since sanity ignores and the bundled test set
change between `ansible-core` releases.

## When to run

Run sanity after modifying any file under `plugins/` — a new or changed module in
`plugins/modules/`, a lookup in `plugins/lookup/`, or their docs — before considering the
change complete. `DOCUMENTATION`/`RETURN`/`EXAMPLES` drift, argument-spec mismatches, and
import errors are exactly what sanity catches, and CI runs the same suite.

## The physical-path requirement

`ansible-test` resolves the real filesystem path and only runs when the collection lives at
`ansible_collections/linuxhq/aws/`. It will not run from the primary checkout
(`/Users/tkimball/Git/ansible-collection-aws`), and **symlinks do not work**.

This repo already has a git worktree at the required path:

```
venv/ansible_collections/linuxhq/aws
```

That worktree shares the same git repository (`.git/worktrees/aws`) as the main checkout, so
it is the place to run sanity. It is a **separate working tree** — edits made in the primary
checkout are not visible there until you sync them across (see below).

## How to run

1. Sync your plugin tree from the primary checkout into the worktree. The two are
   independent working trees, so mirror the source over — always with `--delete` so files you
   renamed or removed do not linger in the worktree and get tested as stale copies:

   ```sh
   rsync -a --delete plugins/ venv/ansible_collections/linuxhq/aws/plugins/
   ```

   Mirror the whole `plugins/` tree (not just the file you touched): a rename leaves the old
   module behind otherwise, and sanity would validate both. Without `--delete` the worktree
   silently accumulates deleted files and reports results that no longer match your checkout.

2. Run sanity from inside the worktree, using the venv's `ansible-test`. Do not hardcode the
   Python version — read it from `.python-version` (present in the worktree) so the skill
   tracks the project's pinned interpreter:

   ```sh
   cd venv/ansible_collections/linuxhq/aws
   ../../../bin/ansible-test sanity --python "$(cat .python-version)" plugins/modules/<file>.py
   ```

   Or run a single test across the file (e.g. just doc/argspec validation):

   ```sh
   ../../../bin/ansible-test sanity --python "$(cat .python-version)" --test validate-modules plugins/modules/<file>.py
   ```

   To run the full collection sanity suite (what CI runs), drop the path argument:

   ```sh
   ../../../bin/ansible-test sanity --python "$(cat .python-version)"
   ```

A clean run exits `0`. Any reported failure names the test, file, and line — fix it in the
**primary checkout**, re-sync, and re-run. Do not leave fixes only in the worktree; it is a
scratch copy and the primary checkout is what gets committed.

## Notes

- If `venv/bin/ansible-test` is missing, sync the venv first: `venv/bin/pip install -r
  requirements.txt` (or `make python`).
- If the worktree is gone (`git worktree list` does not show
  `venv/ansible_collections/linuxhq/aws`), recreate it:
  `git worktree add --detach venv/ansible_collections/linuxhq/aws`. A worktree cannot check
  out a branch already checked out in the primary tree, so keep it detached and sync files in.
- Sanity is separate from formatting and linting. Run the `black` and `ruff` skills on the
  same plugin file as well; sanity does not reformat and does not replace ruff's lint rules.
