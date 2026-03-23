# route53\_delegation\_set\_info

Gather information about aws route53 delegation sets

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

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
