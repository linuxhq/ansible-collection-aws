# wafv2\_web\_acl\_info

Gather information about aws wafv2 web acls

## Requirements

None

## Role Variables

    wafv2_web_acl_info_id: null
    wafv2_web_acl_info_name: null
    wafv2_web_acl_info_scope: regional

## Return Values

    _wafv2_web_acl_info_dict
    _wafv2_web_acl_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.wafv2_web_acl_info
