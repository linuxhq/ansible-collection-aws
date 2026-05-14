# ec2\_transit\_gateway\_route\_table\_info

Gather information about aws ec2 transit gateway route tables

## Requirements

None

## Role Variables

    ec2_transit_gateway_route_table_info_filters: {}
    ec2_transit_gateway_route_table_info_transit_gateway_route_table_ids: []

## Return Values

    _ec2_transit_gateway_route_table_info_dict
    _ec2_transit_gateway_route_table_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_transit_gateway_route_table_info
          ec2_transit_gateway_route_table_info_filters:
            state:
              - available
