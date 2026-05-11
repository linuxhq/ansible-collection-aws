# ec2\_eip\_info

Gather information about aws elastic ips

## Requirements

None

## Role Variables

    ec2_eip_info_filters: {}

## Return Values

    _ec2_eip_info_dict
    _ec2_eip_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_eip_info
