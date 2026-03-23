# aws\_region\_info

Gather information about aws regions

## Requirements

None

## Role Variables

    aws_region_info_filters: {}

## Return Values

    _aws_region_info_dict
    _aws_region_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.aws_region_info
