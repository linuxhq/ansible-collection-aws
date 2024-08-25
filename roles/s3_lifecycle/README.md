# s3\_lifecycle

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws simple storage service bucket lifecycle rules

## Requirements

None

## Role Variables

Available variables are listed below, along with default values:

    s3_lifecycle_list: []

## Return Values

    _s3_lifecycle_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_lifecycle
          s3_lifecycle_list:
            - name: "{{ _aws_caller_info_account }}-{{ aws_region }}-linuxhq-backups"
              rules:
                - rule_id: linuxhq-30d-glacier
                  transition_days: 30
                  prefix: 30d/
                  status: enabled
                  storage_class: glacier
                - rule_id: linuxhq-90d-glacier
                  transition_days: 90
                  prefix: 90d/
                  status: enabled
                  storage_class: glacier
                - rule_id: linuxhq-365d-glacier
                  transition_days: 365
                  prefix: 365d/
                  status: enabled
                  storage_class: glacier

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
