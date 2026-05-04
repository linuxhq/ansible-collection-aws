# route53\_delegation\_set

Manage aws route53 delegation sets

## Requirements

None

## Role Variables

    route53_delegation_set_async: 300
    route53_delegation_set_batch: 10
    route53_delegation_set_delay: 3
    route53_delegation_set_list: []
    route53_delegation_set_poll: 0
    route53_delegation_set_retries: 100

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
