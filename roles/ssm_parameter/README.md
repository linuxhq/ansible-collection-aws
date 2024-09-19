# ssm\_parameter

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws systems manager key-value pairs

## Requirements

None

## Role Variables

    ssm_parameter_list: []

## Return Values

    _ssm_parameter_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_parameter
          ssm_parameter_list:
            - name: /linuxhq/openssh/key/pub
              string_type: SecureString
              value: "{{ openssh_key_pub }}"

            - name: /linuxhq/region
              value: "{{ aws_region }}"

            - name: /linuxhq/vpc/id
              value: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"

            - name: /linuxhq/igw/id
              value: "{{ _ec2_vpc_igw_info_dict[aws_vpc].internet_gateway_id }}"

            - name: "/linuxhq/subnet/pub/{{ _aws_az_info_list_s.0 }}/id"
              value: "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].id }}"

            - name: "/linuxhq/subnet/pub/{{ _aws_az_info_list_s.1 }}/id"
              value: "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].id }}"

            - name: "/linuxhq/subnet/pub/{{ _aws_az_info_list_s.2 }}/id"
              value: "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].id }}"

            - name: "/linuxhq/subnet/pvt/{{ _aws_az_info_list_s.0 }}/id"
              value: "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.0].id }}"

            - name: "/linuxhq/subnet/pvt/{{ _aws_az_info_list_s.1 }}/id"
              value: "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.1].id }}"

            - name: "/linuxhq/subnet/pvt/{{ _aws_az_info_list_s.2 }}/id"
              value: "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.2].id }}"

            - name: "/linuxhq/nat/pub/{{ _aws_az_info_list_s.0 }}/id"
              value: "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].nat_gateway_id }}"

            - name: "/linuxhq/nat/pub/{{ _aws_az_info_list_s.1 }}/id"
              value: "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].nat_gateway_id }}"

            - name: "/linuxhq/nat/pub/{{ _aws_az_info_list_s.2 }}/id"
              value: "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].nat_gateway_id }}"

            - name: "/linuxhq/rtb/pub/{{ _aws_az_info_list_s.0 }}/id"
              value: "{{ _ec2_vpc_route_table_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].route_table_id }}"

            - name: "/linuxhq/rtb/pub/{{ _aws_az_info_list_s.1 }}/id"
              value: "{{ _ec2_vpc_route_table_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].route_table_id }}"

            - name: "/linuxhq/rtb/pub/{{ _aws_az_info_list_s.2 }}/id"
              value: "{{ _ec2_vpc_route_table_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].route_table_id }}"

            - name: "/linuxhq/rtb/pvt/{{ _aws_az_info_list_s.0 }}/id"
              value: "{{ _ec2_vpc_route_table_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.0].route_table_id }}"

            - name: "/linuxhq/rtb/pvt/{{ _aws_az_info_list_s.1 }}/id"
              value: "{{ _ec2_vpc_route_table_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.1].route_table_id }}"

            - name: "/linuxhq/rtb/pvt/{{ _aws_az_info_list_s.2 }}/id"
              value: "{{ _ec2_vpc_route_table_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.2].route_table_id }}"

            - name: /linuxhq/pl/cloudflare-ipv4
              value: "{{ _ec2_vpc_prefix_list_info_dict['cloudflare-ipv4'].PrefixListId }}"

            - name: /linuxhq/pl/cloudflare-ipv6
              value: "{{ _ec2_vpc_prefix_list_info_dict['cloudflare-ipv6'].PrefixListId }}"

            - name: /linuxhq/pl/linuxhq
              value: "{{ _ec2_vpc_prefix_list_info_dict['linuxhq'].PrefixListId }}"

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
