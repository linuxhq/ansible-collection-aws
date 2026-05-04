# rds\_instance\_param\_group\_info

Gather information about aws rds instance parameter groups

## Requirements

None

## Role Variables

    rds_instance_param_group_info_db_parameter_group_name: null

## Return Values

    _rds_instance_param_group_info_dict
    _rds_instance_param_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.rds_instance_param_group_info
