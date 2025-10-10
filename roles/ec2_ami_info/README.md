# ec2\_ami\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about ec2 amazon machine images

## Requirements

None

## Role Variables

    ec2_ami_info_list: []

## Return Values

    _ec2_ami_info_dict
    _ec2_ami_info_latest
    _ec2_ami_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_ami_info
          ec2_ami_info_list:
            - name: 'AlmaLinux OS 8'
              filters:
                owner-alias: aws-marketplace
                product-code: be714bpjscoj5uvqz0of5mscl
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm

            - name: 'AlmaLinux OS 9'
              filters:
                owner-alias: aws-marketplace
                product-code: 3kukoxmnoighcsbjd0u4nq9ds
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm

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
