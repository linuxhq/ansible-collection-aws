# route\_table

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Configure route tables in aws virtual private clouds

## Requirements

None

## Role Variables

Available variables are listed below, along with default values:

    route_tables: []

## Dependencies

* [linuxhq.aws.subnet_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/subnet_info)
* [linuxhq.aws.vpc_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/vpc_info)

## Example Playbook

    - hosts: aws
      collections:
        - linuxhq.aws
      connection: local
      roles:
        - role: linuxhq.aws.route_table
          route_tables:
            - name: molecule-a
              routes:
                - dest: '0.0.0.0/0'
                  gateway_id: igw
              subnets:
                - "{{ _subnet_id['molecule-a'] }}"
              vpc_id: "{{ _vpc_id['molecule'] }}"

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
