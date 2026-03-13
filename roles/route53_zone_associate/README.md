# route53\_zone\_associate

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws route53 zone associations

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    route53_zone_associate_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.route53\_zone\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/route53_zone_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_zone_associate
          route53_zone_associate_list:
            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.0.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-2'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.1.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-2'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.0.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-3'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.1.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-3'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

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
