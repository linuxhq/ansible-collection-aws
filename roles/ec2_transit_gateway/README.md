# ec2\_transit\_gateway

Manage aws ec2 transit gateways

## Requirements

None

## Role Variables

    ec2_transit_gateway_async: 300
    ec2_transit_gateway_batch: 10
    ec2_transit_gateway_delay: 3
    ec2_transit_gateway_list: []
    ec2_transit_gateway_poll: 0
    ec2_transit_gateway_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_transit_gateway
          ec2_transit_gateway_list:
            - name: linuxhq
