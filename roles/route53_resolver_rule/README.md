# route53\_resolver\_rule

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws route53 resolver rules

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    route53_resolver_rule_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.route53\_resolver\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/route53_resolver_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver_rule
          route53_resolver_rule_list:
            - name: "{{ aws_vpc }}-cloudflare"
              domain_name: linuxhq.net
              resolver_endpoint_id: "{{ _route53_resolver_info_dict[aws_vpc ~ '-outbound'].Id }}"
              rule_type: forward
              target_ips:
                - Ip: 1.1.1.1
                  Port: 53
                - Ip: 1.1.1.2
                  Port: 53

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
