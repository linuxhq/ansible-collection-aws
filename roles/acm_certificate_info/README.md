# acm\_certificate\_info

Gather information about aws certificate manager certificates

## Requirements

None

## Role Variables

    acm_certificate_info_certificate_arn: null
    acm_certificate_info_domain_name: null
    acm_certificate_info_statuses: []

## Return Values

    _acm_certificate_info_dict
    _acm_certificate_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.acm_certificate_info
