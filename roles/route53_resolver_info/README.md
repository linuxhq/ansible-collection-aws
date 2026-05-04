# route53\_resolver\_info

Gather information about aws route53 resolver endpoints

## Requirements

None

## Role Variables

    route53_resolver_info_name: null

## Return Values

    _route53_resolver_info_dict
    _route53_resolver_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_resolver_info
