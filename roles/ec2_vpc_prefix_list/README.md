# ec2\_vpc\_prefix\_list

Manage aws virtual private cloud prefix lists

## Requirements

None

## Role Variables

    ec2_vpc_prefix_list_async: 300
    ec2_vpc_prefix_list_batch: 10
    ec2_vpc_prefix_list_delay: 3
    ec2_vpc_prefix_list_entries: []
    ec2_vpc_prefix_list_poll: 0
    ec2_vpc_prefix_list_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_prefix_list
          ec2_vpc_prefix_list_entries:
            - name: molecule-localhost
              entries:
                - cidr: 127.0.0.1/32
                  description: localhost-1
                - cidr: 127.0.0.2/32
                  description: localhost-2
                - cidr: 127.0.0.3/32
                  description: localhost-3
                - cidr: 127.0.0.4/32
                  description: localhost-4
                - cidr: 127.0.0.5/32
                  description: localhost-5

            - name: molecule-private
              entries:
                - cidr: 192.168.1.0/24
                  description: private-1
                - cidr: 192.168.2.0/24
                  description: private-2
                - cidr: 192.168.3.0/24
                  description: private-3
                - cidr: 192.168.4.0/24
                  description: private-4
                - cidr: 192.168.5.0/24
                  description: private-5
