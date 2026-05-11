# iam\_account\_alias\_info

Gather information about aws iam account aliases

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
