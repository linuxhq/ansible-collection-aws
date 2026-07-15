# CLAUDE.md

This file provides guidance to agents when working with code in this repository.

## Rules

Always-on rules live in `.agents/rules/`. Read and apply each of them. `@`-imports are
per-file (no globbing), so add a line here whenever you add a rule file to that directory.

@.agents/rules/helpers.md

## What this is

`linuxhq.aws` is an Ansible collection (namespace `linuxhq`, name `aws`) that extends the
official `amazon.aws` (9.5.2) and `community.aws` (9.3.0) collections with additional AWS
modules and a large library of roles. It targets `ansible-core` 2.18+ and Python 3.12, and
is published to Ansible Galaxy on tag push.

The two deliverables are:
- **Plugins** in `plugins/modules/` (64 modules), `plugins/lookup/` — new Python AWS modules.
- **Roles** in `roles/` (~158 roles) — thin, list-driven wrappers that call `linuxhq.aws`,
  `amazon.aws`, and `community.aws` modules. Most roles just orchestrate existing modules;
  only a subset back a `linuxhq.aws` module authored in this repo.

## Environment & common commands

The Makefile bootstraps a local `venv/` with pinned tooling from `requirements.txt`. All
tool invocations below assume `venv/bin/…` (or an activated venv).

```sh
make                       # create venv, install python deps, galaxy deps, pre-commit hook
source venv/bin/activate
```

Lint / format (these are what CI enforces via pre-commit):
```sh
venv/bin/ansible-lint                 # whole tree; molecule/ and venv/ excluded
venv/bin/ansible-lint roles/<role>    # single role
venv/bin/yamllint --strict .          # strict YAML lint
venv/bin/black plugins                # format modules; CI runs --check
venv/bin/pre-commit run --all-files   # run the full CI lint suite locally
```

Molecule (role tests — every role has a `molecule/default/` scenario that doubles as an
example playbook). Run from the role directory; scenarios hit real AWS:
```sh
cd roles/<role> && ../../venv/bin/molecule test -s default
../../venv/bin/molecule converge -s default   # just the present path, no teardown
```

Build & release:
```sh
ansible-galaxy collection build      # produces linuxhq-aws-<version>.tar.gz
antsibull-changelog generate         # regenerate CHANGELOG.rst from changelogs/fragments/
```

Releasing is tag-driven: pushing a git tag triggers `.github/workflows/release.yml`, which
builds and publishes to Galaxy. Bump `version` in `galaxy.yml` before tagging.

### ansible-test sanity (module changes)

`ansible-test` resolves the physical path and requires the collection to live at
`ansible_collections/linuxhq/aws/`. Run sanity from a real checkout at that path (symlinks
do not work), e.g. via a `git worktree` under `venv/ansible_collections/linuxhq/aws`, then:
```sh
ansible-test sanity --python 3.12
```

## Module architecture (plugins/modules/)

Most resource modules come as a manager/`_info` pair (e.g. `iam_account_alias.py` +
`iam_account_alias_info.py`), though not every module has both halves. Study a nearby
module before adding one — the patterns below are the prevailing house style to match, not
a hard spec; follow what the closest existing modules actually do.

- **Structure**: top-of-file `DOCUMENTATION` / `EXAMPLES` / `RETURN` r-strings, then imports,
  then `ensure_present` / `ensure_absent` (or list/info) helpers, then `main()`. `main()`
  builds the `AnsibleAWSModule`, dispatches on `state`, and calls the helpers.
- **Base class**: `AnsibleAWSModule` from
  `ansible_collections.amazon.aws.plugins.module_utils.modules`. All modules
  `extends_documentation_fragment` the `amazon.aws.common.modules`, `amazon.aws.region.modules`,
  and `amazon.aws.boto3` fragments.
- **Clients & retries**: every module creates its client with
  `module.client("<svc>", retry_decorator=AWSRetry.jittered_backoff())` and passes
  `aws_retry=True` on individual calls. For paginated list/describe, most modules use
  `paginated_query_with_retries` (from `amazon.aws...module_utils.botocore`) rather than
  hand-rolled paginators.
- **SDK capability checks**: many modules have `main()` validate botocore support with
  `get_boto3_client_method_parameters()` before dispatching, `fail_json`-ing on the
  unsupported service method/parameter (see `iam_account_alias.py:main`). Use it when a
  module relies on newer boto3/botocore APIs.
- **Check mode**: `supports_check_mode=True`; never make mutating calls when
  `module.check_mode`; still return the predicted result shape.
- **snake_case**: module params and returned data are snake_case; transform to/from boto3's
  CamelCase using the `amazon.aws` dict-transformation helpers. Wrap API failures with
  `module.fail_json_aws(e, msg=...)`, including the resource identifier.

## Role architecture (roles/)

Roles come in two flavors and mostly share the same layout (`tasks/`, `defaults/`, `meta/`,
`README.md`, `molecule/default/`). Match the structure of nearby roles rather than treating
any single shape as required.

**Manager roles** are usually list-driven: `tasks/main.yml` injects defaults (e.g.
`state: present`) into a caller-supplied `*_list` var, then `include_tasks` `include.yml`
per item with a `loop_var` and `apply.tags` so tagged runs reach child tasks, and
`include.yml` calls the actual AWS module (see `roles/sns_topic`). Simpler roles that manage
a single resource skip the list/`include.yml` split and call the module directly in
`main.yml` (see `roles/iam_account_alias`). Common conventions across manager roles:
- Tasks carry the role-name tag, and `include_tasks` uses `apply.tags`.
- Optional per-item values use `| d(omit)`; `purge_*` booleans are pinned with `d(true)`/
  `d(false)`, **not** `d(omit)` (see `roles/sns_topic/tasks/include.yml`).
- AWS module calls set `validate_certs: true`.
- A `Name` tag is merged into `tags` for taggable resources.

**Info roles** call the matching `_info` module, register the result, and publish
snake_case facts named `_<role>_info_list` (and a `_dict` variant when the data has a stable
name/key). These `_`-prefixed facts are the established role outputs — see
`roles/iam_account_alias_info/tasks/main.yml`.

Role variables are prefixed with the role name; resource lists default to `[]`. Keep
`README.md`, `defaults/main.yml`, and `meta/main.yml` aligned when changing variables,
defaults, dependencies, or return facts.

## Changelog

Changes are recorded as fragments in `changelogs/fragments/` and combined into
`CHANGELOG.rst` by `antsibull-changelog` (config in `changelogs/config.yaml`,
`keep_fragments: false`). Sections follow the standard antsibull set (minor_changes,
bugfixes, breaking_changes, etc.).
