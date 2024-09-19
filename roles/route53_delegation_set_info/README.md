# route53\_delegation\_set\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about route53 delegation sets

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _route53_delegation_set_info_id
    _route53_delegation_set_info_list
    _route53_delegation_set_info_name_servers

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_delegation_set_info

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