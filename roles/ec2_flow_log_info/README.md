# ec2\_flow\_log\_info

Gather information about aws ec2 flow logs

## Requirements

None

## Role Variables

    ec2_flow_log_info_filters: {}
    ec2_flow_log_info_flow_log_ids: []
    ec2_flow_log_info_resource_ids: []

## Return Values

    _ec2_flow_log_info_dict
    _ec2_flow_log_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_flow_log_info
          ec2_flow_log_info_filters:
            flow-log-status:
              - ACTIVE
