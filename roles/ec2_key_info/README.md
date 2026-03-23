# ec2\_key\_info

Gather information about ec2 keys

## Requirements

None

## Role Variables

    ec2_key_info_filters: {}
    ec2_key_info_ids: []
    ec2_key_info_include_public_key: false
    ec2_key_info_names: []

## Return Values

    _ec2_key_info_dict
    _ec2_key_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_key_info
