# iam\_policy\_info

Gather information about identity and access management inline policies

## Requirements

None

## Role Variables

    iam_policy_info_group_names: []
    iam_policy_info_path_prefix: null
    iam_policy_info_policy_names: []
    iam_policy_info_user_names: []

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
