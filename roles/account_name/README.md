# account\_name

Manage aws account name

## Requirements

None

## Role Variables

    account_name_account_id: null
    account_name_name: null

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: localhost
      connection: local
      roles:
        - role: linuxhq.aws.account_name
          account_name_name: production
