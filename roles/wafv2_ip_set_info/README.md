# wafv2\_ip\_set\_info

Gather information about aws wafv2 ip sets

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    wafv2_ip_set_info_scope: regional

## Return Values

    _wafv2_ip_set_info_dict
    _wafv2_ip_set_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.wafv2_ip_set_info
