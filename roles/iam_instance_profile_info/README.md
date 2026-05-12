# iam\_instance\_profile\_info

Gather information about aws iam instance profiles

## Requirements

None

## Role Variables

    iam_instance_profile_info_name: null
    iam_instance_profile_info_path_prefix: null

## Return Values

    _iam_instance_profile_info_dict
    _iam_instance_profile_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.iam_instance_profile_info
