# route53\_delegation\_set

Manage aws route53 delegation sets

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    route53_delegation_set_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_delegation_set
          route53_delegation_set_list:
            - name: molecule-01
            - name: molecule-02
            - name: molecule-03
