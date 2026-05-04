# ec2\_vpc\_net

Manage aws virtual private clouds

## Requirements

None

## Role Variables

    ec2_vpc_net_async: 300
    ec2_vpc_net_batch: 10
    ec2_vpc_net_delay: 3
    ec2_vpc_net_list: []
    ec2_vpc_net_poll: 0
    ec2_vpc_net_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_dhcp\_option\_info](../ec2_vpc_dhcp_option_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_net
          ec2_vpc_net_list:
            - name: molecule-00
              cidr_block: 10.0.0.0/16
            - name: molecule-01
              cidr_block: 10.1.0.0/16
            - name: molecule-02
              cidr_block: 10.2.0.0/16
            - name: molecule-03
              cidr_block: 10.3.0.0/16
            - name: molecule-04
              cidr_block: 10.4.0.0/16
