# AGENTS.md

Guidance for agents working in this repository.

## Overview

An Ansible collection of modules and roles, published to Galaxy on tag push.

| Path               | Description            |
| ------------------ | ---------------------- |
| `plugins/modules/` | Ansible python modules |
| `plugins/lookup/`  | Ansible lookup plugins |
| `roles/`           | Ansible roles          |

## Validation

Invoke the repository skills instead of reconstructing commands. Set up and activate the project
virtualenv first.

| Change                           | Required skills                                      |
| -------------------------------- | ---------------------------------------------------- |
| Any `.yml` or `.yaml` file       | `yamllint`                                           |
| Anything under `roles/`          | `ansible-lint`                                       |
| Anything under `plugins/`        | `black`, `ruff`, `ansible-test`                      |
| Changelog fragments or a release | `changelog`                                          |
| Collection metadata or packaging | `collection-build`                                   |
| A role's behavior                | `molecule`, only when explicitly authorized          |

Use the `pyenv` skill only when the interpreter in `.python-version` is unavailable. Use the
`virtualenv` skill before all other repository tooling.

## Imports

Rules live under `.agents/rules/`; do not add nested `AGENTS.md` files.

- @.agents/rules/helpers.md
- @.agents/rules/helpers-sdk.md
- @.agents/rules/module-authoring.md
- @.agents/rules/module-authoring-sdk.md
- @.agents/rules/role-authoring.md
