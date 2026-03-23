# iam\_account\_alias

Manage aws identity and access management account alias

## Requirements

* [awscli](https://pypi.org/project/awscli)

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
          iam_account_alias_name: "molecule-{{ ansible_date_time.date }}"
