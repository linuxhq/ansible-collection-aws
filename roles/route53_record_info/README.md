# route53\_record\_info

Gather information about aws route53 records

## Requirements

None

## Role Variables

None

## Return Values

    _route53_record_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_record_info
