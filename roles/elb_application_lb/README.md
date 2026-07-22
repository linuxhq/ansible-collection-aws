# elb\_application\_lb

Manage aws application load balancers

## Requirements

None

## Role Variables

    elb_application_lb_async: 600
    elb_application_lb_batch: 10
    elb_application_lb_delay: 3
    elb_application_lb_list: []
    elb_application_lb_poll: 0
    elb_application_lb_retries: 200

## Return Values

None

## Dependencies

* [acm\_certificate\_info](../acm_certificate_info)
* [ec2\_security\_group\_info](../ec2_security_group_info)
* [ec2\_vpc\_nat\_gateway\_info](../ec2_vpc_nat_gateway_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_prefix\_list\_info](../ec2_vpc_prefix_list_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)
* [elb\_target\_group\_info](../elb_target_group_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_security_group
          ec2_security_group_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              security_groups:
                - name: molecule-http-80
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 80
                        - 443
                      proto: tcp

        - role: linuxhq.aws.elb_application_lb
          elb_application_lb_list:
            - name: molecule-http-80
              listeners:
                - Protocol: HTTP
                  Port: 80
                  DefaultActions:
                    - Type: forward
                      TargetGroupName: molecule-http-8080
              security_groups:
                - "{{ _ec2_security_group_info_dict['molecule-http-80'].group_id }}"
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"
