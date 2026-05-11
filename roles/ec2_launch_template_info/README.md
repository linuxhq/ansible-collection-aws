# ec2\_launch\_template\_info

Gather information about aws launch templates

## Requirements

None

## Role Variables

    ec2_launch_template_info_filters: {}
    ec2_launch_template_info_launch_template_ids: []

## Return Values

    _ec2_launch_template_info_dict
    _ec2_launch_template_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_launch_template_info
