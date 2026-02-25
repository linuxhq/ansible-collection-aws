# elb\_application\_lb

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws elastic load balancer application load balancers

## Requirements

None

## Role Variables

    elb_application_lb_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.acm\_certificate\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/acm_certificate_info)
* [linuxhq.aws.elb\_target\_group\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/elb_target_group_info)
* [linuxhq.aws.ec2\_vpc\_nat\_gateway\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_nat_gateway_info)
* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_prefix\_list\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_prefix_list_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

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

## License

Copyright (c) Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
