# rds\_option\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws relational database service option groups

## Requirements

None

## Role Variables

    rds_option_group_async: 300
    rds_option_group_batch: 10
    rds_option_group_delay: 3
    rds_option_group_list: []
    rds_option_group_poll: 0
    rds_option_group_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.rds_option_group
          rds_option_group_list:
            - engine_name: mariadb
              major_engine_version: 10.6
              option_group_name: mariadb106
              options:
                - option_name: MARIADB_AUDIT_PLUGIN
                  option_settings:
                    - name: SERVER_AUDIT_FILE_ROTATE_SIZE
                      value: '1000000'
                    - name: SERVER_AUDIT_FILE_ROTATIONS
                      value: '30'
                    - name: SERVER_AUDIT_QUERY_LOG_LIMIT
                      value: '1024'

            - engine_name: mariadb
              major_engine_version: 11.4
              option_group_name: mariadb114
              options:
                - option_name: MARIADB_AUDIT_PLUGIN
                  option_settings:
                    - name: SERVER_AUDIT_FILE_ROTATE_SIZE
                      value: '1000000'
                    - name: SERVER_AUDIT_FILE_ROTATIONS
                      value: '30'
                    - name: SERVER_AUDIT_QUERY_LOG_LIMIT
                      value: '1024'

            - engine_name: mariadb
              major_engine_version: 11.8
              option_group_name: mariadb118
              options:
                - option_name: MARIADB_AUDIT_PLUGIN
                  option_settings:
                    - name: SERVER_AUDIT_FILE_ROTATE_SIZE
                      value: '1000000'
                    - name: SERVER_AUDIT_FILE_ROTATIONS
                      value: '30'
                    - name: SERVER_AUDIT_QUERY_LOG_LIMIT
                      value: '1024'

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
