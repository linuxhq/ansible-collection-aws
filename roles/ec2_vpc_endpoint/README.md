# ec2\_vpc\_endpoint

Manage aws virtual private cloud endpoints

## Requirements

None

## Role Variables

    ec2_vpc_endpoint_async: 320
    ec2_vpc_endpoint_batch: 10
    ec2_vpc_endpoint_delay: 4
    ec2_vpc_endpoint_list: []
    ec2_vpc_endpoint_poll: 0
    ec2_vpc_endpoint_retries: 80

## Return Values

None

## Dependencies

* [ec2\_security\_group\_info](../ec2_security_group_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_route\_table\_info](../ec2_vpc_route_table_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_endpoint
          ec2_vpc_endpoint_list:
            - name: molecule
              route_table_ids:
                - "{{ _ec2_vpc_route_table_info_dict['molecule'].id }}"
              service: com.amazonaws.us-east-1.s3
              vpc_endpoint_type: Gateway
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
