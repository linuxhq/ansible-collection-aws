# route53\_resolver

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws route53 resolvers

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    route53_resolver_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver
          route53_resolver_list:
            - name: "{{ aws_vpc }}-outbound"
              direction: outbound
              ip_addresses:
                - SubnetId: "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.0] }}"
                  Ip:
                    "{{ aws_network |
                        ansible.utils.ipsubnet(27, 3) |
                        ansible.utils.ipaddr('last_usable') }}"
                - SubnetId: "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.1] }}"
                  Ip:
                    "{{ aws_network |
                        ansible.utils.ipsubnet(27, 4) |
                        ansible.utils.ipaddr('last_usable') }}"
                - SubnetId: "{{ _ec2_vpc_subnet_info_subnet_id[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.2] }}"
                  Ip:
                    "{{ aws_network |
                        ansible.utils.ipsubnet(27, 5) |
                        ansible.utils.ipaddr('last_usable') }}"
              vpc_id: "{{ _ec2_vpc_net_info_id[aws_vpc] }}"

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
