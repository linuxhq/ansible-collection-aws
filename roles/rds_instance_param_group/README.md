# rds\_instance\_param\_group

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
