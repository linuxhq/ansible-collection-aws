# efs

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws elastic filesystems

## Requirements

None

## Role Variables

    efs_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.efs
          efs_list:
            - name: linuxhq-efs1
              encrypt: true
              targets:
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-a'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-b'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-c'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['linuxhq'].id }}"

            - name: linuxhq-efs2
              encrypt: true
              rules:
                - cidr_ip: 10.0.0.0/8
                  ports:
                    - 2049
                  proto: tcp
              rules_egress:
                - cidr_ip: 10.0.0.0/8
                  ports:
                    - 0-65535
                  proto: tcp
              targets:
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-a'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-b'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-c'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['linuxhq'].id }}"

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
