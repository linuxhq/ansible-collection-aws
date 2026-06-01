# iam\_policy\_info

Gather information about aws iam inline policies

## Requirements

None

## Role Variables

    iam_policy_info_group_name: null
    iam_policy_info_path_prefix: null
    iam_policy_info_policy_name: null
    iam_policy_info_user_name: null

## Return Values

    _iam_policy_info_group_dict
    _iam_policy_info_group_list
    _iam_policy_info_user_dict
    _iam_policy_info_user_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.iam_policy_info
