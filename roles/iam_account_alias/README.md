# iam\_account\_alias

Manage aws iam account alias

## Requirements

None

## Role Variables

    iam_account_alias_name: null
    iam_account_alias_state: present

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_account_alias
          iam_account_alias_name: "molecule-{{ ansible_facts.date_time.date }}"
