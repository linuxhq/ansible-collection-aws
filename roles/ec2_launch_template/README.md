# ec2\_launch\_template

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 launch templates

## Requirements

None

## Role Variables

    ec2_launch_template_list: []

## Return Values

    _ec2_launch_template_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_launch_template
          ec2_ami_info_list:
            - name: 'AlmaLinux OS 8'
              filters:
                owner-alias: aws-marketplace
                product-code: be714bpjscoj5uvqz0of5mscl
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm
          ec2_launch_template_list:
            - template_name: linuxhq-al8
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.medium
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['linuxhq-ssh'].group_id }}"


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
