# ec2\_vpc\_nat\_gateway

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud nat gateways

## Requirements

None

## Role Variables

Available variables are listed below, along with default values:

    ec2_vpc_nat_gateway_list: []

## Return Values

    _ec2_vpc_nat_gateway_list

## Dependencies

* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
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


## License

Copyright (C) 2023 Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.