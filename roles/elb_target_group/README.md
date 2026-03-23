# elb\_target\_group

Manage aws elastic load balancer target groups

## Requirements

None

## Role Variables

    elb_target_group_async: 300
    elb_target_group_batch: 10
    elb_target_group_delay: 3
    elb_target_group_list: []
    elb_target_group_poll: 0
    elb_target_group_retries: 100

## Return Values

None

## Dependencies

* [ec2\_instance\_info](../ec2_instance_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.elb_target_group
          elb_target_group_list:
            - name: molecule-http-8080
              health_check_interval: 10
              health_check_path: /healthcheck
              health_check_port: 8080
              health_check_protocol: http
              healthy_threshold_count: 3
              port: 8080
              protocol: http
              stickiness_enabled: true
              target_type: instance
              targets:
                - Id: "{{ _ec2_instance_info_dict['molecule-1'].instance_id }}"
                  Port: 8080
                - Id: "{{ _ec2_instance_info_dict['molecule-2'].instance_id }}"
                  Port: 8080
                - Id: "{{ _ec2_instance_info_dict['molecule-3'].instance_id }}"
                  Port: 8080
              unhealthy_threshold_count: 3
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

            - name: molecule-http-8081
              health_check_interval: 10
              health_check_path: /admin
              health_check_port: 8081
              health_check_protocol: http
              healthy_threshold_count: 3
              port: 8081
              protocol: http
              stickiness_enabled: true
              target_type: instance
              targets:
                - Id: "{{ _ec2_instance_info_dict['molecule-1'].instance_id }}"
                  Port: 8081
                - Id: "{{ _ec2_instance_info_dict['molecule-2'].instance_id }}"
                  Port: 8081
                - Id: "{{ _ec2_instance_info_dict['molecule-3'].instance_id }}"
                  Port: 8081
              unhealthy_threshold_count: 3
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
