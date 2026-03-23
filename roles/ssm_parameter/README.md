# ssm\_parameter

Manage aws systems manager key-value pairs

## Requirements

None

## Role Variables

    ssm_parameter_async: 300
    ssm_parameter_batch: 10
    ssm_parameter_delay: 3
    ssm_parameter_list: []
    ssm_parameter_poll: 0
    ssm_parameter_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_igw\_info](../ec2_vpc_igw_info)
* [ec2\_vpc\_nat\_gateway\_info](../ec2_vpc_nat_gateway_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_prefix\_list\_info](../ec2_vpc_prefix_list_info)
* [ec2\_vpc\_route\_table\_info](../ec2_vpc_route_table_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_parameter
          ssm_parameter_list:
            - name: /molecule/vpc/id
              value: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

            - name: /molecule/vpc/igw/id
              value: "{{ _ec2_vpc_igw_info_dict['molecule'].internet_gateway_id }}"

            - name: /molecule/vpc/nat/id
              value: "{{ _ec2_vpc_nat_gateway_info_dict['molecule'].nat_gateway_id }}"

            - name: /molecule/vpc/rtb/a/id
              value: "{{ _ec2_vpc_route_table_info_dict['molecule-a'].route_table_id }}"

            - name: /molecule/vpc/rtb/b/id
              value: "{{ _ec2_vpc_route_table_info_dict['molecule-b'].route_table_id }}"

            - name: /molecule/vpc/subnet/a/id
              value: "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"

            - name: /molecule/vpc/subnet/b/id
              value: "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"
