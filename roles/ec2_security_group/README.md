# ec2\_security\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 security groups

## Requirements

None

## Role Variables

    ec2_security_group_list: []
    ec2_security_group_async: 300
    ec2_security_group_batch: 10
    ec2_security_group_delay: 3
    ec2_security_group_poll: 0
    ec2_security_group_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_prefix\_list\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_prefix_list_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_security_group
          ec2_security_group_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"
                - name: "{{ aws_vpc }}-ssh"
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 22
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1

                - name: "{{ aws_vpc }}-https"
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 443
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1

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
