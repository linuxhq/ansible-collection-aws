# ec2\_vpc\_subnet

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud subnets

## Requirements

None

## Role Variables

    ec2_vpc_subnet_list: []
    ec2_vpc_subnet_async: 300
    ec2_vpc_subnet_batch: 10
    ec2_vpc_subnet_delay: 3
    ec2_vpc_subnet_poll: 0
    ec2_vpc_subnet_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_subnet
          ec2_vpc_subnet_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"
              subnets:
                - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.0 }}"
                  az: "{{ aws_region ~ _aws_az_info_list_s.0 }}"
                  cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 0) }}"

                - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.1 }}"
                  az: "{{ aws_region ~ _aws_az_info_list_s.1 }}"
                  cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 1) }}"

                - name: "{{ aws_vpc }}-pub-{{ _aws_az_info_list_s.2 }}"
                  az: "{{ aws_region ~ _aws_az_info_list_s.2 }}"
                  cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 2) }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.0 }}"
                  az: "{{ aws_region ~ _aws_az_info_list_s.0 }}"
                  cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 3) }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.1 }}"
                  az: "{{ aws_region ~ _aws_az_info_list_s.1 }}"
                  cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 4) }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.2 }}"
                  az: "{{ aws_region ~ _aws_az_info_list_s.2 }}"
                  cidr: "{{ aws_network | ansible.utils.ipsubnet(27, 5) }}"

## License

Copyright (c) Linux HeadQuarters

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
