# rds\_option\_group\_info

Gather information about aws rds option groups

## Requirements

None

## Role Variables

    rds_option_group_info_engine_name: null
    rds_option_group_info_major_engine_version: null
    rds_option_group_info_marker: null
    rds_option_group_info_max_records: 100
    rds_option_group_info_option_group_name: null

## Return Values

    _rds_option_group_info_dict
    _rds_option_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.rds_option_group_info
