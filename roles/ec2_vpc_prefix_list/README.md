# ec2\_vpc\_prefix\_list

Manage aws virtual private cloud prefix lists

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
                - Cidr: 127.0.0.1/32
                  Description: localhost-1
                - Cidr: 127.0.0.2/32
                  Description: localhost-2
                - Cidr: 127.0.0.3/32
                  Description: localhost-3
                - Cidr: 127.0.0.4/32
                  Description: localhost-4
                - Cidr: 127.0.0.5/32
                  Description: localhost-5

            - name: molecule-private
              entries:
                - Cidr: 192.168.1.0/24
                  Description: private-1
                - Cidr: 192.168.2.0/24
                  Description: private-2
                - Cidr: 192.168.3.0/24
                  Description: private-3
                - Cidr: 192.168.4.0/24
                  Description: private-4
                - Cidr: 192.168.5.0/24
                  Description: private-5
