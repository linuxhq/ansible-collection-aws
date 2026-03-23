# ec2\_vpc\_route\_table

Manage aws virtual private cloud route tables

## Requirements

None

## Role Variables

    ec2_vpc_route_table_async: 300
    ec2_vpc_route_table_batch: 10
    ec2_vpc_route_table_delay: 3
    ec2_vpc_route_table_list: []
    ec2_vpc_route_table_poll: 0
    ec2_vpc_route_table_retries: 100

## Return Values

None

## Dependencies

* [ec2\_transit\_gateway\_info](../ec2_transit_gateway_info)
* [ec2\_vpc\_nat\_gateway\_info](../ec2_vpc_nat_gateway_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_route_table
          ec2_vpc_route_table_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"
              route_tables:
                - name: "{{ aws_vpc }}-pub"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id: igw
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].id }}"
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].id }}"
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].id }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.0 }}"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id:
                        "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.0].nat_gateway_id }}"
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.0].id }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.1 }}"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id:
                        "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.1].nat_gateway_id }}"
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.1].id }}"

                - name: "{{ aws_vpc }}-pvt-{{ _aws_az_info_list_s.2 }}"
                  routes:
                    - dest: '0.0.0.0/0'
                      gateway_id:
                        "{{ _ec2_vpc_nat_gateway_info_dict[aws_vpc ~ '-pub-' ~ _aws_az_info_list_s.2].nat_gateway_id }}"
                  subnets:
                    - "{{ _ec2_vpc_subnet_info_dict[aws_vpc ~ '-pvt-' ~ _aws_az_info_list_s.2].id }}"
