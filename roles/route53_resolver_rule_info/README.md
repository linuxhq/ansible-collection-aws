# route53\_resolver\_rule\_info

Gather information about aws route53 resolver rules

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _route53_resolver_rule_info_dict
    _route53_resolver_rule_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_resolver_rule_info
