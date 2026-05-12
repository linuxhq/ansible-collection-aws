# ec2\_instance\_info

Gather information about aws instances

## Requirements

None

## Role Variables

    ec2_instance_info_filters: {}
    ec2_instance_info_include_attributes: []
    ec2_instance_info_instance_ids: []
    ec2_instance_info_minimum_uptime: null

## Return Values

    _ec2_instance_info_dict
    _ec2_instance_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_instance_info
          ec2_instance_info_filters:
            instance-state-name:
              - running
