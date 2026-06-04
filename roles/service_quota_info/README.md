# service\_quota\_info

Gather information about aws service quotas

## Requirements

None

## Role Variables

    service_quota_info_list: []

## Return Values

    _service_quota_info_dict
    _service_quota_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.service_quota_info
          service_quota_info_list: "{{ service_quota_list }}"
