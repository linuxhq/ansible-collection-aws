# ecs\_ecr\_info

Gather information about aws elastic container registry repositories

## Requirements

None

## Role Variables

    ecs_ecr_info_repository_names: []
    ecs_ecr_info_registry_id: null

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
          ecs_ecr_info_repository_names:
            - molecule-00
