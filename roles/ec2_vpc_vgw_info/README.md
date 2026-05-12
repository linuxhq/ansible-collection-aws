# ec2\_vpc\_vgw\_info

Gather information about aws virtual private cloud vpn gateways

## Requirements

None

## Role Variables

    ec2_vpc_vgw_info_filters: {}
    ec2_vpc_vgw_info_vpn_gateway_ids: []

## Return Values

    _ec2_vpc_vgw_info_dict
    _ec2_vpc_vgw_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_vgw_info
          ec2_vpc_vgw_info_filters:
            state:
              - available
