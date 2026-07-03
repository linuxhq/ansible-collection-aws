# global\_accelerator

Manage aws global accelerators

## Requirements

None

## Role Variables

    global_accelerator_async: 1500
    global_accelerator_batch: 10
    global_accelerator_delay: 10
    global_accelerator_list: []
    global_accelerator_poll: 0
    global_accelerator_retries: 150

## Return Values

None

## Dependencies

* [ec2\_instance\_info](../ec2_instance_info)
* [elb\_application\_lb\_info](../elb_application_lb_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.global_accelerator
          global_accelerator_list:
            - name: molecule-global-accelerator
              enabled: true
              tags:
                Environment: molecule
              listeners:
                - protocol: TCP
                  port_ranges:
                    - from_port: 443
                      to_port: 443
                  endpoint_groups:
                    - endpoint_group_region: us-east-1
                      traffic_dial_percentage: 100
