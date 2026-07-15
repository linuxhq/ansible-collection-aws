# AGENTS.md

Guidance for agents working in this repository.

## Overview

An Ansible collection of AWS modules and roles, published to Galaxy on tag push.

| Path               | Description                                 |
| ------------------ | ------------------------------------------- |
| `plugins/modules/` | New Python AWS modules (resource + `_info`) |
| `plugins/lookup/`  | Python lookup plugins                       |
| `roles/`           | List-driven wrappers over AWS modules       |

## Rules

Always-on rules in `.agents/rules/`, `@` - imported per file

@.agents/rules/helpers.md
@.agents/rules/module-authoring.md
@.agents/rules/module-docs.md
@.agents/rules/role-authoring.md

| Rule                  | Covers                                                     |
| --------------------- | ---------------------------------------------------------- |
| `helpers.md`          | `module_utils` helper reference                            |
| `module-authoring.md` | Module structure, behavior, arguments, operations, results |
| `module-docs.md`      | Doc / `argument_spec` alignment                            |
| `role-authoring.md`   | Role layout, patterns, naming                              |

## Tooling

All tools run from a local `venv/`. Each task has a skill — invoke it rather than
running commands ad hoc.

| Skill              | Purpose                       |
| ------------------ | ----------------------------- |
| `virtualenv`       | Set up the venv               |
| `ansible-lint`     | Lint roles & playbooks        |
| `yamllint`         | Lint YAML                     |
| `black`            | Format Python                 |
| `ruff`             | Lint Python                   |
| `ansible-test`     | Module sanity                 |
| `molecule`         | Role tests                    |
| `changelog`        | Changelog fragments & release |
| `collection-build` | Build the collection tarball  |
