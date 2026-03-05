# ssm\_parameter

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws systems manager key-value pairs

## Requirements

None

## Role Variables

    ssm_parameter_async: 300
    ssm_parameter_batch: 10
    ssm_parameter_delay: 3
    ssm_parameter_list: []
    ssm_parameter_poll: 0
    ssm_parameter_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_igw\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_igw_info)
* [linuxhq.aws.ec2\_vpc\_nat\_gateway\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_nat_gateway_info)
* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_prefix\_list\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_prefix_list_info)
* [linuxhq.aws.ec2\_vpc\_route\_table\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_route_table_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_parameter
          ssm_parameter_list:
            - name: /molecule/vpc/id
              value: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

            - name: /molecule/vpc/igw/id
              value: "{{ _ec2_vpc_igw_info_dict['molecule'].internet_gateway_id }}"

            - name: /molecule/vpc/nat/id
              value: "{{ _ec2_vpc_nat_gateway_info_dict['molecule'].nat_gateway_id }}"

            - name: /molecule/vpc/rtb/a/id
              value: "{{ _ec2_vpc_route_table_info_dict['molecule-a'].route_table_id }}"

            - name: /molecule/vpc/rtb/b/id
              value: "{{ _ec2_vpc_route_table_info_dict['molecule-b'].route_table_id }}"

            - name: /molecule/vpc/subnet/a/id
              value: "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"

            - name: /molecule/vpc/subnet/b/id
              value: "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"

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
