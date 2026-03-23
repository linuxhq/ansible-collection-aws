# wafv2\_resources

Manage aws wafv2 resources

## Requirements

None

## Role Variables

    wafv2_resources_async: 300
    wafv2_resources_batch: 10
    wafv2_resources_delay: 3
    wafv2_resources_list: []
    wafv2_resources_poll: 0
    wafv2_resources_retries: 100

## Return Values

None

## Dependencies

* [elb\_application\_lb\_info](../elb_application_lb_info)
* [wafv2\_web\_acl\_info](../wafv2_web_acl_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.wafv2_resources
          wafv2_resources_list:
            - arn: "{{ _elb_application_lb_info_dict['molecule'].load_balancer_arn }}"
              name: molecule
              scope: regional
