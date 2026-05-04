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
            - name: molecule-cgw-01
              ip_address: 52.93.22.49
            - name: molecule-cgw-02
              ip_address: 52.93.22.50
            - name: molecule-cgw-03
              ip_address: 52.93.22.51
            - name: molecule-cgw-04
              ip_address: 52.93.22.52
            - name: molecule-cgw-05
              ip_address: 52.93.22.53
            - name: molecule-cgw-06
              ip_address: 52.93.22.54
            - name: molecule-cgw-07
              ip_address: 52.93.22.55
            - name: molecule-cgw-08
              ip_address: 52.93.22.56
            - name: molecule-cgw-09
              ip_address: 52.93.22.57
            - name: molecule-cgw-10
              ip_address: 52.93.22.58
            - name: molecule-cgw-11
              ip_address: 52.93.22.59
            - name: molecule-cgw-12
              ip_address: 52.93.22.60
            - name: molecule-cgw-13
              ip_address: 52.93.22.61
            - name: molecule-cgw-14
              ip_address: 52.93.22.62
