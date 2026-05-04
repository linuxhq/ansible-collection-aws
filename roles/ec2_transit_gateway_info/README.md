# ec2\_transit\_gateway\_info

Gather information about ec2 transit gateways

## Requirements

None

## Role Variables

    ec2_transit_gateway_info_filters: {}
    ec2_transit_gateway_info_transit_gateway_ids: []

## Return Values

    _ec2_transit_gateway_info_dict
    _ec2_transit_gateway_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_transit_gateway_info
          ec2_transit_gateway_info_filters:
            state:
              - available
