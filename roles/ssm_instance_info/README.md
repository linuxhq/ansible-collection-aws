# ssm\_instance\_info

Gather information about aws systems manager instances

## Requirements

None

## Role Variables

    ssm_instance_info_filters: {}
    ssm_instance_info_instance_ids: []
    ssm_instance_info_ping_status: null

## Return Values

    _ssm_instance_info_dict
    _ssm_instance_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_instance_info
          ssm_instance_info_instance_ids:
            - i-0123456789abcdef0
          ssm_instance_info_ping_status: Online
