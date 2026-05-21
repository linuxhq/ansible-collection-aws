# ec2\_vpc\_nat\_gateway

Manage aws virtual private cloud nat gateways

## Requirements

None

## Role Variables

    ec2_vpc_nat_gateway_async: 320
    ec2_vpc_nat_gateway_batch: 10
    ec2_vpc_nat_gateway_delay: 4
    ec2_vpc_nat_gateway_list: []
    ec2_vpc_nat_gateway_poll: 0
    ec2_vpc_nat_gateway_retries: 80

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
            - name: molecule-pub-a
              if_exist_do_not_create: true
              release_eip: true
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-pub-a'].id }}"
              wait: true
            - name: molecule-pub-b
              if_exist_do_not_create: true
              release_eip: true
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-pub-b'].id }}"
              wait: true
            - name: molecule-pub-c
              if_exist_do_not_create: true
              release_eip: true
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-pub-c'].id }}"
              wait: true
