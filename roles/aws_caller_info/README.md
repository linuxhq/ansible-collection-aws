# aws\_caller\_info

Gather information about aws caller identity

## Requirements

None

## Role Variables

None

## Return Values

    _aws_caller_info_account
    _aws_caller_info_account_alias
    _aws_caller_info_arn
    _aws_caller_info_user_id

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.aws_caller_info
