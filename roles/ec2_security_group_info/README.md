# ec2\_security\_group\_info

Gather information about ec2 security groups

## Requirements

None

## Role Variables

    ec2_security_group_info_filters: {}

## Return Values

    _ec2_security_group_info_dict
    _ec2_security_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_security_group_info
