# ec2\_vpc\_vgw

Manage aws virtual private cloud vpn gateways

## Requirements

None

## Role Variables

    ec2_vpc_vgw_async: 300
    ec2_vpc_vgw_batch: 10
    ec2_vpc_vgw_delay: 3
    ec2_vpc_vgw_list: []
    ec2_vpc_vgw_poll: 0
    ec2_vpc_vgw_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_vgw
          ec2_vpc_vgw_list:
            - name: molecule
              vpc_id: "{{ _ec2_vpc_net_info_dict[ec2_vpc_net_list.0.name].id }}"
