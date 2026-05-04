# ssm\_parameter\_info

Gather information about aws systems manager key-value pairs

## Requirements

None

## Role Variables

    ssm_parameter_info_list: []
    ssm_parameter_info_on_denied: error
    ssm_parameter_info_on_missing: error

## Return Values

    _ssm_parameter_info_dict
    _ssm_parameter_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_parameter_info
          ssm_parameter_info_list: "{{ ssm_parameter_list }}"
