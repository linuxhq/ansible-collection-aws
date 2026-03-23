# ec2\_customer\_gateway\_info

Gather information about ec2 customer gateways

## Requirements

None

## Role Variables

    ec2_customer_gateway_info_customer_gateway_ids: []
    ec2_customer_gateway_info_filters: {}

## Return Values

    _ec2_customer_gateway_info_dict
    _ec2_customer_gateway_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_customer_gateway_info
