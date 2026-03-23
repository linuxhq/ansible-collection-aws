# iam\_user\_info

Gather information about iam users

## Requirements

None

## Role Variables

    iam_user_info_group: null
    iam_user_info_name: null
    iam_user_info_path_prefix: null

## Return Values

    _iam_user_info_dict
    _iam_user_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.iam_user_info
