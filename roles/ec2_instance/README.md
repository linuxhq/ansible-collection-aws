# ec2\_instance

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 instances

## Requirements

None

## Role Variables

    ec2_instance_list: []
    ec2_instance_async: 600
    ec2_instance_batch: 10
    ec2_instance_delay: 3
    ec2_instance_poll: 0
    ec2_instance_retries: 300

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_ami\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_ami_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_instance
          ec2_ami_info_list:
            - name: 'AlmaLinux OS 9'
              filters:
                owner-alias: aws-marketplace
                product-code: 3kukoxmnoighcsbjd0u4nq9ds
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm

          ec2_instance_list:
            - name: linuxhq-1
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.small
              vpc_subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-pvt-a'].id }}"

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
