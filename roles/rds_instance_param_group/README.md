# rds\_instance\_param\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws relational database service instance parameter groups

## Requirements

None

## Role Variables

    rds_instance_param_group_async: 300
    rds_instance_param_group_batch: 10
    rds_instance_param_group_delay: 3
    rds_instance_param_group_list: []
    rds_instance_param_group_poll: 0
    rds_instance_param_group_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.rds_instance_param_group
          rds_instance_param_group_list:
            - name: mariadb106
              engine: mariadb10.5
              immediate: true
              params:
                character_set_client: utf8mb4
                character_set_connection: utf8mb4
                character_set_database: utf8mb4
                character_set_results: utf8mb4
                character_set_server: utf8mb4
                collation_connection: utf8mb4_general_ci
                collation_server: utf8mb4_general_ci
                init_connect: SET NAMES utf8mb4 COLLATE utf8mb4_general_ci
                log_warnings: 2
                max_allowed_packet: 33554432

            - name: mariadb114
              engine: mariadb11.4
              immediate: true
              params:
                character_set_client: utf8mb4
                character_set_connection: utf8mb4
                character_set_database: utf8mb4
                character_set_results: utf8mb4
                character_set_server: utf8mb4
                collation_connection: utf8mb4_general_ci
                collation_server: utf8mb4_general_ci
                init_connect: SET NAMES utf8mb4 COLLATE utf8mb4_general_ci
                log_warnings: 2
                max_allowed_packet: 33554432

            - name: mariadb118
              engine: mariadb11.8
              immediate: true
              params:
                character_set_client: utf8mb4
                character_set_connection: utf8mb4
                character_set_database: utf8mb4
                character_set_results: utf8mb4
                character_set_server: utf8mb4
                collation_connection: utf8mb4_general_ci
                collation_server: utf8mb4_general_ci
                init_connect: SET NAMES utf8mb4 COLLATE utf8mb4_general_ci
                log_warnings: 2
                max_allowed_packet: 33554432

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
