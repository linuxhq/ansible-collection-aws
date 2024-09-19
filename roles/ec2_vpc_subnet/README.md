# ec2\_vpc\_subnet

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud subnets

## Requirements

None

## Role Variables

    ec2_vpc_subnet_list: []

## Return Values

    _ec2_vpc_subnet_list

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_subnet
          ec2_vpc_subnet_list:
            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.0 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.0 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 0) }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.1 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.1 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 1) }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

            - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.2 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.2 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 2) }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.0 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.0 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 3) }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.1 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.1 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 4) }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

            - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.2 }}"
              az: "{{ aws_region ~ _aws_az_info_list_s.2 }}"
              cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 5) }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

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
