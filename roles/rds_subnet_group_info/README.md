# rds\_subnet\_group\_info

Gather information about aws rds subnet groups

## Requirements

None

## Role Variables

    rds_subnet_group_info_filters: {}
    rds_subnet_group_info_name: null

## Return Values

    _rds_subnet_group_info_dict
    _rds_subnet_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.rds_subnet_group_info
