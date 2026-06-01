# ec2\_placement\_group\_info

Gather information about aws placement groups

## Role Variables

    ec2_placement_group_info_filters: {}
    ec2_placement_group_info_group_ids: []
    ec2_placement_group_info_group_names: []

## Return Values

    _ec2_placement_group_info_dict
    _ec2_placement_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_placement_group_info
