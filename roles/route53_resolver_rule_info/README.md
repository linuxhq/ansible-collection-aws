# route53\_resolver\_rule\_info

Gather information about aws route53 resolver rules

## Requirements

None

## Role Variables

    route53_resolver_rule_info_name: null

## Return Values

    _route53_resolver_rule_info_dict
    _route53_resolver_rule_info_list

Returned rule objects include:

    associations
    vpc_ids

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_resolver_rule_info

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver_rule_info
          route53_resolver_rule_info_name: molecule-cloudflare
