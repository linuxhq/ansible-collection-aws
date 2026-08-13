# linuxhq.aws

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)
[![Ansible Galaxy](https://img.shields.io/badge/collection-linuxhq.aws-blue)](https://galaxy.ansible.com/linuxhq/aws)
[![Lint](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/pre-commit.yml)
[![Release](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/release.yml/badge.svg)](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/release.yml)

An Ansible collection of AWS modules and roles.

## Installation

```sh
ansible-galaxy collection install linuxhq.aws
```

## Development

With Tox installed, install the pre-commit hook:

```sh
tox run -e pre-commit
```

Tox manages isolated environments under `.tox/`; no environment activation is required.

### Checks

Run the default lint suite:

```sh
tox
```

Run or fix individual checks:

```sh
tox run -e ansible-lint
tox run -e yamllint
tox run -e black-lint
tox run -e ruff-lint
tox run -e black
tox run -e ruff
```

Run Ansible sanity tests for a module:

```sh
tox run -e ansible-test -- sanity --python 3.13 plugins/modules/account_region.py
```

### Molecule

Each role has a Molecule scenario that also serves as an example playbook. Set `MOLECULE_ROLE`
to select a role:

```sh
MOLECULE_ROLE=account_region tox run -e molecule -- test -s default
```

Molecule scenarios may create real AWS resources and incur costs.

### Changelog and build

```sh
tox run -e changelog -- generate
tox run -e build
```
