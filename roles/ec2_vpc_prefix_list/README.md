# ec2\_vpc\_prefix\_list

Manage aws virtual private cloud prefix lists

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    ec2_vpc_prefix_list_entries: []

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
            - name: linuxhq-localhost
              entries:
                - Cidr: 127.0.0.1/32
                - Cidr: 127.0.0.2/32
                - Cidr: 127.0.0.3/32
                - Cidr: 127.0.0.4/32
                - Cidr: 127.0.0.5/32

            - name: linuxhq-private
              entries:
                - Cidr: 192.168.1.0/24
                - Cidr: 192.168.2.0/24
                - Cidr: 192.168.3.0/24
                - Cidr: 192.168.4.0/24
                - Cidr: 192.168.5.0/24
