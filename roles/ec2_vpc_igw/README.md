# ec2\_vpc\_igw

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud internet gateways

## Requirements

None

## Role Variables

    ec2_vpc_igw_list: []
    ec2_vpc_igw_async: 300
    ec2_vpc_igw_batch: 10
    ec2_vpc_igw_delay: 3
    ec2_vpc_igw_poll: 0
    ec2_vpc_igw_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_igw
          ec2_vpc_igw_list:
            - name: linuxhq
              vpc_id: "{{ _ec2_vpc_net_info_dict['linuxhq'].id }}"

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
