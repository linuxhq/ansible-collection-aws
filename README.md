# linuxhq.aws

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)
[![Ansible Galaxy](https://img.shields.io/badge/collection-linuxhq.aws-blue)](https://galaxy.ansible.com/linuxhq/aws)
[![Lint](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/linting.yml/badge.svg)](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/linting.yml)
[![Release](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/release.yml/badge.svg)](https://github.com/linuxhq/ansible-collection-aws/actions/workflows/release.yml)

A collection of aws roles

# Collection

## Build

    ansible-galaxy collection build

## Install

    ansible-galaxy collection install linuxhq.aws

## Molecule

    /usr/bin/python3 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt

# Playbook

An example playbook utilizing roles available in this collection

    - hosts: aws
      collections:
        - linuxhq.aws
      connection: local
