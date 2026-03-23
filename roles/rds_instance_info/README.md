# rds\_instance\_info

Gather information about aws relational database service instances

## Requirements

None

## Role Variables

    rds_instance_info_db_instance_identifier: null
    rds_instance_info_filters: {}

## Return Values

    _rds_instance_info_dict
    _rds_instance_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.rds_instance_info
