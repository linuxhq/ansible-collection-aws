# elb\_application\_lb\_info

Gather information about aws application load balancers

## Requirements

None

## Role Variables

    elb_application_lb_info_include_attributes: true
    elb_application_lb_info_include_listener_rules: true
    elb_application_lb_info_include_listeners: true
    elb_application_lb_info_load_balancer_arns: []
    elb_application_lb_info_names: []

## Return Values

    _elb_application_lb_info_dict
    _elb_application_lb_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.elb_application_lb_info
