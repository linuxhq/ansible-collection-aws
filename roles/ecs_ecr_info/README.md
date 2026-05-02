# ecs\_ecr\_info

Gather information about aws elastic container registry repositories

## Requirements

None

## Role Variables

None

## Return Values

    _ecs_ecr_info_dict
    _ecs_ecr_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ecs_ecr_info
