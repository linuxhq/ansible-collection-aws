# ec2\_vpc\_igw

Manage aws virtual private cloud internet gateways

## Requirements

None

## Role Variables

    ec2_vpc_igw_async: 300
    ec2_vpc_igw_batch: 10
    ec2_vpc_igw_delay: 3
    ec2_vpc_igw_list: []
    ec2_vpc_igw_poll: 0
    ec2_vpc_igw_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_igw
          ec2_vpc_igw_list:
            - name: linuxhq
              vpc_id: "{{ _ec2_vpc_net_info_dict['linuxhq'].id }}"
