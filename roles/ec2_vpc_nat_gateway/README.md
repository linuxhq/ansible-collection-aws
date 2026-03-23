# ec2\_vpc\_nat\_gateway

Manage aws virtual private cloud nat gateways

## Requirements

None

## Role Variables

    ec2_vpc_nat_gateway_async: 300
    ec2_vpc_nat_gateway_batch: 10
    ec2_vpc_nat_gateway_delay: 3
    ec2_vpc_nat_gateway_list: []
    ec2_vpc_nat_gateway_poll: 0
    ec2_vpc_nat_gateway_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_nat_gateway
          ec2_vpc_nat_gateway_list:
            - name: linuxhq-pub-a
              if_exist_do_not_create: true
              release_eip: true
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-pub-a'].id }}"
              wait: true
            - name: linuxhq-pub-b
              if_exist_do_not_create: true
              release_eip: true
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-pub-b'].id }}"
              wait: true
            - name: linuxhq-pub-c
              if_exist_do_not_create: true
              release_eip: true
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-pub-c'].id }}"
              wait: true
