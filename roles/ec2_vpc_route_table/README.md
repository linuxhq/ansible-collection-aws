# ec2\_vpc\_route\_table

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud route tables

## Requirements

None

## Role Variables

    ec2_vpc_route_table_list: []
    ec2_vpc_route_table_async: 300
    ec2_vpc_route_table_batch: 10
    ec2_vpc_route_table_delay: 3
    ec2_vpc_route_table_poll: 0
    ec2_vpc_route_table_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_nat\_gateway\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_nat_gateway_info)
* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_route_table
          ec2_vpc_route_table_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"
              route_tables:
                - name: "{{ aws_vpc }}-pub"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id: igw
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].id }}"
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].id }}"
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].id }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.0 }}"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id:
                        "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].nat_gateway_id }}"
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.0].id }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.1 }}"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id:
                        "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].nat_gateway_id }}"
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.1].id }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.2 }}"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id:
                        "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].nat_gateway_id }}"
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.2].id }}"

## License

Copyright (C) 2025 Linux HeadQuarters

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
