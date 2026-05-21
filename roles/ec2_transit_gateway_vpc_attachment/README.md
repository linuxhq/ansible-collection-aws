# ec2\_transit\_gateway\_vpc\_attachment

Manage aws ec2 transit gateway vpc attachments

## Requirements

None

## Role Variables

    ec2_transit_gateway_vpc_attachment_async: 600
    ec2_transit_gateway_vpc_attachment_batch: 10
    ec2_transit_gateway_vpc_attachment_delay: 3
    ec2_transit_gateway_vpc_attachment_list: []
    ec2_transit_gateway_vpc_attachment_poll: 0
    ec2_transit_gateway_vpc_attachment_retries: 200

## Return Values

None

## Dependencies

* [ec2\_transit\_gateway\_info](../ec2_transit_gateway_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_transit_gateway_vpc_attachment
          ec2_transit_gateway_vpc_attachment_list:
            - name: molecule
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule'].id }}"
              transit_gateway: "{{ _ec2_transit_gateway_info_dict['molecule'].transit_gateway_id }}"
