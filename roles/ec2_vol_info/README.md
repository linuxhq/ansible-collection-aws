# ec2\_vol\_info

Gather information about aws ec2 volumes

## Requirements

None

## Role Variables

    ec2_vol_info_filters: {}

## Return Values

    _ec2_vol_info_dict
    _ec2_vol_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_vol_info
