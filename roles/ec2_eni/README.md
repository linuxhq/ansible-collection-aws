# ec2\_eni

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 network interfaces

## Requirements

None

## Role Variables

    ec2_eni_list: []
    ec2_eni_async: 300
    ec2_eni_batch: 10
    ec2_eni_delay: 3
    ec2_eni_poll: 0
    ec2_eni_retries: 100

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
              network_interfaces:
                - name: linuxhq-eni-1
                  private_ip_address:
                    "{{ ec2_vpc_subnet_list.0.subnets.0.cidr |
                        ansible.utils.ipaddr(10) |
                        ansible.utils.ipaddr('address') }}"

                - name: linuxhq-eni-2
                  private_ip_address:
                    "{{ ec2_vpc_subnet_list.0.subnets.0.cidr |
                        ansible.utils.ipaddr(11) |
                        ansible.utils.ipaddr('address') }}"

                - name: linuxhq-eni-3
                  device_index: 1
                  instance_id: "{{ _ec2_instance_info_dict['linuxhq-1'].instance_id }}"
                  private_ip_address:
                    "{{ ec2_vpc_subnet_list.0.subnets.0.cidr |
                        ansible.utils.ipaddr(20) |
                        ansible.utils.ipaddr('address') }}"
                  secondary_private_ip_addresses:
                    - "{{ ec2_vpc_subnet_list.0.subnets.0.cidr |
                          ansible.utils.ipaddr(21) |
                          ansible.utils.ipaddr('address') }}"
                  security_groups:
                    - "{{ _ec2_security_group_info_dict['linuxhq-ssh'].group_id }}"
                    - "{{ _ec2_security_group_info_dict['linuxhq-https'].group_id }}"

                - name: linuxhq-eni-4
                  device_index: 1
                  instance_id: "{{ _ec2_instance_info_dict['linuxhq-2'].instance_id }}"
                  private_ip_address:
                    "{{ ec2_vpc_subnet_list.0.subnets.0.cidr |
                        ansible.utils.ipaddr(30) |
                        ansible.utils.ipaddr('address') }}"
                  secondary_private_ip_addresses:
                    - "{{ ec2_vpc_subnet_list.0.subnets.0.cidr |
                          ansible.utils.ipaddr(31) |
                          ansible.utils.ipaddr('address') }}"
                  security_groups:
                    - "{{ _ec2_security_group_info_dict['linuxhq-ssh'].group_id }}"
                    - "{{ _ec2_security_group_info_dict['linuxhq-https'].group_id }}"

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
