# ec2\_vpc\_endpoint\_info

Gather information about aws virtual private cloud endpoints

## Requirements

None

## Role Variables

    ec2_vpc_endpoint_info_filters: {}
    ec2_vpc_endpoint_info_vpc_endpoint_ids: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_endpoint_info
          ec2_vpc_endpoint_info_filters:
            vpc-endpoint-state:
              - available
