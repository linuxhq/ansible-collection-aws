# rds\_subnet\_group\_info

Gather information about aws relational database service subnet groups

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

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
