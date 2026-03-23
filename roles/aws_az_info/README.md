# aws\_az\_info

Gather information about aws availability zones

## Requirements

None

## Role Variables

    aws_az_info_filters: {}

## Return Values

    _aws_az_info_dict
    _aws_az_info_list
    _aws_az_info_list_l
    _aws_az_info_list_s

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.aws_az_info
