# route53\_resolver\_rule\_associate\_info

Gather information about aws route53 resolver rule associations

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _route53_resolver_rule_associate_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_resolver_rule_associate_info
