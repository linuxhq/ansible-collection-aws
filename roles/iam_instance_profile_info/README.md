# iam\_instance\_profile\_info

Gather information about identity and access management instance profiles

## Requirements

None

## Role Variables

None

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
