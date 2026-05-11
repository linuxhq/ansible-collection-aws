# ec2\_instance\_type\_info

Gather information about aws instance types

## Requirements

None

## Role Variables

    ec2_instance_type_info_filters: {}
    ec2_instance_type_info_instance_types: []

## Return Values

    _ec2_instance_type_info_dict
    _ec2_instance_type_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_instance_type_info
          ec2_instance_type_info_instance_types:
            - t3.micro
            - t3.small
