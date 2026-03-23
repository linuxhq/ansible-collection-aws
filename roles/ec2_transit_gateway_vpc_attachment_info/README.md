# ec2\_transit\_gateway\_vpc\_attachment\_info

Gather information about ec2 transit gateway vpc attachments

## Requirements

None

## Role Variables

    ec2_transit_gateway_vpc_attachment_info_filters: {}

## Return Values

    _ec2_transit_gateway_vpc_attachment_info_dict
    _ec2_transit_gateway_vpc_attachment_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_transit_gateway_vpc_attachment_info
