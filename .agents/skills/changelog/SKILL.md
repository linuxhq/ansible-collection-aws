---
name: changelog
description: Manage changelog fragments and CHANGELOG.rst with antsibull-changelog from the project virtualenv. Add a fragment per user-facing change; release consumes fragments to cut a version.
---

# changelog

Record user-facing changes as YAML fragments in `changelogs/fragments/`; `antsibull-changelog`
(config `changelogs/config.yaml`) folds them into `CHANGELOG.rst`. Needs the `virtualenv` skill.

## Add a fragment

`changelogs/fragments/<name>.yml`, keyed by antsibull section (a list per section):

```yaml
minor_changes:
  - <module_or_role> - add X (https://github.com/.../pull/NNN).
```

Sections: `release_summary` (a string, prelude), `major_changes`, `minor_changes`,
`breaking_changes`, `deprecated_features`, `removed_features`, `security_fixes`, `bugfixes`,
`known_issues`, `trivial` (not rendered).

## Commands

```sh
venv/bin/antsibull-changelog lint       # check fragment syntax
venv/bin/antsibull-changelog generate   # re-render CHANGELOG.rst from recorded releases
venv/bin/antsibull-changelog release    # cut a version: fold in + consume fragments, re-render
```

`generate` does **not** touch fragments or show pending ones — only `release` records the
`galaxy.yml` version and (with `keep_fragments: false`) deletes the consumed fragments. Bump
`version` in `galaxy.yml` before `release`/tagging.
