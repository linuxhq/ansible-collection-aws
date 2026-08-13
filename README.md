# linuxhq.aws

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)
[![Ansible Galaxy](https://img.shields.io/badge/collection-linuxhq.aws-blue)](https://galaxy.ansible.com/linuxhq/aws)
[![Lint](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/pre-commit.yml)
[![Release](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/release.yml/badge.svg)](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/release.yml)

A collection of aws roles

# Collection

## Environment

    tox run -e pre-commit

## Build

    tox run -e build

## Install

    ansible-galaxy collection install linuxhq.aws

## Changelog

    tox run -e changelog -- generate

## Linting

    tox run -e ansible-lint
    tox run -e yamllint

## Testing

All roles have molecule tests which provide example playbooks

    MOLECULE_ROLE=account_region tox run -e molecule -- test -s default
