# ec2\_flow\_log

Manage aws ec2 flow logs

## Requirements

None

## Role Variables

    ec2_flow_log_async: 300
    ec2_flow_log_batch: 10
    ec2_flow_log_delay: 3
    ec2_flow_log_list: []
    ec2_flow_log_poll: 0
    ec2_flow_log_retries: 100

## Return Values

None

## Dependencies

* [ec2\_transit\_gateway\_info](../ec2_transit_gateway_info)
* [ec2\_transit\_gateway\_vpc\_attachment\_info](../ec2_transit_gateway_vpc_attachment_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_flow_log
          ec2_flow_log_list:
            - name: molecule-vpc
              resource_ids:
                - "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              resource_type: VPC
              traffic_type: ALL
              log_destination_type: s3
              log_destination: "arn:aws:s3:::molecule-flow-log-{{ _aws_caller_info_account }}"

            - name: molecule-subnet
              resource_ids:
                - "{{ _ec2_vpc_subnet_info_dict['molecule'].id }}"
              resource_type: Subnet
              traffic_type: ACCEPT
              log_destination_type: s3
              log_destination: "arn:aws:s3:::molecule-flow-log-{{ _aws_caller_info_account }}"

            - name: molecule-tgw
              resource_ids:
                - "{{ _ec2_transit_gateway_info_dict['molecule'].transit_gateway_id }}"
              resource_type: TransitGateway
              log_destination_type: s3
              log_destination: "arn:aws:s3:::molecule-flow-log-{{ _aws_caller_info_account }}"

            - name: molecule-tgw-attachment
              resource_ids:
                - "{{ _ec2_transit_gateway_vpc_attachment_info_dict['molecule'] |
                      json_query('transit_gateway_attachment_id') }}"
              resource_type: TransitGatewayAttachment
              log_destination_type: s3
              log_destination: "arn:aws:s3:::molecule-flow-log-{{ _aws_caller_info_account }}"
