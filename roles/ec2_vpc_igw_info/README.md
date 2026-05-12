# ec2\_vpc\_igw\_info

Gather information about aws virtual private cloud internet gateways

## Requirements

None

## Role Variables

    ec2_vpc_igw_info_filters: {}
    ec2_vpc_igw_info_internet_gateway_ids: []

## Return Values

    _ec2_vpc_igw_info_dict
    _ec2_vpc_igw_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_igw_info
          ec2_vpc_igw_info_filters:
            attachment.state:
              - available
