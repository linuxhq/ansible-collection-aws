# route53\_resolver\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about route53 resolvers

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _route53_resolver_info_direction
    _route53_resolver_info_host_vpc_id
    _route53_resolver_info_id
    _route53_resolver_info_ip_address_count
    _route53_resolver_info_list
    _route53_resolver_info_resolver_endpoint_type
    _route53_resolver_info_security_group_ids
    _route53_resolver_info_status

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_resolver_info

## License

Copyright (C) 2023 Linux HeadQuarters

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