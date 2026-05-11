# ec2\_vpc\_dhcp\_option\_info

Gather information about aws virtual private cloud dhcp options

## Requirements

None

## Role Variables

    ec2_vpc_dhcp_option_info_dhcp_options_ids: []
    ec2_vpc_dhcp_option_info_filters: {}

## Return Values

    _ec2_vpc_dhcp_option_info_dict
    _ec2_vpc_dhcp_option_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_vpc_dhcp_option_info
