# notifications\_contacts\_info

Gather information about aws notifications contacts

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.37.10

## Role Variables

None

## Return Values

    _notifications_contacts_info_dict
    _notifications_contacts_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.notifications_contacts_info
