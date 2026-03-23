# ec2\_vpc\_dhcp\_option

Manage aws virtual private cloud dhcp options

## Requirements

None

## Role Variables

    ec2_vpc_dhcp_option_async: 300
    ec2_vpc_dhcp_option_batch: 10
    ec2_vpc_dhcp_option_delay: 3
    ec2_vpc_dhcp_option_list: []
    ec2_vpc_dhcp_option_poll: 0
    ec2_vpc_dhcp_option_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_dhcp_option
          ec2_vpc_dhcp_option_list:
            - name: linuxhq
              dns_servers:
                - 1.1.1.1
                - 1.1.1.2
