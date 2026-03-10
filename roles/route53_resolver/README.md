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

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver
          route53_resolver_list:
            - name: molecule-cloudflare
              direction: outbound
              ip_addresses:
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.0.name].id }}"
                  Ip: 192.168.0.125
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.1.name].id }}"
                  Ip: 192.168.0.253
              vpc_id: "{{ _ec2_vpc_net_info_dict[ec2_vpc_net_list.0.name].id }}"

            - name: molecule-google
              direction: outbound
              ip_addresses:
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.0.name].id }}"
                  Ip: 192.168.0.126
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.1.name].id }}"
                  Ip: 192.168.0.254
              rules:
                - cidr_ip: 192.168.0.0/24
                  ports:
                    - 53
                  proto: tcp
                - cidr_ip: 192.168.0.0/24
                  ports:
                    - 53
                  proto: udp
              rules_egress:
                - cidr_ip: 192.168.0.0/24
                  proto: -1
              vpc_id: "{{ _ec2_vpc_net_info_dict[ec2_vpc_net_list.0.name].id }}"

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
