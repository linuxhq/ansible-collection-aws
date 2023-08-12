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
      vars:
        aws_network: 192.168.0.0/24
        aws_region: us-west-1

      roles:
        - role: linuxhq.aws.vpc
          vpcs:
            - name: molecule
              cidr_block: "{{ aws_network }}"

        - role: linuxhq.aws.internet_gateway
          internet_gateways:
            - name: molecule
              vpc_id: "{{ _vpc_id['molecule'] }}"

        - role: linuxhq.aws.subnets
          subnets:
            - name: molecule-a
              az: "{{ aws_region ~ 'a' }}"
              cidr: "{{ aws_network }}"
              vpc_id: "{{ _vpc_id['molecule'] }}"

        - role: linuxhq.aws.route_table
          route_tables:
            - name: molecule-a
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id: igw
              subnets:
                - "{{ _subnet_id['molecule-a'] }}"
              vpc_id: "{{ _vpc_id['molecule'] }}"
