# ec2\_transit\_gateway\_route\_table

Manage aws ec2 transit gateway route tables

## Requirements

None

## Role Variables

    ec2_transit_gateway_route_table_async: 600
    ec2_transit_gateway_route_table_batch: 10
    ec2_transit_gateway_route_table_delay: 3
    ec2_transit_gateway_route_table_list: []
    ec2_transit_gateway_route_table_poll: 0
    ec2_transit_gateway_route_table_retries: 200

## Return Values

None

## Dependencies

* [ec2\_transit\_gateway\_info](../ec2_transit_gateway_info)
* [ec2\_transit\_gateway\_vpc\_attachment\_info](../ec2_transit_gateway_vpc_attachment_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_transit_gateway_route_table
          ec2_transit_gateway_route_table_list:
            - name: molecule
              transit_gateway_id:
                "{{ _ec2_transit_gateway_info_dict['molecule'].transit_gateway_id }}"
              routes:
                - destination_cidr_block: 192.168.0.0/24
                  blackhole: true
                - destination_cidr_block: 192.168.1.0/24
                  transit_gateway_attachment_id:
                    "{{ _ec2_transit_gateway_vpc_attachment_info_dict['molecule'].transit_gateway_attachment_id }}"

            - name: molecule-rtb
              purge_routes: true
              transit_gateway_id:
                "{{ _ec2_transit_gateway_info_dict['molecule'].transit_gateway_id }}"
              routes:
                - destination_cidr_block: 10.10.0.0/16
                  blackhole: true
                - destination_cidr_block: 10.20.0.0/16
                  transit_gateway_attachment_id:
                    "{{ _ec2_transit_gateway_vpc_attachment_info_dict['molecule'].transit_gateway_attachment_id }}"
