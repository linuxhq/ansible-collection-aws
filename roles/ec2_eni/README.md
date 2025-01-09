# ec2\_eni

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 network interfaces

## Requirements

None

## Role Variables

    ec2_eni_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_instance\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_instance_info)
* [linuxhq.aws.ec2\_security\_group\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_security_group_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_eni
          ec2_eni_list:
            - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-pvt-a'].id }}"
              security_groups:
                - "{{ _ec2_security_group_info_dict['linuxhq-ssh'].group_id }}"
              network_interfaces:
                - name: linuxhq-eni-1
                  private_ip_address: 192.168.0.100
                - name: linuxhq-eni-2
                  delete_on_termination: true
                  device_index: 1
                  instance_id: "{{ _ec2_instance_info_dict['linuxhq-instance-1'].instance_id }}"
                  private_ip_address: 192.168.0.101
                  secondary_private_ip_addresses:
                    - 192.168.0.102
                  security_groups:
                    - "{{ _ec2_security_group_info_dict['linuxhq-ssh'].group_id }}"
                    - "{{ _ec2_security_group_info_dict['linuxhq-https'].group_id }}"


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
