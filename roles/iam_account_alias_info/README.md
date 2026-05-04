# iam\_account\_alias\_info

Gather information about identity and access management account alias

## Requirements

None

## Role Variables

None

## Return Values

    _iam_account_alias_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.iam_account_alias_info
