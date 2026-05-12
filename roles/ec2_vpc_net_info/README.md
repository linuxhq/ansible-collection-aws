# ec2\_vpc\_net\_info

Gather information about aws virtual private clouds

## Requirements

None

## Role Variables

    ec2_vpc_net_info_filters: {}
    ec2_vpc_net_info_vpc_ids: []

## Return Values

    _ec2_vpc_net_info_dict
    _ec2_vpc_net_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_net_info
          ec2_vpc_net_info_filters:
            state:
              - available
