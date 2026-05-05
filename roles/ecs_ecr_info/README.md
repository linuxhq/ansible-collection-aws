# ecs\_ecr\_info

Gather information about aws elastic container registry repositories

## Requirements

    ecs_ecr_info_name: null

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
        - role: linuxhq.aws.ecs_ecr_info
          ecs_ecr_info_name: molecule-00
