# global\_accelerator\_info

Gather information about aws global accelerators

## Requirements

None

## Role Variables

    global_accelerator_info_arn: null
    global_accelerator_info_include_endpoint_groups: false
    global_accelerator_info_include_listeners: false

## Return Values

    _global_accelerator_info_dict
    _global_accelerator_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.global_accelerator_info
