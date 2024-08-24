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

An example playbook to build a vpc across three availability zones

    - hosts: aws
      connection: local
      vars:
        aws_network: 192.168.0.0/24
        aws_region: us-west-2
        aws_vpc: linuxhq

      roles:
        - linuxhq.aws.aws_az_info
        - linuxhq.aws.aws_caller_info
        - linuxhq.aws.aws_region_info

        - role: linuxhq.aws.ec2_vpc_dhcp_option
          ec2_vpc_dhcp_option_list:
            - name: "{{ aws_vpc }}"
              dns_servers:
                - 1.1.1.1
                - 1.1.1.2

        - role: linuxhq.aws.ec2_vpc_net
          ec2_vpc_net_list:
            - name: "{{ aws_vpc }}"
              cidr_block: "{{ aws_network }}"
              dhcp_options_id: "{{ _ec2_vpc_dhcp_option_info_dhcp_options_id[aws_vpc] }}"

        - role: linuxhq.aws.ec2_vpc_igw
          ec2_vpc_igw_list:
            - name: "{{ aws_vpc }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

        - role: linuxhq.aws.ec2_vpc_subnet
          ec2_vpc_subnet_list:
            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.0 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.0 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 0) }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.1 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.1 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 1) }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.2 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.2 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 2) }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.0 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.0 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 3) }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.1 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.1 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 4) }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.2 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.2 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 5) }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

        - role: linuxhq.aws.ec2_vpc_nat_gateway
          ec2_vpc_nat_gateway_list:
            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.0 }}"
              if_exist_do_not_create: true
              subnet_id: "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0] }}"
              wait: true

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.1 }}"
              if_exist_do_not_create: true
              subnet_id: "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1] }}"
              wait: true

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.2 }}"
              if_exist_do_not_create: true
              subnet_id: "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2] }}"
              wait: true

        - role: linuxhq.aws.ec2_vpc_route_table
          ec2_vpc_route_table_list:
            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.0 }}"
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id: igw
              subnets:
                - "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0] }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.1 }}"
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id: igw
              subnets:
                - "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1] }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.2 }}"
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id: igw
              subnets:
                - "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2] }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.0 }}"
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id:
                    "{{ _ec2_vpc_nat_gateway_info_nat_gateway_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0] }}"
              subnets:
                - "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.0] }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.1 }}"
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id:
                    "{{ _ec2_vpc_nat_gateway_info_nat_gateway_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1] }}"
              subnets:
                - "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.1] }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.2 }}"
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id:
                    "{{ _ec2_vpc_nat_gateway_info_nat_gateway_id[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2] }}"
              subnets:
                - "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.2] }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"
