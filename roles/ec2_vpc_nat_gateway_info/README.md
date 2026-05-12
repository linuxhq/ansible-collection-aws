# ec2\_vpc\_nat\_gateway\_info

Gather information about aws virtual private cloud nat gateways

## Requirements

None

## Role Variables

    ec2_vpc_nat_gateway_info_filters: {}
    ec2_vpc_nat_gateway_info_nat_gateway_ids: []

## Return Values

    _ec2_vpc_nat_gateway_info_dict
    _ec2_vpc_nat_gateway_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_nat_gateway_info
          ec2_vpc_nat_gateway_info_filters:
            state:
              - available
