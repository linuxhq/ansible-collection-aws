# ec2\_vpc\_route\_table\_info

Gather information about aws virtual private cloud route tables

## Requirements

None

## Role Variables

    ec2_vpc_route_table_info_filters: {}

## Return Values

    _ec2_vpc_route_table_info_dict
    _ec2_vpc_route_table_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_vpc_route_table_info
