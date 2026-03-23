# ec2\_vpc\_subnet\_info

Gather information about virtual private cloud subnets

## Requirements

None

## Role Variables

    ec2_vpc_subnet_info_filters: {}
    ec2_vpc_subnet_info_subnet_ids: []

## Return Values

    _ec2_vpc_subnet_info_dict
    _ec2_vpc_subnet_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_vpc_subnet_info
