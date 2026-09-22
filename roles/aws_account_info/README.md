# aws\_account\_info

Gather information about aws account

## Requirements

None

## Role Variables

    aws_account_info_account_id: null

## Return Values

    _aws_account_info_dict

## Dependencies

None

## Example Playbook

    - hosts: localhost
      connection: local
      roles:
        - linuxhq.aws.aws_account_info
