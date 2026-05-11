# elb\_target\_group\_info

Gather information about aws elastic load balancer target groups

## Requirements

None

## Role Variables

    elb_target_group_info_collect_targets_health: false
    elb_target_group_info_load_balancer_arn: null
    elb_target_group_info_names: []
    elb_target_group_info_target_group_arns: []

## Return Values

    _elb_target_group_info_dict
    _elb_target_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.elb_target_group_info
