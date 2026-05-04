# notifications\_contacts\_info

Gather information about aws notifications contacts

## Requirements

None

## Role Variables

    notifications_contacts_info_name: null

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

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.notifications_contacts_info
          notifications_contacts_info_name: molecule-dummy01
