# notifications\_hub\_info

Gather information about aws notifications hubs

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.37.10

## Role Variables

None

## Return Values

    _notifications_hub_info_dict
    _notifications_hub_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.notifications_hub_info
