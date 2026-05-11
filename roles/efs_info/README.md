# efs\_info

Gather information about aws elastic filesystems

## Requirements

None

## Role Variables

    efs_info_id: null
    efs_info_name: null
    efs_info_tags: {}
    efs_info_targets: []

## Return Values

    _efs_info_dict
    _efs_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.efs_info
