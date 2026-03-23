# route53\_zone\_info

Gather information about aws route53 zones

## Requirements

None

## Role Variables

None

## Return Values

    _route53_zone_info_dict
    _route53_zone_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.route53_zone_info
