# ec2\_vpc\_vpn\_info

Gather information about aws virtual private cloud vpn connections

## Requirements

None

## Role Variables

    ec2_vpc_vpn_info_filters: {}
    ec2_vpc_vpn_info_vpn_connection_ids: []

## Return Values

    _ec2_vpc_vpn_info_dict
    _ec2_vpc_vpn_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_vpn_info
          ec2_vpc_vpn_info_filters:
            state:
              - available
