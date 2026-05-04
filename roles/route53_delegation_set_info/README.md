# route53\_delegation\_set\_info

Gather information about aws route53 delegation sets

## Requirements

None

## Role Variables

    route53_delegation_set_info_name: null

## Return Values

    _route53_delegation_set_info_dict
    _route53_delegation_set_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_delegation_set_info
