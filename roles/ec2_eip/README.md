# ec2\_eip

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 elastic ip addresses

## Requirements

None

## Role Variables

    ec2_eip_list: []
    ec2_eip_async: 300
    ec2_eip_batch: 10
    ec2_eip_delay: 3
    ec2_eip_poll: 0
    ec2_eip_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_eni\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_eni_info)
* [linuxhq.aws.ec2\_instance\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_instance_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_eip
          ec2_eip_list:
            - name: linuxhq-eip-01
              device_id: "{{ _ec2_instance_info_dict['linuxhq-1'].instance_id }}"
              in_vpc: true
            - name: linuxhq-eip-02
              device_id: "{{ _ec2_instance_info_dict['linuxhq-2'].instance_id }}"
              in_vpc: true
            - name: linuxhq-eip-03
              device_id: "{{ _ec2_instance_info_dict['linuxhq-3'].instance_id }}"
              in_vpc: true
            - name: linuxhq-eip-04
              device_id: "{{ _ec2_instance_info_dict['linuxhq-4'].instance_id }}"
              in_vpc: true
            - name: linuxhq-eip-05
              device_id: "{{ _ec2_instance_info_dict['linuxhq-5'].instance_id }}"
              in_vpc: true

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
