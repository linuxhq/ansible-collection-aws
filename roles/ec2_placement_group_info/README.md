# ec2\_placement\_group\_info

Gather information about ec2 placement groups

## Role Variables

    ec2_placement_group_info_name: null

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
