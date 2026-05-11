# elb\_application\_lb

Manage aws application load balancers

## Requirements

None

## Role Variables

    elb_application_lb_list: []

## Return Values

None

## Dependencies

* [acm\_certificate\_info](../acm_certificate_info)
* [elb\_target\_group\_info](../elb_target_group_info)
* [ec2\_vpc\_nat\_gateway\_info](../ec2_vpc_nat_gateway_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_prefix\_list\_info](../ec2_vpc_prefix_list_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.elb_application_lb
          elb_application_lb_list:
            - name: molecule-http-80
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"
              listeners:
                - Protocol: HTTP
                  Port: 80
                  DefaultActions:
                    - Type: forward
                      TargetGroupName: molecule-http-8080
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

            - name: molecule-http-81
              rules:
                - cidr_ip: 0.0.0.0/0
                  ports: 81
                  proto: tcp
              rules_egress:
                - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                  proto: -1
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"
              listeners:
                - Protocol: HTTP
                  Port: 81
                  DefaultActions:
                    - Type: forward
                      TargetGroupName: molecule-http-8081
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
