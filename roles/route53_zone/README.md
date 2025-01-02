# route53\_zone

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws route53 zones

## Requirements

None

## Role Variables

    route53_zone_list: []

## Return Values

    _route53_zone_list

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.route53\_delegation\_set\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/route53_delegation_set_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_zone
          route53_zone_list:
            - zone: linuxhq.net
              delegation_set_id: "{{ _route53_delegation_set_info_dict[aws_vpc].Id }}"

            - zone: linuxhq.local
              vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"
              vpc_region: "{{ aws_region }}"

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
