# ec2\_customer\_gateway

Manage aws ec2 customer gateways

## Requirements

None

## Role Variables

    ec2_customer_gateway_async: 300
    ec2_customer_gateway_batch: 10
    ec2_customer_gateway_delay: 3
    ec2_customer_gateway_list: []
    ec2_customer_gateway_poll: 0
    ec2_customer_gateway_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_customer_gateway
          ec2_customer_gateway_list:
            - name: "{{ aws_vpc }}-proton1"
              ip_address: 146.70.127.253

            - name: "{{ aws_vpc }}-proton2"
              ip_address: 146.70.127.254
